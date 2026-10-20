import uuid

from django.db import IntegrityError, connection, transaction
from django.test import TestCase

from core.test_helpers import LogInHelper
from individual.models import Individual
from individual.tests.test_helpers import create_individual, create_individual_label


class IndividualLabelModelTest(TestCase):
    user = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = LogInHelper().get_or_create_user_api()

    def test_labels_default_empty_and_overlap_filter(self):
        create_individual_label(self.user.username, 'TEST_LABEL_A')
        labelled = create_individual(self.user.username, payload_override={'labels': ['TEST_LABEL_A']})
        unlabelled = create_individual(self.user.username)

        self.assertEqual(unlabelled.labels, [])
        ids = set(Individual.objects.filter(labels__overlap=['TEST_LABEL_A']).values_list('id', flat=True))
        self.assertEqual(ids, {labelled.id})

    def test_labels_recorded_in_history(self):
        individual = create_individual(self.user.username, payload_override={'labels': ['TEST_LABEL_A']})
        self.assertEqual(individual.history.first().labels, ['TEST_LABEL_A'])

    def test_label_code_unique(self):
        create_individual_label(self.user.username, 'TEST_LABEL_A')
        with self.assertRaises(IntegrityError), transaction.atomic():
            create_individual_label(self.user.username, 'TEST_LABEL_A')

    def test_raw_insert_without_labels_defaults_to_empty(self):
        individual_id = uuid.uuid4()
        with connection.cursor() as cursor:
            cursor.execute(
                '''INSERT INTO individual_individual(
                    "UUID", "isDeleted", version, "UserCreatedUUID", "UserUpdatedUUID",
                    "Json_ext", first_name, last_name, dob)
                VALUES (%s, false, 1, %s, %s, '{}'::jsonb, 'Raw', 'Insert', '2000-01-01')''',
                [individual_id, self.user.id, self.user.id],
            )
        self.assertEqual(Individual.objects.get(id=individual_id).labels, [])
