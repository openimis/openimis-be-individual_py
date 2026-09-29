from io import StringIO

from django.core.management import CommandError, call_command
from django.test import TestCase

from core.test_helpers import LogInHelper
from individual.tests.test_helpers import create_individual_label, set_individual_schema


class CheckIndividualSchemaUsageTest(TestCase):
    user = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = LogInHelper().get_or_create_user_api()

    def setUp(self):
        super().setUp()
        set_individual_schema(self, {"properties": {"licence_no": {"type": "string"}, "badge": {"type": "string"}}})
        create_individual_label(self.user.username, 'TEST_LABEL_A', {
            'json_schema': {"properties": {"licence_no": {"type": "string"}}},
        })
        create_individual_label(self.user.username, 'TEST_LABEL_B', {
            'json_schema': {"properties": {"badge": {"type": "string"}}},
        })

    def test_reports_success_when_every_schema_is_aligned(self):
        out = StringIO()
        call_command('check_individual_schema_usage', stdout=out)
        self.assertIn('All schemas are aligned', out.getvalue())

    def test_lists_schemas_using_fields_the_individual_schema_lost(self):
        set_individual_schema(self, {"properties": {"licence_no": {"type": "integer"}}})
        out = StringIO()

        with self.assertRaisesMessage(CommandError, '2 schema(s)'):
            call_command('check_individual_schema_usage', stdout=out)

        self.assertIn('TEST_LABEL_A: ', out.getvalue())
        self.assertIn('licence_no', out.getvalue())
        self.assertIn('TEST_LABEL_B: ', out.getvalue())
        self.assertIn('badge', out.getvalue())
