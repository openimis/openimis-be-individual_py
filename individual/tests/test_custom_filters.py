import os
import json
from collections import namedtuple
from unittest.mock import patch

from django.test import TestCase

from core.models import ModuleConfiguration
from core.test_helpers import LogInHelper
from individual.custom_filters import IndividualCustomFilterWizard
from individual.tests.test_helpers import (
    IndividualGQLTestCase,
    create_individual_label,
    reload_individual_config,
)


class IndividualCustomFilterQueryTest(IndividualGQLTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.test_config_path = os.path.join(
            os.path.dirname(__file__), 'fixtures', 'individual_config.json'
        )

    def test_individual_custom_filter_query(self):
        # First set the individual schema to be empty. An empty *config* is not
        # enough: it is merged with DEFAULT_CONFIG, whose individual_schema
        # ships properties of its own, and those would surface as filters here.
        empty_schema_config = json.dumps({'individual_schema': json.dumps({})})
        config = ModuleConfiguration.objects.filter(module='individual', layer='be').first()
        self.addCleanup(reload_individual_config, config.config if config else '{}')
        if config is None:
            config = ModuleConfiguration(
                module='individual', layer='be', config=empty_schema_config)
        else:
            config.config = empty_schema_config
        # The module reload is queued with transaction.on_commit, which never
        # runs inside a TestCase's rolled-back transaction.
        with self.captureOnCommitCallbacks(execute=True):
            config.save()

        query_str = '''
            {
              customFilters(
                moduleName: "individual",
                objectTypeName: "Individual",
                additionalParams: "{\\"type\\":\\"INDIVIDUAL\\"}"
              ){
                type
                code
                possibleFilters {
                    field
                    filter
                    type
                }
              }
            }
        '''

        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"}
        )
        self.assertResponseNoErrors(response)
        content = json.loads(response.content)
        possible_filters = content['data']['customFilters']['possibleFilters']
        self.assertEqual(possible_filters, [])

        # Then update individual config to with the fixture config
        with open(self.test_config_path, 'rb') as test_file:
            config.config = test_file.read()
        with self.captureOnCommitCallbacks(execute=True):
            config.save()

        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"}
        )
        self.assertResponseNoErrors(response)
        content = json.loads(response.content)
        possible_filters = content['data']['customFilters']['possibleFilters']
        self.assertTrue(len(possible_filters), 3)
        expected_possible_filters = [
            {'field': 'poor', 'filter': ['exact'], 'type': 'boolean'},
            {'field': 'educated_level', 'filter': ['iexact', 'istartswith', 'icontains'], 'type': 'string'},
            {'field': 'number_of_children', 'filter': ['exact', 'lt', 'lte', 'gt', 'gte'], 'type': 'integer'},
        ]
        for f in expected_possible_filters:
            self.assertTrue(f in possible_filters, f'expected to find {f} in {possible_filters}')


@patch('individual.apps.IndividualConfig.individual_schema',
       json.dumps({"properties": {"email": {"type": "string"}}}))
class IndividualCustomFilterLabelSchemaTest(TestCase):
    definition = namedtuple('definition', ['field', 'filter', 'type'])

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = LogInHelper().get_or_create_user_api()

    def _fields(self, additional_params):
        definitions = IndividualCustomFilterWizard().load_definition(
            self.definition, additional_params=additional_params)
        return [d.field for d in definitions]

    def test_label_schema_drives_definitions(self):
        create_individual_label(self.user.username, 'TEST_LABEL_A', {
            'json_schema': {"properties": {"licence_no": {"type": "string"}}},
        })
        self.assertEqual(self._fields({'label': 'TEST_LABEL_A'}), ['licence_no'])

    def test_falls_back_to_global_schema(self):
        create_individual_label(self.user.username, 'TEST_LABEL_A')
        self.assertEqual(self._fields({}), ['email'])
        self.assertEqual(self._fields({'label': 'TEST_LABEL_A'}), ['email'])
        self.assertEqual(self._fields({'label': 'TEST_LABEL_NOPE'}), ['email'])
