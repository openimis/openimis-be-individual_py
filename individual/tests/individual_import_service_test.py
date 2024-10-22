import csv
import json
import os
import pandas as pd
import uuid
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
from unittest.mock import MagicMock, patch


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

    @patch('individual.services.load_dataframe')
    @patch('individual.services.fetch_summary_of_broken_items')
    def test_validate_import_individuals_success(self, mock_fetch_summary, mock_load_dataframe):
        upload_id = uuid.uuid4()

        dataframe = pd.DataFrame({
            'id': [1, 2],
            'first_name': ['John', 'Jane'],
            'last_name': ['Doe', 'Smith'],
            'email': ['john@example.com', 'jane@example.com']
        })
        mock_load_dataframe.return_value = dataframe

        mock_invalid_items = {"invalid_items_count": 0}
        mock_fetch_summary.return_value = mock_invalid_items

        individual_sources = MagicMock()
        result = self.service.validate_import_individuals(upload_id, individual_sources)

        mock_load_dataframe.assert_called_once_with(individual_sources)

        # Assert that the result contains the validated dataframe and summary of invalid items
        self.assertEqual(result['success'], True)
        self.assertEqual(len(result['data']), 2)  # Two records were validated
        self.assertEqual(result['summary_invalid_items'], mock_invalid_items)

        # Check the validation logic on the dataframe
        validated_rows = result['data']
        for row in validated_rows:
            self.assertIn('validations', row)
            self.assertTrue(all(v.get('success', True) for v in row['validations'].values()))

    @patch('individual.services.IndividualConfig.individual_schema', json.dumps({
        "properties": {
            "email": {"type": "string", "uniqueness": True}
        }
    }))  # Mock schema for testing uniqueness
    @patch('individual.services.load_dataframe')
    @patch('individual.services.fetch_summary_of_broken_items')
    def test_validate_import_individuals_with_duplicate_emails(self, mock_fetch_summary, mock_load_dataframe):
        upload_id = uuid.uuid4()

        # Create a dataframe with duplicate emails to test uniqueness validation
        email = 'john@example.com'
        dataframe = pd.DataFrame({
            'id': [1, 2],
            'email': [email, email]
        })
        mock_load_dataframe.return_value = dataframe

        mock_invalid_items = {"invalid_items_count": 1}
        mock_fetch_summary.return_value = mock_invalid_items

        individual_sources = MagicMock()
        result = self.service.validate_import_individuals(upload_id, individual_sources)

        mock_load_dataframe.assert_called_once_with(individual_sources)

        # Assert that the result contains the validated dataframe and summary of invalid items
        self.assertEqual(result['success'], True)
        self.assertEqual(len(result['data']), 2)  # Two records were validated
        self.assertEqual(result['summary_invalid_items'], mock_invalid_items)

        # Check that the validation flagged the duplicate emails
        validated_rows = result['data']
        for row in validated_rows:
            if row['row']['email'] == email:
                self.assertIn('validations', row)
                email_validation = row['validations']['email_uniqueness']
                self.assertFalse(email_validation.get('success'))
                self.assertEqual(email_validation.get('field_name'), 'email')
                self.assertEqual(email_validation.get('note'), "'email' Field value 'john@example.com' is duplicated")
