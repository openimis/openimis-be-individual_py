import json
from core.models import ModuleConfiguration
from django.test import TestCase
from individual.apps import IndividualConfig
from individual.tests.test_helpers import reload_individual_config


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
