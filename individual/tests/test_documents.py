from unittest import skipUnless
from unittest.mock import patch

from django.apps import apps
from django.test import SimpleTestCase

from individual.apps import IndividualConfig
from individual.models import Individual


@skipUnless('opensearch_reports' in apps.app_configs, "opensearch_reports is not installed")
class IndividualDocumentPrivateLabelsTest(SimpleTestCase):
    def document(self, labels):
        from individual.documents import IndividualDocument

        individual = Individual(
            first_name='Ada', last_name='Lovelace', dob='1815-12-10',
            json_ext={'phone': '+100', 'address': {'city': 'London'}}, labels=labels,
        )
        return IndividualDocument().prepare(individual)

    @patch.object(IndividualConfig, 'individual_opensearch_private_labels', ['INSUREE'])
    def test_an_individual_with_a_private_label_is_indexed_without_personal_data(self):
        document = self.document(['INSUREE', 'BENEFICIARY'])
        self.assertEqual(set(document), {'id', 'labels', 'date_created'})
        self.assertEqual(document['labels'], ['INSUREE', 'BENEFICIARY'])

    @patch.object(IndividualConfig, 'individual_opensearch_private_labels', ['INSUREE'])
    def test_other_individuals_are_indexed_whole(self):
        document = self.document(['BENEFICIARY'])
        self.assertEqual(document['first_name'], 'Ada')
        self.assertEqual(document['json_ext']['address__city'], 'London')

    @patch.object(IndividualConfig, 'individual_opensearch_private_labels', [])
    def test_no_private_label_indexes_everyone_whole(self):
        self.assertEqual(self.document(['INSUREE'])['last_name'], 'Lovelace')

    def test_insurees_are_private_by_default(self):
        from individual.apps import DEFAULT_CONFIG

        self.assertEqual(DEFAULT_CONFIG['individual_opensearch_private_labels'], ['INSUREE'])

    @patch.object(IndividualConfig, 'individual_opensearch_private_labels', 'INSUREE')
    def test_a_single_label_stored_as_text_still_counts(self):
        self.assertEqual(set(self.document(['INSUREE'])), {'id', 'labels', 'date_created'})
