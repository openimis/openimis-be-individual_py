import json
from datetime import datetime, timedelta
from unittest.mock import patch

from django.test import TestCase

from core.models import ModuleConfiguration
from core.test_helpers import LogInHelper
from individual.apps import IndividualConfig
from individual.models import IndividualLabel
from individual.services import IndividualSchemaService
from individual.tests.test_helpers import create_individual_label, set_individual_schema


class IndividualSchemaServiceTest(TestCase):
    user = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = LogInHelper().get_or_create_user_api()

    def setUp(self):
        super().setUp()
        set_individual_schema(self, {"properties": {
            "licence_no": {"type": "string"}, "years": {"type": "integer"}, "email": {"type": "string"},
        }})
        create_individual_label(self.user.username, 'TEST_LABEL_A', {
            'json_schema': {"properties": {"licence_no": {"type": "string"}, "years": {"type": "integer"}}},
        })

    def _update(self, properties):
        with self.captureOnCommitCallbacks(execute=True):
            return IndividualSchemaService(self.user).update({"properties": properties})

    def _stored_properties(self):
        config = ModuleConfiguration.objects.get(module='individual', layer='be', is_disabled_until__isnull=True)
        return json.loads(json.loads(config.config)['individual_schema'])['properties']

    def test_removing_a_field_a_label_uses_is_refused(self):
        result = self._update({"years": {"type": "integer"}, "email": {"type": "string"}})
        self.assertFalse(result.get('success', True))
        self.assertIn('licence_no (TEST_LABEL_A)', result.get('detail', ''))
        self.assertIn('licence_no', self._stored_properties())

    def test_retyping_a_field_a_label_uses_is_refused(self):
        result = self._update({
            "licence_no": {"type": "string"}, "years": {"type": "decimal"}, "email": {"type": "string"},
        })
        self.assertFalse(result.get('success', True))
        self.assertIn('years (TEST_LABEL_A)', result.get('detail', ''))
        self.assertEqual(self._stored_properties()['years']['type'], 'integer')

    def test_removing_an_unused_field_and_changing_options_is_allowed(self):
        result = self._update({
            "licence_no": {"type": "string", "uniqueness": True, "description": "Issued number"},
            "years": {"type": "integer"},
        })
        self.assertTrue(result.get('success'), result)
        self.assertNotIn('email', self._stored_properties())

    def test_a_deleted_label_still_holds_its_fields(self):
        create_individual_label(self.user.username, 'TEST_LABEL_B', {
            'json_schema': {"properties": {"email": {"type": "string"}}}, 'is_deleted': True,
        })
        result = self._update({"licence_no": {"type": "string"}, "years": {"type": "integer"}})
        self.assertFalse(result.get('success', True))
        self.assertIn('email (TEST_LABEL_B)', result.get('detail', ''))

    def test_every_registered_owner_is_asked(self):
        owners = [(IndividualLabel, 'code', 'json_schema'), (IndividualLabel, 'name', 'json_schema')]
        with patch('individual.schema_usage._owners', owners):
            result = self._update({"years": {"type": "integer"}, "email": {"type": "string"}})
        self.assertFalse(result.get('success', True))
        self.assertIn('TEST_LABEL_A', result.get('detail', ''))
        self.assertIn(IndividualLabel.objects.get(code='TEST_LABEL_A').name, result.get('detail', ''))

    def test_a_schema_stored_as_a_json_string_holds_its_fields(self):
        label = create_individual_label(self.user.username, 'TEST_LABEL_B')
        IndividualLabel.objects.filter(id=label.id).update(
            json_schema=json.dumps({"properties": {"email": {"type": "string"}}}))
        result = self._update({"licence_no": {"type": "string"}, "years": {"type": "integer"}})
        self.assertFalse(result.get('success', True))
        self.assertIn('email (TEST_LABEL_B)', result.get('detail', ''))

    def test_a_malformed_stored_schema_can_be_repaired(self):
        set_individual_schema(self, {"properties": {
            "licence_no": {"type": "string"}, "years": {"type": "integer"}, "broken": "not a definition",
        }})
        result = self._update({"licence_no": {"type": "string"}, "years": {"type": "integer"}})
        self.assertTrue(result.get('success'), result)
        self.assertNotIn('broken', self._stored_properties())

    def test_a_disabled_row_is_neither_read_nor_written(self):
        disabled_config = json.dumps({'individual_schema': json.dumps({"properties": {"old": {"type": "string"}}})})
        ModuleConfiguration.objects.filter(module='individual', layer='be').update(
            is_disabled_until=datetime.now() + timedelta(days=1), config=disabled_config)

        result = self._update({"licence_no": {"type": "string"}, "years": {"type": "integer"}})

        self.assertTrue(result.get('success'), result)
        self.assertEqual(
            ModuleConfiguration.objects.get(module='individual', layer='be', is_disabled_until__isnull=False).config,
            disabled_config)
        self.assertEqual(IndividualConfig.current_individual_schema(), {"properties": {
            "licence_no": {"type": "string"}, "years": {"type": "integer"},
        }})
