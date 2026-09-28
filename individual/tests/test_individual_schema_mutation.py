import json

from core.models import ModuleConfiguration
from django.utils.translation import gettext as _

from individual.apps import IndividualConfig
from individual.tests.test_helpers import IndividualGQLTestCase, reload_individual_config


class IndividualSchemaMutationTest(IndividualGQLTestCase):
    new_schema = {"properties": {
        "email": {"type": "string", "uniqueness": True},
        "income": {"type": "decimal", "description": "Monthly, in local currency"},
    }}

    def setUp(self):
        super().setUp()
        config = ModuleConfiguration.objects.filter(module='individual', layer='be').first()
        self.addCleanup(reload_individual_config, config.config if config else '{}')
        self.original_schema = IndividualConfig.individual_schema

    @staticmethod
    def _mutation(schema):
        # JSON string escaping is valid GraphQL string escaping.
        return f'''
            mutation {{
              updateIndividualSchema(input: {{ schema: {json.dumps(json.dumps(schema))} }}) {{
                internalId
              }}
            }}
        '''

    def _run(self, schema, token):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.query(self._mutation(schema), headers={"HTTP_AUTHORIZATION": f"Bearer {token}"})
        return json.loads(response.content)['data']['updateIndividualSchema']['internalId']

    def _stored_schema(self):
        config = ModuleConfiguration.objects.filter(module='individual', layer='be').first()
        return json.loads(json.loads(config.config)['individual_schema']) if config else None

    def _global_schema(self):
        response = self.query(
            '{ globalSchema { schema } }', headers={"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"})
        return json.loads(json.loads(response.content)['data']['globalSchema']['schema'])

    def test_anonymous_is_refused(self):
        self.assert_unauthenticated(self.query(self._mutation(self.new_schema)))
        self.assertEqual(IndividualConfig.individual_schema, self.original_schema)

    def test_user_without_the_right_is_refused(self):
        self.assert_mutation_error(self._run(self.new_schema, self.med_enroll_officer_token), _('unauthorized'))
        self.assertNotEqual(self._stored_schema(), self.new_schema)
        self.assertEqual(IndividualConfig.individual_schema, self.original_schema)

    def test_invalid_schema_is_refused_and_nothing_is_stored(self):
        schema = {"properties": {"email": {"type": "string", "uniqueness": False}}}
        self.assert_mutation_error(self._run(schema, self.admin_token), 'email')
        self.assertNotEqual(self._stored_schema(), schema)
        self.assertEqual(IndividualConfig.individual_schema, self.original_schema)

    def test_schema_is_saved_and_takes_effect(self):
        self.assert_mutation_success(self._run(self.new_schema, self.admin_token))
        self.assertEqual(self._stored_schema(), self.new_schema)
        self.assertEqual(json.loads(IndividualConfig.individual_schema), self.new_schema)
        self.assertEqual(self._global_schema(), self.new_schema)

    def test_other_configuration_keys_are_kept(self):
        config = ModuleConfiguration.objects.filter(module='individual', layer='be').first() \
            or ModuleConfiguration(module='individual', layer='be', version='1')
        config.config = json.dumps({'individual_accept_enrolment': 'custom.accept', 'individual_schema': '{}'})
        with self.captureOnCommitCallbacks(execute=True):
            config.save()

        self.assert_mutation_success(self._run(self.new_schema, self.admin_token))

        stored = json.loads(ModuleConfiguration.objects.get(module='individual', layer='be').config)
        self.assertEqual(stored['individual_accept_enrolment'], 'custom.accept')
        self.assertEqual(json.loads(stored['individual_schema']), self.new_schema)
