"""The Python import pipeline: chunked validation, upload-wide deduplication, import."""
import json
import uuid
from unittest.mock import patch

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from core.models import Role
from core.test_helpers import create_right_only_user, create_test_interactive_user
from individual import import_pipeline
from individual.apps import IndividualConfig
from individual.models import (
    Individual,
    IndividualDataSource,
    IndividualDataSourceUpload,
    IndividualDataUploadRecords,
)
from individual.services import IndividualImportService
from individual.signals.on_validation_import_valid_items import IndividualItemsImportTaskCompletionEvent
from location.models import Location
from location.test_helpers import assign_user_districts, create_basic_test_locations
from tasks_management.models import Task
from workflow.services import WorkflowService

SCHEMA = json.dumps({"properties": {
    "national_id": {"type": "string", "uniqueness": True},
    "email": {"type": "string"},
}})
HEADER = "first_name,last_name,dob,location_name,location_code,national_id,email"


def _pipeline_workflow():
    return WorkflowService.get_workflows(
        import_pipeline.PIPELINE_IMPORT_WORKFLOW, import_pipeline.WORKFLOW_GROUP
    )["data"]["workflows"][0]


@override_settings(ROW_SECURITY=True)
class ImportPipelineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        create_basic_test_locations()
        cls.village_a = Location.objects.get(code="R1D1M1V1", validity_to__isnull=True)
        cls.village_b = Location.objects.get(code="R2D1M1V1", validity_to__isnull=True)
        admin_role = Role.objects.filter(is_system=64, *Role.filter_validity()).first()
        cls.admin = create_test_interactive_user(username="pipeadmin", roles=[admin_role.id])
        # A role grants no location: the importer works in village A's district.
        assign_user_districts(cls.admin, ["R1D1"])
        cls.district_user = create_right_only_user(
            "pipedistrict", ["gql_individual_create_perms"], district_codes=["R1D1"]
        )
        existing = Individual(first_name="Old", last_name="Timer", dob="1970-01-01",
                              json_ext={"national_id": "N-EXISTING"})
        existing.save(user=cls.admin)
        # Another upload waiting for review holds N-PENDING.
        other = IndividualDataSourceUpload(source_name="other.csv", source_type="individual import",
                                           status=IndividualDataSourceUpload.Status.WAITING_FOR_VERIFICATION)
        other.save(user=cls.admin)
        IndividualDataSource(upload=other, json_ext={"national_id": "N-PENDING"},
                             validations={"validation_errors": []}).save(user=cls.admin)

    def setUp(self):
        cache.clear()
        self._saved = {
            name: getattr(IndividualConfig, name)
            for name in ("individual_schema", "individual_import_pipeline_chunk_size",
                         "individual_import_pipeline_executor", "individual_import_duplicate_policy",
                         "individual_import_pipeline_dispatch")
        }
        IndividualConfig.individual_schema = SCHEMA
        IndividualConfig.individual_import_pipeline_chunk_size = 2
        IndividualConfig.individual_import_pipeline_executor = "inline"
        IndividualConfig.individual_import_duplicate_policy = "flag_all"
        import_pipeline._CONTEXTS.clear()

    def tearDown(self):
        for name, value in self._saved.items():
            setattr(IndividualConfig, name, value)
        import_pipeline._CONTEXTS.clear()

    def _row(self, first_name, national_id, village=None, dob="1990-05-01"):
        village = village or self.village_a
        return f"{first_name},Test,{dob},{village.name},{village.code},{national_id},"

    def _upload(self, rows, user=None):
        user = user or self.admin
        name = f"pipeline-{uuid.uuid4().hex}.csv"
        content = "\n".join([HEADER, *rows]).encode()
        default_storage.save(IndividualConfig.get_individual_upload_file_path(name), ContentFile(content))
        self.addCleanup(default_storage.delete, IndividualConfig.get_individual_upload_file_path(name))
        upload_file = SimpleUploadedFile(name, content, content_type="text/csv")
        result = IndividualImportService(user).import_individuals(upload_file, _pipeline_workflow(), None)
        return IndividualDataSourceUpload.objects.get(id=result["data"]["upload_uuid"])

    def _errors(self, upload):
        return {
            row.json_ext["first_name"]: sorted(e["field_name"] for e in row.validations["validation_errors"])
            for row in IndividualDataSource.objects.filter(upload=upload)
        }

    ROWS = property(lambda self: [
        self._row("Alice", "N-1"),                      # chunk 1
        self._row("Carol", "N-EXISTING"),
        self._row("Dan", "N-PENDING"),                  # chunk 2
        self._row("Bob", "N-1"),                        # duplicates Alice from another chunk
        self._row("Eve", "N-4").replace(",R1D1M1V1,", ",NOPE,"),  # chunk 3
        self._row("Frank", "N-5", dob="05/01/1990"),
        self._row("Gina", "N-6"),                       # chunk 4
    ])

    def test_validation_and_deduplication_across_chunks(self):
        upload = self._upload(self.ROWS)
        self.assertEqual(self._errors(upload), {
            "Alice": ["national_id"],
            "Bob": ["national_id"],
            "Carol": ["national_id"],
            "Dan": ["national_id"],
            "Eve": ["location_name"],
            "Frank": ["dob"],
            "Gina": [],
        })
        upload.refresh_from_db()
        self.assertEqual(upload.status, IndividualDataSourceUpload.Status.WAITING_FOR_VERIFICATION)
        self.assertEqual(upload.json_ext["pipeline"]["chunks_total"], 4)
        self.assertTrue(Task.objects.filter(json_ext__data_upload_id=str(upload.id)).exists())

    def test_keep_first_policy_keeps_the_first_copy(self):
        IndividualConfig.individual_import_duplicate_policy = "keep_first"
        errors = self._errors(self._upload(self.ROWS))
        self.assertEqual(errors["Alice"], [])
        self.assertEqual(errors["Bob"], ["national_id"])

    def test_location_outside_the_users_districts(self):
        errors = self._errors(self._upload(
            [self._row("Hana", "N-7"), self._row("Ivan", "N-8", village=self.village_b)],
            user=self.district_user,
        ))
        self.assertEqual(errors, {"Hana": [], "Ivan": ["location_name"]})

    @patch.object(IndividualImportService, "synchronize_data_for_reporting")
    def test_approval_imports_the_valid_rows(self, _sync):
        upload = self._upload(self.ROWS)
        record = IndividualDataUploadRecords.objects.get(data_upload=upload)
        self.assertEqual(
            import_pipeline.valid_items_workflow(record),
            f"{import_pipeline.WORKFLOW_GROUP}.{import_pipeline.PIPELINE_VALID_WORKFLOW}",
        )
        IndividualItemsImportTaskCompletionEvent(
            import_pipeline.valid_items_workflow(record), record, upload.id, self.admin
        ).run_workflow()

        gina = IndividualDataSource.objects.get(upload=upload, json_ext__first_name="Gina")
        self.assertIsNotNone(gina.individual_id)
        self.assertEqual(gina.individual.location_id, self.village_a.id)
        self.assertEqual(str(gina.individual.dob), "1990-05-01")
        self.assertEqual(
            IndividualDataSource.objects.filter(upload=upload, individual__isnull=False).count(), 1
        )
        upload.refresh_from_db()
        self.assertEqual(upload.status, IndividualDataSourceUpload.Status.PARTIAL_SUCCESS)

    def test_other_uploads_keep_the_configured_workflow(self):
        record = IndividualDataUploadRecords(workflow="Python Import Individuals")
        self.assertEqual(
            import_pipeline.valid_items_workflow(record),
            IndividualConfig.validation_import_valid_items_workflow,
        )

    def test_celery_executor_reduces_once_after_the_last_chunk(self):
        from individual.tasks import dispatch_task, finish_validation_task, stage_chunk_task

        IndividualConfig.individual_import_pipeline_executor = "celery"
        # Run the tasks here, as a worker would, without touching the global
        # celery configuration other tests depend on.
        for task in (dispatch_task, stage_chunk_task, finish_validation_task):
            patcher = patch.object(task, "delay", side_effect=lambda *a, _t=task, **k: _t.apply(args=a, kwargs=k))
            patcher.start()
            self.addCleanup(patcher.stop)

        # "worker": the request only queues the dispatch; "request": it reads the
        # file and queues the chunks itself. Same outcome either way.
        for dispatch in ("worker", "request"):
            with self.subTest(dispatch=dispatch):
                IndividualConfig.individual_import_pipeline_dispatch = dispatch
                upload = self._upload(self.ROWS)
                self.assertEqual(self._errors(upload)["Bob"], ["national_id"])
                upload.refresh_from_db()
                state = upload.json_ext["pipeline"]
                self.assertEqual((state["chunks_done"], state["chunks_total"], state["reduced"]), (4, 4, True))
                self.assertEqual(Task.objects.filter(json_ext__data_upload_id=str(upload.id)).count(), 1)
