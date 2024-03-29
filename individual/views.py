import logging

import numpy as np
import pandas as pd
from django.db.models import Q
from django.http import HttpResponse, StreamingHttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from core.utils import DefaultStorageFileHandler
from im_export.views import check_user_rights
from individual.apps import IndividualConfig
from individual.models import IndividualDataSource
from individual.services import IndividualImportService

from django.core.files.uploadedfile import InMemoryUploadedFile

logger = logging.getLogger(__name__)

_import_loaders = {
    # .csv
    'text/csv': lambda f, **kwargs: pd.read_csv(f, **kwargs),
    # .xlsx
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': lambda f, **kwargs: pd.read_excel(f, **kwargs),
    # .xls
    'application/vnd.ms-excel': lambda f, **kwargs: pd.read_excel(f, **kwargs),
    # .ods
    'application/vnd.oasis.opendocument.spreadsheet': lambda f, **kwargs: pd.read_excel(f, **kwargs),
}


def load_spreadsheet(file: InMemoryUploadedFile, **kwargs) -> pd.DataFrame:
    content_type = file.content_type
    if content_type not in _import_loaders:
        raise ValueError("Unsupported content type: {}".format(content_type))

    return _import_loaders[content_type](file, **kwargs)


@api_view(["POST"])
@permission_classes([check_user_rights(IndividualConfig.gql_individual_create_perms, )])
def import_individuals(request):
    import_file = None
    try:
        user = request.user
        import_file = request.FILES.get('file', None)
        workflow_name = request.POST.get('workflow_name', None)
        workflow_group = request.POST.get('workflow_group', None)

        if not (import_file and workflow_name and workflow_group):
            raise ValueError("invalid args")

        _handle_file_upload(import_file)

        from workflow.services import WorkflowService
        result = WorkflowService.get_workflows(workflow_name, workflow_group)
        workflows = result.get('data', {}).get('workflows', [])

        if not workflows:
            raise ValueError('workflow not found')

        result = IndividualImportService(user).import_individuals(import_file, workflows[0])
        if not result.get('success'):
            raise ValueError('{}: {}'.format(result.get("message"), result.get("details")))

        return Response(result)
    except ValueError as e:
        if import_file:
            _remove_file(import_file)
        logger.error("Error while uploading individuals", exc_info=e)
        return Response({'success': False, 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except FileExistsError as e:
        logger.error("Error while saving file", exc_info=e)
        return Response({'success': False, 'error': str(e)}, status=status.HTTP_409_CONFLICT)
    except Exception as e:
        logger.error("Unexpected error while uploading individuals", exc_info=e)
        return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["GET"])
@permission_classes([check_user_rights(IndividualConfig.gql_individual_search_perms, )])
def download_invalid_items(request):
    try:
        upload_id = request.query_params.get('upload_id')

        invalid_items = IndividualDataSource.objects.filter(
            Q(is_deleted=False) &
            Q(upload_id=upload_id) &
            ~Q(validations__validation_errors=[])
        )

        data_from_source = []
        for invalid_item in invalid_items:
            json_ext = invalid_item.json_ext
            invalid_item.json_ext["id"] = invalid_item.id
            invalid_item.json_ext["error"] = invalid_item.validations
            data_from_source.append(json_ext)

        recreated_df = pd.DataFrame(data_from_source)

        # Function to stream the DataFrame content as CSV
        def stream_csv():
            output = recreated_df.to_csv(index=False)
            yield output.encode('utf-8')

        # Create a streaming response with the CSV content
        response = StreamingHttpResponse(
            stream_csv(), content_type='text/csv'
        )
        response['Content-Disposition'] = 'attachment; filename="individuals_invalid_items.csv"'
        return response

    except ValueError as exc:
        # Handle errors gracefully
        logger.error("Error while fetching data", exc_info=exc)
        return Response({'success': False, 'error': str(exc)}, status=400)
    except Exception as exc:
        logger.error("Unexpected error", exc_info=exc)
        return Response({'success': False, 'error': str(exc)}, status=500)


@api_view(["GET"])
@permission_classes([check_user_rights(IndividualConfig.gql_individual_search_perms, )])
def download_individual_upload(request):
    try:
        filename = request.query_params.get('filename')
        target_file_path = IndividualConfig.get_individual_upload_file_path(filename)
        file_handler = DefaultStorageFileHandler(target_file_path)
        return file_handler.get_file_response_csv(filename)

    except ValueError as exc:
        logger.error("Error while fetching data", exc_info=exc)
        return Response({'success': False, 'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except FileNotFoundError as exc:
        logger.error("Error while getting file", exc_info=exc)
        return Response({'success': False, 'error': str(exc)}, status=status.HTTP_404_NOT_FOUND)
    except Exception as exc:
        logger.error("Unexpected error", exc_info=exc)
        return Response({'success': False, 'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _handle_file_upload(file):
    try:
        target_file_path = IndividualConfig.get_individual_upload_file_path(file.name)
        file_handler = DefaultStorageFileHandler(target_file_path)
        file_handler.save_file(file)
    except FileExistsError as exc:
        raise exc


def _remove_file(file):
    target_file_path = IndividualConfig.get_individual_upload_file_path(file.name)
    file_handler = DefaultStorageFileHandler(target_file_path)
    file_handler.remove_file()
