from unittest.mock import patch

from django.test import TestCase

from core.test_helpers import LogInHelper
from individual.models import Individual, IndividualLabel
from individual.services import IndividualLabelService, IndividualService
from individual.tests.test_helpers import create_individual, create_individual_label, set_individual_schema


class IndividualLabelServiceTest(TestCase):
    user = None
    service = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = LogInHelper().get_or_create_user_api()
        cls.service = IndividualLabelService(cls.user)

    def setUp(self):
        super().setUp()
        set_individual_schema(self, {"properties": {
            "licence_no": {"type": "string"}, "years": {"type": "integer"}, "fee": {"type": "decimal"},
            "licensed_on": {"type": "date"}, "active": {"type": "boolean"},
        }})

    def test_create_label(self):
        result = self.service.create({'code': 'TEST_LABEL_A', 'name': 'Test A'})
        self.assertTrue(result.get('success', False), result.get('detail', "No details provided"))
        self.assertEqual(IndividualLabel.objects.filter(code='TEST_LABEL_A', is_deleted=False).count(), 1)

    def test_create_label_with_schema(self):
        schema = {"properties": {"licence_no": {"type": "string"}}}
        result = self.service.create({'code': 'TEST_LABEL_A', 'name': 'Test A', 'json_schema': schema})
        self.assertTrue(result.get('success', False), result.get('detail', "No details provided"))
        self.assertEqual(IndividualLabel.objects.get(code='TEST_LABEL_A').json_schema, schema)

    def test_create_label_rejects_bad_code(self):
        for code in ['test_label', 'TEST LABEL', '1ST', 'A', 'A' * 65, '', 'TEST_LABEL\n', 'NA', 'NULL']:
            result = self.service.create({'code': code, 'name': 'x'})
            self.assertFalse(result.get('success', True), code)

    def test_create_label_rejects_duplicate_code(self):
        self.service.create({'code': 'TEST_LABEL_A', 'name': 'Test A'})
        result = self.service.create({'code': 'TEST_LABEL_A', 'name': 'again'})
        self.assertFalse(result.get('success', True))
        self.assertIn('TEST_LABEL_A', result.get('detail', ''))

    def test_create_label_accepts_every_filter_type(self):
        schema = {"properties": {
            "licence_no": {"type": "string"}, "years": {"type": "integer"}, "fee": {"type": "decimal"},
            "licensed_on": {"type": "date"}, "active": {"type": "boolean"},
        }}
        result = self.service.create({'code': 'TEST_LABEL_A', 'name': 'x', 'json_schema': schema})
        self.assertTrue(result.get('success'), result)

    def test_create_label_rejects_fields_missing_from_the_individual_schema(self):
        schema = {"properties": {"licence_no": {"type": "string"}, "badge": {"type": "string"}}}
        result = self.service.create({'code': 'TEST_LABEL_A', 'name': 'x', 'json_schema': schema})
        self.assertFalse(result.get('success', True))
        self.assertIn('badge', result.get('detail', ''))
        self.assertNotIn('licence_no', result.get('detail', ''))

    def test_create_label_rejects_a_type_that_differs_from_the_individual_schema(self):
        schema = {"properties": {"years": {"type": "string"}, "badge": {"type": "string"}}}
        result = self.service.create({'code': 'TEST_LABEL_A', 'name': 'x', 'json_schema': schema})
        self.assertFalse(result.get('success', True))
        self.assertIn('years', result.get('detail', ''))
        self.assertIn('badge', result.get('detail', ''))

    def test_create_label_accepts_a_schema_without_fields(self):
        result = self.service.create({'code': 'TEST_LABEL_A', 'name': 'x', 'json_schema': {"properties": {}}})
        self.assertTrue(result.get('success'), result)

    def test_update_label_rejects_fields_missing_from_the_individual_schema(self):
        label = create_individual_label(self.user.username, 'TEST_LABEL_A')
        result = self.service.update({'id': label.id, 'json_schema': {"properties": {"badge": {"type": "string"}}}})
        self.assertFalse(result.get('success', True))
        self.assertIn('badge', result.get('detail', ''))

    def test_create_label_applies_the_field_option_rules(self):
        schema = {"properties": {"licence_no": {"type": "string", "uniqueness": False}}}
        result = self.service.create({'code': 'TEST_LABEL_A', 'name': 'x', 'json_schema': schema})
        self.assertFalse(result.get('success', True))
        self.assertIn('licence_no', result.get('detail', ''))

    def test_create_label_rejects_invalid_schema(self):
        result = self.service.create({'code': 'TEST_LABEL_A', 'name': 'x', 'json_schema': {'type': 'nope'}})
        self.assertFalse(result.get('success', True))

    def test_create_label_rejects_schema_the_filter_wizard_cannot_use(self):
        for schema in [
            '{"properties": {}}',
            ['a'],
            {"properties": []},
            {"properties": {"licence_no": {}}},
            {"properties": {"licence_no": {"type": ["string", "null"]}}},
            {"properties": {"address": {"type": "object"}}},
        ]:
            result = self.service.create({'code': 'TEST_LABEL_A', 'name': 'x', 'json_schema': schema})
            self.assertFalse(result.get('success', True), schema)
        self.assertFalse(IndividualLabel.objects.filter(code='TEST_LABEL_A').exists())

    def test_update_label_code_is_immutable(self):
        label = create_individual_label(self.user.username, 'TEST_LABEL_A')
        result = self.service.update({'id': label.id, 'code': 'TEST_LABEL_B'})
        self.assertFalse(result.get('success', True))
        result = self.service.update({'id': label.id, 'name': 'Renamed'})
        self.assertTrue(result.get('success', False), result.get('detail', "No details provided"))
        label.refresh_from_db()
        self.assertEqual((label.code, label.name), ('TEST_LABEL_A', 'Renamed'))

    def test_update_deleted_label_refused(self):
        label = create_individual_label(self.user.username, 'TEST_LABEL_A')
        label.delete(username=self.user.username)
        self.assertFalse(self.service.update({'id': label.id, 'name': 'Renamed'}).get('success', True))

    @patch('individual.apps.IndividualConfig.check_individual_update', True)
    def test_delete_label_refused_while_pending_task_adds_it(self):
        label = create_individual_label(self.user.username, 'TEST_LABEL_A')
        individual = create_individual(self.user.username)
        task = IndividualService(self.user).create_update_task({
            'id': individual.id, 'first_name': individual.first_name, 'last_name': individual.last_name,
            'dob': individual.dob, 'labels': ['TEST_LABEL_A'],
        })
        self.assertTrue(task.get('success', False), task.get('detail', "No details provided"))

        result = self.service.delete({'id': label.id})

        self.assertFalse(result.get('success', True))
        self.assertIn('TEST_LABEL_A', result.get('detail', ''))

    def test_delete_label_in_use_refused(self):
        label = create_individual_label(self.user.username, 'TEST_LABEL_A')
        create_individual(self.user.username, payload_override={'labels': ['TEST_LABEL_A']})
        result = self.service.delete({'id': label.id})
        self.assertFalse(result.get('success', True))
        self.assertIn('TEST_LABEL_A', result.get('detail', ''))

        Individual.objects.filter(labels__contains=['TEST_LABEL_A']).update(labels=[])
        result = self.service.delete({'id': label.id})
        self.assertTrue(result.get('success', False), result.get('detail', "No details provided"))
        label.refresh_from_db()
        self.assertTrue(label.is_deleted)

    def test_delete_label_refused_while_soft_deleted_individual_carries_it(self):
        label = create_individual_label(self.user.username, 'TEST_LABEL_A')
        individual = create_individual(self.user.username, payload_override={'labels': ['TEST_LABEL_A']})
        individual.delete(username=self.user.username)
        result = self.service.delete({'id': label.id})
        self.assertFalse(result.get('success', True))
