import csv
import os
from core.test_helpers import LogInHelper
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from individual.services import IndividualImportService
from individual.models import (
    IndividualDataSource,
    IndividualDataSourceUpload,
    IndividualDataUploadRecords,
)
from individual.tests.test_helpers import generate_random_string
from unittest.mock import MagicMock


def count_csv_records(file_path):
    with open(file_path, mode='r', encoding='utf-8') as file:
        reader = csv.reader(file)
        valid_rows = list(
            row for row in reader 
            if any(cell.strip() for cell in row)  # Do not count blank lines
        )
        return len(valid_rows) - 1  # Exclude the header row


class IndividualImportServiceTest(TestCase):
    user = None
    service = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.user = LogInHelper().get_or_create_user_api()
        cls.service = IndividualImportService(cls.user)

        cls.csv_file_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'individual_upload.csv')
        # SimpleUploadedFile requires a bytes-like object so use 'rb' instead of 'r'
        with open(cls.csv_file_path, 'rb') as f:
            cls.csv_content = f.read()


    def test_import_individuals(self):
        uploaded_csv_name = f"{generate_random_string(20)}.csv"
        csv_file = SimpleUploadedFile(
            uploaded_csv_name,
            self.csv_content,
            content_type="text/csv"
        )

        mock_workflow = self._create_mock_workflow()

        result = self.service.import_individuals(csv_file, mock_workflow, "group_code")
        self.assertEqual(result['success'], True)

        # Check that an IndividualDataSourceUpload object was saved in the database
        upload = IndividualDataSourceUpload.objects.get(source_name=uploaded_csv_name)
        self.assertIsNotNone(upload)
        self.assertEqual(upload.source_name, uploaded_csv_name)
        self.assertEqual(upload.source_type, "individual import")
        self.assertEqual(upload.status, IndividualDataSourceUpload.Status.TRIGGERED)

        self.assertEqual(result['data']['upload_uuid'], upload.uuid)

        # Check that an IndividualDataUploadRecords object was saved in the database
        data_upload_record = IndividualDataUploadRecords.objects.get(data_upload=upload)
        self.assertIsNotNone(data_upload_record)
        self.assertEqual(data_upload_record.workflow, mock_workflow.name)
        self.assertEqual(data_upload_record.json_ext['group_aggregation_column'], "group_code")

        # Check that an IndividualDataSource objects saved in the database
        individual_data_sources = IndividualDataSource.objects.filter(upload=upload)
        num_records = count_csv_records(self.csv_file_path)
        self.assertEqual(individual_data_sources.count(), num_records)

        # Check that workflow is triggered
        mock_workflow.run.assert_called_once_with({
            'user_uuid': str(self.user.id),
            'upload_uuid': str(upload.uuid),
        })


    def _create_mock_workflow(self):
        mock_workflow = MagicMock()
        mock_workflow.name = 'Test Workflow'
        return mock_workflow

