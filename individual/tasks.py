import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def task_import_individual_workflow(user_uuid, upload_uuid):
    from individual.workflows.base_individual_upload import import_individual_workflow
    return import_individual_workflow(user_uuid, upload_uuid)


@shared_task
def task_import_individual_workflow_valid(user_uuid, upload_uuid, percentage_of_invalid_items):
    from individual.workflows.base_individual_upload import import_individual_workflow_valid
    return import_individual_workflow_valid(user_uuid, upload_uuid, percentage_of_invalid_items)
