"""Validation results are written in batches (one UPDATE over 100,000 rows never finished)."""
import uuid

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from core.test_helpers import create_test_interactive_user
from individual.models import IndividualDataSource, IndividualDataSourceUpload
from individual.services import IndividualImportService


class ValidationBatchingTest(TestCase):
    def test_validation_results_are_saved_in_batches(self):
        user = create_test_interactive_user(username="batchuser")
        upload = IndividualDataSourceUpload(source_name="batch.csv", source_type="individual import")
        upload.save(user=user)
        rows = [IndividualDataSource(id=uuid.uuid4(), upload=upload, json_ext={}, validations={},
                                     user_created=user, user_updated=user)
                for _ in range(2500)]
        IndividualDataSource.objects.bulk_create(rows)
        validated = [{"row": {"id": row.id}, "validations": {"dob": {"success": True}}} for row in rows]

        with CaptureQueriesContext(connection) as queries:
            IndividualImportService(user).save_validation_error_in_data_source_bulk(validated)

        updates = [q for q in queries.captured_queries if q["sql"].startswith("UPDATE")]
        self.assertEqual(len(updates), 3)
        self.assertEqual(
            IndividualDataSource.objects.filter(upload=upload, validations__validation_errors=[]).count(), 2500
        )
