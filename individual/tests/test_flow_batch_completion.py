"""
Signal-level coverage for CSV import tasks following a multi-step approval
flow (openimis-be-tasks_management_py#72). Proves two properties raised in
review: an intermediate vote must not run the import workflow, and the
workflow that eventually runs must see only the records that survived every
step - not the ones rejected along the way.

The workflow's own SQL procedure is mocked out (autospec, capturing `self`)
so these tests exercise the real signal dispatch chain - TaskService.resolve_task
-> tasks_management's flow resolver -> this module's on_task_resolve /
on_task_complete_action - without needing the underlying stored procedures.
"""
from unittest.mock import patch

from django.test import TestCase

from core.test_helpers import create_test_interactive_user
from individual.apps import IndividualConfig
from individual.models import (
    IndividualDataSource,
    IndividualDataSourceUpload,
    IndividualDataUploadRecords,
)
from individual.signals.on_validation_import_valid_items import (
    IndividualItemsImportTaskCompletionEvent,
)
from tasks_management.apps import TasksManagementConfig
from tasks_management.models import Task, TaskExecutor, TaskFlow, TaskFlowStep, TaskGroup
from tasks_management.services import TaskService


class FlowBatchCompletionTestCase(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.admin = create_test_interactive_user(username="fbc_admin")
        cls.exec_a = create_test_interactive_user(username="fbc_exec_a")
        cls.exec_b = create_test_interactive_user(username="fbc_exec_b")

    def _group(self, code, executors):
        group = TaskGroup(code=code, completion_policy='ANY')
        group.save(username=self.admin.username)
        for user in executors:
            TaskExecutor(task_group=group, user=user).save(username=self.admin.username)
        return group

    def _two_step_flow(self, code):
        group1 = self._group(f'{code}_g1', [self.exec_a])
        group2 = self._group(f'{code}_g2', [self.exec_b])
        flow = TaskFlow(code=code, name=code)
        flow.save(username=self.admin.username)
        step1 = TaskFlowStep(flow=flow, task_group=group1, order=1)
        step1.save(username=self.admin.username)
        step2 = TaskFlowStep(flow=flow, task_group=group2, order=2)
        step2.save(username=self.admin.username)
        return flow, step1, step2

    def _upload_with_sources(self, record_count):
        upload = IndividualDataSourceUpload(source_name='fbc_test', source_type='csv')
        upload.save(username=self.admin.username)
        upload_record = IndividualDataUploadRecords(data_upload=upload, workflow='fbc')
        upload_record.save(username=self.admin.username)
        sources = []
        for i in range(record_count):
            source = IndividualDataSource(upload=upload, json_ext={'first_name': f'row{i}'})
            source.save(username=self.admin.username)
            sources.append(source)
        return upload_record, sources

    def _flow_task(self, flow, step, upload_record):
        task = Task(
            source='import_valid_items',
            entity=upload_record,
            status=Task.Status.ACCEPTED,
            executor_action_event=TasksManagementConfig.default_executor_event,
            business_event=IndividualConfig.validation_import_valid_items,
            business_status={}, data={},
            flow=flow, current_step=step, task_group=step.task_group,
        )
        task.save(username=self.admin.username)
        return task

    def _vote(self, task, user, verdict):
        return TaskService(user).resolve_task({
            'id': task.id, 'business_status': {str(user.id): verdict},
        })

    def test_intermediate_vote_does_not_run_workflow(self):
        flow, step1, step2 = self._two_step_flow('FBC_MID')
        upload_record, sources = self._upload_with_sources(3)
        task = self._flow_task(flow, step1, upload_record)

        with patch.object(
            IndividualItemsImportTaskCompletionEvent, 'run_workflow', autospec=True,
        ) as mock_run:
            result = self._vote(task, self.exec_a, {'ACCEPT': [str(sources[0].id)]})
            self.assertTrue(result.get('success'), result)
            task.refresh_from_db()
            self.assertEqual(task.status, Task.Status.ACCEPTED)
            mock_run.assert_not_called()

    def test_completion_receives_only_surviving_records(self):
        flow, step1, step2 = self._two_step_flow('FBC_FINAL')
        upload_record, sources = self._upload_with_sources(3)
        task = self._flow_task(flow, step1, upload_record)

        # step 1: reject source[0], accept the rest
        result = self._vote(task, self.exec_a, {
            'ACCEPT': [str(sources[1].id), str(sources[2].id)],
            'REJECT': [str(sources[0].id)],
        })
        self.assertTrue(result.get('success'), result)
        task.refresh_from_db()
        self.assertEqual(task.status, Task.Status.ACCEPTED)
        self.assertEqual(task.current_step_id, step2.id)

        captured = []

        def fake_run_workflow(self):
            captured.append(self)

        with patch.object(
            IndividualItemsImportTaskCompletionEvent, 'run_workflow',
            autospec=True, side_effect=fake_run_workflow,
        ) as mock_run:
            # step 2: reject source[1] too - cumulative across both steps
            result = self._vote(task, self.exec_b, {
                'ACCEPT': [str(sources[2].id)],
                'REJECT': [str(sources[1].id)],
            })
            self.assertTrue(result.get('success'), result)
            task.refresh_from_db()
            self.assertEqual(task.status, Task.Status.COMPLETED)
            mock_run.assert_called_once()

        self.assertEqual(len(captured), 1)
        accepted_ids = set(captured[0].accepted)
        self.assertEqual(accepted_ids, {str(sources[2].id)})
        self.assertNotIn(str(sources[0].id), accepted_ids)
        self.assertNotIn(str(sources[1].id), accepted_ids)
