import logging

import numpy as np
import pandas as pd
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from im_export.views import check_user_rights
from individual.apps import IndividualConfig

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
    try:
        user = request.user
        import_file = request.FILES.get('file', None)
        workflow_name = request.POST.get('workflow_name', None)
        workflow_group = request.POST.get('workflow_group', None)

        if not (import_file and workflow_name and workflow_group):
            raise ValueError("invalid args")

        from individual.models import IndividualDataSourceUpload, IndividualDataSource
        upload = IndividualDataSourceUpload(source_name=import_file.name, source_type='beneficiary import')
        upload.save(username=user.login_name)

        def save_row(row):
            ds = IndividualDataSource(upload=upload, json_ext=row.to_dict(), validations={})
            ds.save(username=user.login_name)

        df = load_spreadsheet(import_file)
        df = df.replace({np.nan: None})
        df.apply(save_row, axis='columns')

        # trigger workflow
        from workflow.services import WorkflowService
        result = WorkflowService.get_workflows(workflow_name, workflow_group)
        workflows = result.get('data', {}).get('workflows', [])

        if not workflows:
            raise ValueError('workflow not found')

        from core.models import User
        workflows[0].run({
            'user_uuid': str(User.objects.get(username=user.login_name).id),
            'upload_uuid': str(upload.uuid),
        })

        return Response({'success': True, 'error': None}, status=201)

    except Exception as e:
        logger.error("Unexpected error while uploading individuals", exc_info=e)
        return Response({'success': False, 'error': str(e)}, status=500)
