import json
from collections import namedtuple
from unittest.mock import patch

from core.models import ModuleConfiguration
from django.test import TestCase
from individual.apps import IndividualConfig
from individual.custom_filters import IndividualCustomFilterWizard
from individual.tests.test_helpers import reload_individual_config, set_individual_schema
from individual.views import get_global_schema_fields


class ModuleConfigTest(TestCase):

    def test_config_reloading(self):
        # First set the individual config to be empty
        config = ModuleConfiguration.objects.filter(module='individual', layer='be').first()
        self.addCleanup(reload_individual_config, config.config if config else '{}')
        if config is None:
            config = ModuleConfiguration(module='individual', layer='be', config='{}')
        else:
            config.config = '{}'
        # The module reload is queued with transaction.on_commit, which never
        # runs inside a TestCase's rolled-back transaction.
        with self.captureOnCommitCallbacks(execute=True):
            config.save()

        self.assertTrue(IndividualConfig.enable_maker_checker_for_individual_upload)
        self.assertTrue(IndividualConfig.enable_maker_checker_for_individual_update)

        # Update config should trigger a reload
        updated_config = {
            "enable_maker_checker_for_individual_upload": False,
            "enable_maker_checker_for_individual_update": False,
        }
        config.config = json.dumps(updated_config)
        with self.captureOnCommitCallbacks(execute=True):
            config.save()

        self.assertFalse(IndividualConfig.enable_maker_checker_for_individual_upload)
        self.assertFalse(IndividualConfig.enable_maker_checker_for_individual_update)


class SchemaSavedByAnotherProcessTest(TestCase):
    definition = namedtuple('definition', ['field', 'filter', 'type'])

    def setUp(self):
        super().setUp()
        set_individual_schema(self, {"properties": {"email": {"type": "string"}}})

    def _save_from_another_process(self, schema):
        # The row changes, but no reload runs in this process.
        config = ModuleConfiguration.objects.get(module='individual', layer='be')
        stored = json.loads(config.config)
        stored['individual_schema'] = json.dumps(schema)
        ModuleConfiguration.objects.filter(id=config.id).update(config=json.dumps(stored))

    def test_readers_follow_the_stored_schema(self):
        schema = {"properties": {"poor": {"type": "boolean"}}}
        self._save_from_another_process(schema)

        self.assertEqual(IndividualConfig.current_individual_schema(), schema)
        self.assertEqual(json.loads(IndividualConfig.individual_schema), schema)
        definitions = IndividualCustomFilterWizard().load_definition(self.definition, additional_params={})
        self.assertEqual([d.field for d in definitions], ['poor'])
        self.assertIn('poor', get_global_schema_fields())
        self.assertNotIn('email', get_global_schema_fields())

    def test_an_unchanged_row_keeps_the_loaded_configuration(self):
        overridden = json.dumps({"properties": {"income": {"type": "decimal"}}})
        with patch('individual.apps.IndividualConfig.individual_schema', overridden), \
                patch('individual.apps.IndividualConfig.enable_maker_checker_for_individual_update', 'marker'):
            self.assertEqual(IndividualConfig.current_individual_schema(), json.loads(overridden))
            self.assertEqual(IndividualConfig.enable_maker_checker_for_individual_update, 'marker')

    def test_reading_the_schema_without_a_stored_row_logs_nothing(self):
        ModuleConfiguration.objects.filter(module='individual', layer='be').delete()
        IndividualConfig.current_individual_schema()
        with self.assertNoLogs('core.models.base', level='INFO'):
            IndividualConfig.current_individual_schema()
            IndividualConfig.current_individual_schema()
