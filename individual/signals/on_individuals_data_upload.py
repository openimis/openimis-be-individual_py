import logging

from individual.models import IndividualDataSourceUpload, IndividualDataUploadRecords

logger = logging.getLogger(__name__)


def on_individuals_data_upload(**kwargs):
    result = kwargs.get('result', None)
    if result:
        try:
            workflow = kwargs['data'][0][1].name
            upload = IndividualDataSourceUpload.objects \
                .get(id=result['data']['upload_uuid'])
            record = IndividualDataUploadRecords(
                data_upload=upload,
                workflow=workflow
            )
            record.save(username=kwargs['cls_'].user.username)
        except (KeyError, ValueError) as e:
            logger.error(
                "Failed to create benefit plan data upload registry."
                F"Result to provide `data.upload_uuid` (input: {result})"
            )
