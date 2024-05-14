import logging
from typing import List

from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import Count

from core.models import User
from individual.models import (
    IndividualDataSourceUpload,
    IndividualDataSource,
    IndividualDataUploadRecords, Group, GroupIndividual, Individual
)
from tasks_management.models import Task
from workflow.services import WorkflowService

logger = logging.getLogger(__name__)


class ItemsUploadTaskCompletionEvent:
    def run_workflow(self):
        group, name = self.workflow_name.split('.')
        workflow = self._get_workflow(group, name)
        result = workflow.run({
            'user_uuid': str(self.user.id),
            'upload_uuid': str(self.upload_id),
            'accepted': self.accepted
        })
        if not result.get('success'):
            if self.upload_record:
                data_upload = self.upload_record.data_upload
                data_upload.status = IndividualDataSourceUpload.Status.FAIL
                data_upload.error = {"Task Resolve": str(result.get('message'))}
                # Todo: this should be changed to system user
                data_upload.save(username=data_upload.user_updated.username)

    def _get_workflow(self, group, name):
        result_workflow = WorkflowService.get_workflows(name, group)
        if not result_workflow.get('success'):
            raise ValueError('{}: {}'.format(result_workflow.get("message"), result_workflow.get("details")))
        workflows = result_workflow.get('data', {}).get('workflows')
        if not workflows:
            raise ValueError('Workflow not found: group={} name={}'.format(group, name))
        if len(workflows) > 1:
            raise ValueError('Multiple workflows found: group={} name={}'.format(group, name))
        workflow = workflows[0]
        return workflow

    def __init__(self, workflow: str, upload_record, upload_id: str, user: User, accepted: List[str] = None):
        """
        Workflow name should be in workflow_group.workflow_name notation.
        Upload ID is IndividualDataSource upload id.
        User is actor performing action.
        """
        self.workflow_name = workflow
        self.upload_record = upload_record
        self.upload_id = upload_id
        self.user = user
        self.accepted = accepted


class IndividualItemsImportTaskCompletionEvent(ItemsUploadTaskCompletionEvent):
    def run_workflow(self):
        super().run_workflow()

        if not self.upload_record:
            return

        upload_record_json_ext = self.upload_record.json_ext or {}
        group_aggregation_column = upload_record_json_ext.get('group_aggregation_column')

        if not group_aggregation_column:
            return

        individuals = self._get_individuals()

        grouped_individuals = self._get_grouped_individuals(individuals, group_aggregation_column)

        self._create_groups(grouped_individuals)

    def _get_individuals(self):
        return IndividualDataSource.objects.filter(
            upload__id=self.upload_id, individual__isnull=False, is_deleted=False
        ).prefetch_related('individual')

    def _get_grouped_individuals(self, individuals_qs, group_aggregation_column):
        return (
            individuals_qs
            .values(f'json_ext__{group_aggregation_column}')
            .annotate(
                record_ids=ArrayAgg('individual_id'),
                num_records=Count('id')
            )
            .filter(num_records__gt=1)
        )

    def _create_groups(self, grouped_individuals):
        for individual_group in grouped_individuals:
            ids = individual_group['record_ids']
            group = Group()
            group.save(username=self.user.username)
            self._add_individuals_to_group(ids, group)

    def _add_individuals_to_group(self, ids, group):
        for individual_id in ids:
            if GroupIndividual.objects.filter(id=individual_id, group_id=group.id).exists():
                continue
            self._create_group_individual(individual_id, group)

    def _create_group_individual(self, individual_id, group):
        group_individual = GroupIndividual(individual_id=individual_id, group_id=group.id)
        individual = Individual.objects.filter(id=individual_id).first()
        if individual:
            self._set_group_individual_role(group_individual, individual)
        group_individual.save(username=self.user.username)

    def _set_group_individual_role(self, group_individual, individual):
        individual_json_ext = individual.json_ext or {}
        recipient_info = individual_json_ext.get('recipient_info')
        if recipient_info in [1, '1']:
            group_individual.role = GroupIndividual.Role.HEAD
        elif recipient_info in [2, '2']:
            group_individual.role = GroupIndividual.Role.RECIPIENT


def on_task_complete_action(business_event, **kwargs):
    from individual.apps import IndividualConfig

    result = kwargs.get('result')
    if not result or not result.get('success'):
        return

    data = result.get('data')
    task = data.get('task') if data else None
    # Further conditions for early return
    if not task or task.get('business_event') != business_event:
        return

    task_status = task.get('status')
    if task_status != Task.Status.COMPLETED:
        return

    # Main logic remains unchanged, assuming necessary variables are correctly set
    upload_record = None
    try:
        upload_record = IndividualDataUploadRecords.objects.get(id=task['entity_id'])
        if business_event == IndividualConfig.validation_import_valid_items:
            workflow = IndividualConfig.validation_import_valid_items_workflow
            IndividualItemsImportTaskCompletionEvent(
                workflow,
                upload_record,
                upload_record.data_upload.id,
                User.objects.get(id=data['user']['id'])
            ).run_workflow()
        elif business_event == IndividualConfig.validation_upload_valid_items:
            workflow = IndividualConfig.validation_upload_valid_items_workflow
            ItemsUploadTaskCompletionEvent(
                workflow,
                upload_record,
                upload_record.data_upload.id,
                User.objects.get(id=data['user']['id'])
            ).run_workflow()
        else:
            raise ValueError(f"Business event {business_event} doesn't have assigned workflow.")
    except Exception as exc:
        if upload_record:
            data_upload = upload_record.data_upload
            data_upload.status = IndividualDataSourceUpload.Status.FAIL
            data_upload.error = {"Task Resolve": str(exc)}
            # Todo: this should be changed to system user
            data_upload.save(username=data_upload.user_updated.username)
        logger.error(f"Error while executing on_task_complete_action for {business_event}", exc_info=exc)


def on_task_complete_import_validated(**kwargs):
    from individual.apps import IndividualConfig
    on_task_complete_action(IndividualConfig.validation_import_valid_items, **kwargs)
    on_task_complete_action(IndividualConfig.validation_upload_valid_items, **kwargs)


def _delete_rejected(uuids_list):
    # Use soft delete to remove atomic tasks, it's not possible to mark them on level of Individual.
    sources_to_update = IndividualDataSource.objects.filter(id__in=uuids_list)

    # Set is_deleted to True for each instance
    for source in sources_to_update:
        source.is_deleted = True

    # Perform the bulk update
    IndividualDataSource.objects.bulk_update(sources_to_update, ['is_deleted'])


def _complete_task_for_accepted(_task, accept, user):
    from individual.apps import IndividualConfig
    upload_record = IndividualDataUploadRecords.objects.get(id=_task.entity_id)

    if not upload_record:
        return

    if _task.business_event == IndividualConfig.validation_import_valid_items:
        ItemsUploadTaskCompletionEvent(
            IndividualConfig.validation_import_valid_items_workflow,
            upload_record,
            upload_record.data_upload.id,
            user,
            accept
        ).run_workflow()

    if _task.business_event == IndividualConfig.validation_upload_valid_items:
        ItemsUploadTaskCompletionEvent(
            IndividualConfig.validation_upload_valid_items_workflow,
            upload_record,
            upload_record.data_upload.id,
            user,
            accept
        ).run_workflow()


def _resolve_task_any(_task: Task, _user):
    # Atomic resolution of individuals
    user_id_str = str(_user.id)
    if isinstance(_task.business_status.get(user_id_str), dict):
        last = _task.history.first().prev_record
        if last and isinstance(last.business_status.get(user_id_str), dict):
            # Only new approvals/rejections, the format is {user_id: {[ACCEPT|REJECT]: [uuid1_, ... uuid_n]}
            accept = list(set(_task.business_status[user_id_str].get('ACCEPT', []))
                          - set(last.business_status[user_id_str].get('ACCEPT', [])))
            reject = list(set(_task.business_status[user_id_str].get('REJECT', []))
                          - set(last.business_status[user_id_str].get('REJECT', [])))
        else:
            accept = _task.business_status[user_id_str].get('ACCEPT', [])
            reject = _task.business_status[user_id_str].get('REJECT', [])

        _delete_rejected(reject)
        _complete_task_for_accepted(_task, accept, _user)


def _resolve_task_all(_task, _user):
    # TODO for now hardcoded to any, to be updated
    _resolve_task_any(_task, _user)


def _resolve_task_n(_task, _user):
    # TODO for now hardcoded to any, to be updated
    _resolve_task_any(_task, _user)


def on_task_resolve(**kwargs):
    from tasks_management.apps import TasksManagementConfig
    from individual.apps import IndividualConfig
    """
    Partial approval requires custom resolve policy that doesn't rely on default APPROVE value in businessStatus.
    """
    try:
        result = kwargs.get('result', None)
        task_data = result['data']['task']
        if result and result['success'] \
                and task_data['status'] == Task.Status.ACCEPTED \
                and task_data['executor_action_event'] == TasksManagementConfig.default_executor_event \
                and task_data['business_event'] in [
                    IndividualConfig.validation_import_valid_items,
                    IndividualConfig.validation_upload_valid_items
                ]:
            data = kwargs.get("result").get("data")
            task = Task.objects.select_related('task_group').prefetch_related('task_group__taskexecutor_set').get(
                id=data["task"]["id"])
            user = User.objects.get(id=data["user"]["id"])

            # Task only relevant for this specific source
            if task.source != 'import_valid_items':
                return

            if not task.task_group:
                logger.error("Resolving task not assigned to TaskGroup: %s", data['task']['id'])
                return ['Task not assigned to TaskGroup']

            resolvers = {
                'ALL': _resolve_task_all,
                'ANY': _resolve_task_any,
                'N': _resolve_task_n,
            }

            if task.task_group.completion_policy not in resolvers:
                logger.error("Resolving task with unknown completion_policy: %s", task.task_group.completion_policy)
                return ['Unknown completion_policy: %s' % task.task_group.completion_policy]

            resolvers[task.task_group.completion_policy](task, user)
    except Exception as e:
        logger.error("Error while executing on_task_resolve", exc_info=e)
        return [str(e)]