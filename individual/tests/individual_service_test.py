import copy
from unittest.mock import patch

from django.test import TestCase

from individual.models import Individual
from individual.services import IndividualService
from individual.tests.data import (
    service_add_individual_payload,
    service_add_individual_payload_no_ext,
    service_update_individual_payload
)
from core.test_helpers import LogInHelper, create_test_interactive_user
from location.test_helpers import create_test_village, assign_user_districts
from opensearch_reports.service import BaseSyncDocument
from individual.tests.test_helpers import (
    create_individual,
    create_individual_label,
    create_group_with_individual,
    create_sp_role,
)
from social_protection.tests.test_helpers import create_benefit_plan


class IndividualServiceTest(TestCase):
    user = None
    service = None
    query_all = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.user = LogInHelper().get_or_create_user_api()
        cls.service = IndividualService(cls.user)
        cls.query_all = Individual.objects.filter(is_deleted=False)

    def test_add_individual(self):
        result = self.service.create(service_add_individual_payload)
        self.assertTrue(result.get('success', False), result.get('detail', "No details provided"))
        uuid = result.get('data', {}).get('uuid', None)
        query = self.query_all.filter(uuid=uuid)
        self.assertEqual(query.count(), 1)
        json_ext = query.first().json_ext
        self.assertEqual(json_ext['key'], 'value')
        self.assertEqual(json_ext['key2'], 'value2')

    def test_add_individual_no_ext(self):
        result = self.service.create(service_add_individual_payload_no_ext)
        self.assertTrue(result.get('success', False), result.get('detail', "No details provided"))
        uuid = result.get('data', {}).get('uuid')
        query = self.query_all.filter(uuid=uuid)
        self.assertEqual(query.count(), 1)

    def test_add_individual_with_labels_dedupes(self):
        create_individual_label(self.user.username, 'TEST_LABEL_A')
        payload = {**service_add_individual_payload_no_ext, 'labels': ['TEST_LABEL_A', 'TEST_LABEL_A']}
        result = self.service.create(payload)
        self.assertTrue(result.get('success', False), result.get('detail', "No details provided"))
        uuid = result.get('data', {}).get('uuid')
        self.assertEqual(self.query_all.get(uuid=uuid).labels, ['TEST_LABEL_A'])

    def test_add_individual_unknown_label_rejected(self):
        result = self.service.create({**service_add_individual_payload_no_ext, 'labels': ['TEST_LABEL_NOPE']})
        self.assertFalse(result.get('success', True))
        self.assertIn('TEST_LABEL_NOPE', result.get('detail', ''))

    def test_update_individual_labels_replaces_keeps_and_clears(self):
        create_individual_label(self.user.username, 'TEST_LABEL_A')
        create_individual_label(self.user.username, 'TEST_LABEL_B')
        result = self.service.create({**service_add_individual_payload_no_ext, 'labels': ['TEST_LABEL_A']})
        uuid = result.get('data', {}).get('uuid')

        def update(**extra):
            payload = {**copy.deepcopy(service_update_individual_payload), 'id': uuid, **extra}
            result = self.service.update(payload)
            self.assertTrue(result.get('success', False), result.get('detail', "No details provided"))
            return self.query_all.get(uuid=uuid).labels

        self.assertEqual(update(labels=['TEST_LABEL_B']), ['TEST_LABEL_B'])
        self.assertEqual(update(), ['TEST_LABEL_B'])
        self.assertEqual(update(labels=None), ['TEST_LABEL_B'])
        self.assertEqual(update(labels=[]), [])

    @patch.object(BaseSyncDocument, 'update')
    def test_update_labels_bulk_add_remove_with_history(self, mock_document_update):
        create_individual_label(self.user.username, 'TEST_LABEL_A')
        create_individual_label(self.user.username, 'TEST_LABEL_B')
        first = create_individual(self.user.username, payload_override={'labels': ['TEST_LABEL_A']})
        second = create_individual(self.user.username)
        history_before = first.history.count()

        with self.captureOnCommitCallbacks(execute=True):
            result = self.service.update_labels(
                [first.id, second.id], add=['TEST_LABEL_B'], remove=['TEST_LABEL_A'])

        self.assertTrue(result.get('success', False), result.get('detail', "No details provided"))
        self.assertEqual(result['data']['updated'], 2)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.labels, ['TEST_LABEL_B'])
        self.assertEqual(second.labels, ['TEST_LABEL_B'])
        self.assertEqual(first.version, 2)
        self.assertEqual(first.history.count(), history_before + 1)
        self.assertEqual(first.history.first().labels, ['TEST_LABEL_B'])
        synced, action = mock_document_update.call_args.args
        self.assertEqual(action, 'index')
        self.assertEqual({i.id for i in synced}, {first.id, second.id})

    @patch.object(BaseSyncDocument, 'update')
    def test_update_labels_keeps_existing_order_and_skips_present(self, mock_document_update):
        create_individual_label(self.user.username, 'TEST_LABEL_A')
        create_individual_label(self.user.username, 'TEST_LABEL_B')
        individual = create_individual(self.user.username, payload_override={'labels': ['TEST_LABEL_B']})

        result = self.service.update_labels([individual.id], add=['TEST_LABEL_A', 'TEST_LABEL_B'])

        self.assertTrue(result.get('success', False), result.get('detail', "No details provided"))
        individual.refresh_from_db()
        self.assertEqual(individual.labels, ['TEST_LABEL_B', 'TEST_LABEL_A'])

    @patch.object(BaseSyncDocument, 'update')
    def test_update_labels_skips_rows_that_would_not_change(self, mock_document_update):
        create_individual_label(self.user.username, 'TEST_LABEL_A')
        individual = create_individual(self.user.username, payload_override={'labels': ['TEST_LABEL_A']})
        history_before = individual.history.count()

        for kwargs in ({'add': ['TEST_LABEL_A']}, {'remove': ['TEST_LABEL_B']}, {}):
            if 'remove' in kwargs:
                create_individual_label(self.user.username, 'TEST_LABEL_B')
            result = self.service.update_labels([individual.id], **kwargs)
            self.assertTrue(result.get('success', False), result.get('detail', "No details provided"))
            self.assertEqual(result['data']['updated'], 0, kwargs)

        individual.refresh_from_db()
        self.assertEqual(individual.version, 1)
        self.assertEqual(individual.history.count(), history_before)

    def test_update_labels_survives_search_index_failure(self):
        create_individual_label(self.user.username, 'TEST_LABEL_A')
        individual = create_individual(self.user.username)

        with patch.object(BaseSyncDocument, 'update', side_effect=RuntimeError('broker down')), \
                self.captureOnCommitCallbacks(execute=True):
            result = self.service.update_labels([individual.id], add=['TEST_LABEL_A'])

        self.assertTrue(result.get('success', False), result.get('detail', "No details provided"))
        individual.refresh_from_db()
        self.assertEqual(individual.labels, ['TEST_LABEL_A'])

    def test_update_labels_empty_ids(self):
        create_individual_label(self.user.username, 'TEST_LABEL_A')
        result = self.service.update_labels([], add=['TEST_LABEL_A'])
        self.assertTrue(result.get('success', False), result.get('detail', "No details provided"))
        self.assertEqual(result['data']['updated'], 0)

    def test_update_labels_rejects_unknown_and_overlapping_codes(self):
        create_individual_label(self.user.username, 'TEST_LABEL_A')
        individual = create_individual(self.user.username)

        result = self.service.update_labels([individual.id], add=['TEST_LABEL_NOPE'])
        self.assertFalse(result.get('success', True))
        self.assertIn('TEST_LABEL_NOPE', result.get('detail', ''))

        result = self.service.update_labels([individual.id], add=['TEST_LABEL_A'], remove=['TEST_LABEL_A'])
        self.assertFalse(result.get('success', True))

        individual.refresh_from_db()
        self.assertEqual(individual.labels, [])

    @patch.object(BaseSyncDocument, 'update')
    def test_update_labels_respects_row_security(self, mock_document_update):
        create_individual_label(self.user.username, 'TEST_LABEL_A')
        village_a = create_test_village({'name': 'Label Village A', 'code': 'LVA'})
        village_b = create_test_village({'name': 'Label Village B', 'code': 'LVB'})
        individual = create_individual(self.user.username, payload_override={'location': village_a})
        district_b_user = create_test_interactive_user(
            username="labelDistrictBUser", roles=[create_sp_role(self.user).id])
        assign_user_districts(district_b_user, [village_b.parent.parent.code])

        result = IndividualService(district_b_user).update_labels([individual.id], add=['TEST_LABEL_A'])

        self.assertTrue(result.get('success', False), result.get('detail', "No details provided"))
        self.assertEqual(result['data']['updated'], 0)
        individual.refresh_from_db()
        self.assertEqual(individual.labels, [])

    def test_update_individual(self):
        result = self.service.create(service_add_individual_payload)
        self.assertTrue(result.get('success', False), result.get('detail', "No details provided"))
        uuid = result.get('data', {}).get('uuid')
        update_payload = copy.deepcopy(service_update_individual_payload)
        update_payload['id'] = uuid
        result = self.service.update(update_payload)
        self.assertTrue(result.get('success', False), result.get('detail', "No details provided"))
        query = self.query_all.filter(uuid=uuid)
        self.assertEqual(query.count(), 1)
        self.assertEqual(query.first().first_name, update_payload.get('first_name'))
        json_ext = query.first().json_ext
        self.assertEqual(json_ext['key'], 'value')
        self.assertEqual(json_ext['key2'], 'value2 updated')

    def test_delete_individual(self):
        result = self.service.create(service_add_individual_payload)
        self.assertTrue(result.get('success', False), result.get('detail', "No details provided"))
        uuid = result.get('data', {}).get('uuid')
        delete_payload = {'id': uuid}
        result = self.service.delete(delete_payload)
        self.assertTrue(result.get('success', False), result.get('detail', "No details provided"))
        query = self.query_all.filter(uuid=uuid)
        self.assertEqual(query.count(), 0)

    def test_select_individuals_to_benefit_plan(self):
        custom_filters = []
        status = "ACTIVE"
        benefit_plan = create_benefit_plan(self.user.username, payload_override={
            'type': "INDIVIDUAL"
        })

        self.individual_a, self.group_a, self.group_individual_a = create_group_with_individual(
            self.user.username
        )

        self.individual_a_no_group = create_individual(
            self.user.username,
        )

        summary = self.service.select_individuals_to_benefit_plan(
            custom_filters=custom_filters,
            benefit_plan_id=str(benefit_plan.id),
            status=status,
            user=self.user
        )

        self.assertNotEqual(summary, None)
        self.assertEqual(summary['individual_query_with_filters'].count(), 1)
        self.assertEqual(summary['individuals_assigned_to_selected_programme'].count(), 0)
        self.assertEqual(summary['individuals_not_assigned_to_selected_programme'].count(), 1)

        # Delete the group and groupindividual
        self.group_a.delete(user=self.user)
        self.group_individual_a.delete(user=self.user)

        # Verify the individual is now counted in the enrollment summary
        summary = self.service.select_individuals_to_benefit_plan(
            custom_filters=custom_filters,
            benefit_plan_id=str(benefit_plan.id),
            status=status,
            user=self.user
        )

        self.assertNotEqual(summary, None)
        self.assertEqual(summary['individual_query_with_filters'].count(), 2)
        self.assertEqual(summary['individuals_assigned_to_selected_programme'].count(), 0)
        self.assertEqual(summary['individuals_not_assigned_to_selected_programme'].count(), 2)
