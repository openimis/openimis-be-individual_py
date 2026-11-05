"""Uploads and their rows are visible to their uploader, reviewers, and through imported individuals (audit H01)."""
from django.core.cache import cache
from django.test import TestCase, override_settings

from core.test_helpers import create_right_only_user
from individual.models import (
    Individual,
    IndividualDataSource,
    IndividualDataSourceUpload,
    IndividualDataUploadRecords,
)
from location.models import Location
from location.test_helpers import create_basic_test_locations
from tasks_management.models import Task, TaskExecutor, TaskGroup

SEARCH = ["gql_individual_search_perms"]


@override_settings(ROW_SECURITY=True)
class UploadRowSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_basic_test_locations()
        village = Location.objects.get(code="R1D1M1V1", validity_to__isnull=True)
        cls.uploader = create_right_only_user("h01uploader", SEARCH)
        cls.outsider = create_right_only_user("h01outsider", SEARCH)
        cls.reviewer = create_right_only_user("h01reviewer", SEARCH)
        cls.district_user = create_right_only_user("h01district", SEARCH, district_codes=["R1D1"])

        cls.upload = IndividualDataSourceUpload(source_name="h01.csv", source_type="individual import")
        cls.upload.save(user=cls.uploader)
        cls.pending = IndividualDataSource(upload=cls.upload, json_ext={"first_name": "Pending"},
                                           validations={"validation_errors": []})
        cls.pending.save(user=cls.uploader)
        individual = Individual(first_name="Imported", last_name="Row", dob="1990-01-01", location=village)
        individual.save(user=cls.uploader)
        cls.imported = IndividualDataSource(upload=cls.upload, individual=individual, json_ext={})
        cls.imported.save(user=cls.uploader)

        record = IndividualDataUploadRecords(data_upload=cls.upload, workflow="Python Import Individuals")
        record.save(user=cls.uploader)
        group = TaskGroup(code="h01_reviewers", completion_policy="ANY")
        group.save(user=cls.uploader)
        TaskExecutor(task_group=group, user=cls.reviewer).save(user=cls.uploader)
        Task(entity=record, task_group=group, status=Task.Status.ACCEPTED, source="import_valid_items",
             business_event="individual_validation.import_valid_items",
             executor_action_event="APPROVE", business_status={}, json_ext={}).save(user=cls.uploader)

    def setUp(self):
        cache.clear()

    def _uploads(self, user):
        return IndividualDataSourceUpload.get_queryset(
            IndividualDataSourceUpload.objects.filter(id=self.upload.id), user
        ).exists()

    def _rows(self, user):
        return set(IndividualDataSource.get_queryset(
            IndividualDataSource.objects.filter(upload=self.upload), user
        ).values_list("id", flat=True))

    def _records(self, user):
        return IndividualDataUploadRecords.get_queryset(
            IndividualDataUploadRecords.objects.filter(data_upload=self.upload), user
        ).exists()

    def test_uploader_sees_upload_and_pending_rows(self):
        self.assertTrue(self._uploads(self.uploader))
        self.assertIn(self.pending.id, self._rows(self.uploader))
        self.assertTrue(self._records(self.uploader))

    def test_reviewer_sees_upload_and_pending_rows(self):
        self.assertTrue(self._uploads(self.reviewer))
        self.assertIn(self.pending.id, self._rows(self.reviewer))

    def test_imported_individual_shows_its_upload_but_not_pending_rows(self):
        self.assertTrue(self._uploads(self.district_user))
        self.assertEqual(self._rows(self.district_user), {self.imported.id})

    def test_outsider_sees_nothing(self):
        self.assertFalse(self._uploads(self.outsider))
        self.assertEqual(self._rows(self.outsider), set())
        self.assertFalse(self._records(self.outsider))

    def test_reviewer_matches_a_task_whatever_the_case_of_its_entity_id(self):
        # SQL Server casts a uniqueidentifier to uppercase text while Task.entity_id
        # holds str(uuid), lowercase: the task must match its record as a UUID,
        # whatever case either side is written in.
        task = Task.objects.get(task_group__code="h01_reviewers")
        Task.objects.filter(id=task.id).update(entity_id=task.entity_id.upper())
        self.assertTrue(self._uploads(self.reviewer))
        self.assertIn(self.pending.id, self._rows(self.reviewer))
