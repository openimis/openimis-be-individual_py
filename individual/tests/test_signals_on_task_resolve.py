from django.test import SimpleTestCase

from individual.signals.on_validation_import_valid_items import on_task_resolve

SIGNAL_LOGGER = 'individual.signals.on_validation_import_valid_items'
COMPLETED_TASK_MESSAGE = 'Cannot update completed task'


class OnTaskResolveGuardTest(SimpleTestCase):
    """
    on_task_resolve receives the raw output of TaskService.resolve_task; a failed
    call carries a string instead of a dict in 'data'. The handler must skip such
    results with a warning, without raising and without touching the database.
    """

    def _assert_skipped_with_warning(self, expected_fragment, **kwargs):
        with self.assertLogs(SIGNAL_LOGGER, level='WARNING') as captured:
            self.assertIsNone(on_task_resolve(**kwargs))
        self.assertEqual(len(captured.records), 1)
        self.assertEqual(captured.records[0].levelname, 'WARNING')
        self.assertIn(expected_fragment, captured.output[0])

    def test_failed_result_with_string_task_is_skipped(self):
        result = {
            'success': False,
            'message': 'Failed to resolve Task',
            'detail': COMPLETED_TASK_MESSAGE,
            'data': {'task': COMPLETED_TASK_MESSAGE},
        }
        self._assert_skipped_with_warning(COMPLETED_TASK_MESSAGE, result=result)

    def test_failed_result_with_empty_string_data_is_skipped(self):
        result = {
            'success': False,
            'message': 'Failed to resolve Task',
            'detail': COMPLETED_TASK_MESSAGE,
            'data': '',
        }
        self._assert_skipped_with_warning(COMPLETED_TASK_MESSAGE, result=result)

    def test_successful_result_without_task_dict_is_skipped(self):
        result = {'success': True, 'message': 'Ok', 'data': {'task': 'not-a-dict'}}
        self._assert_skipped_with_warning('no task data', result=result)

    def test_missing_result_is_skipped(self):
        self._assert_skipped_with_warning('None')
