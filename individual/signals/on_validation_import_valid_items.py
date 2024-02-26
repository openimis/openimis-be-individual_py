import logging

from core.models import User
from tasks_management.models import Task
from individual.apps import IndividualConfig
from individual.models import IndividualDataUploadRecords
from workflow.services import WorkflowService

logger = logging.getLogger(__name__)


def on_task_complete_validation_individual_import_valid_items(**kwargs):
    def validation_import_valid_items(upload_id, user, percentage_of_invalid_items):
        from individual.workflows.base_individual_upload import process_import_individual_workflow_valid
        process_import_individual_workflow_valid(
            user_uuid=user.id,
            upload_uuid=upload_id,
            percentage_of_invalid_items=percentage_of_invalid_items
        )

    try:
        result = kwargs.get('result', None)
        task = result['data']['task']
        if result \
                and result['success'] \
                and task['business_event'] == IndividualConfig.validation_import_valid_items:
            task_status = task['status']
            if task_status == Task.Status.COMPLETED:
                user = User.objects.get(id=result['data']['user']['id'])
                upload_record = IndividualDataUploadRecords.objects.get(id=task['entity_id'])
                upload_id = upload_record.data_upload.id
                percentage_of_invalid_items = task['json_ext']['percentage_of_invalid_items']
                validation_import_valid_items(upload_id, user, percentage_of_invalid_items)
    except Exception as exc:
        logger.error("Error while executing on_task_complete_validation_individual_import_valid_items", exc_info=exc)
