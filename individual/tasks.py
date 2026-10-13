"""Celery tasks of the individual import pipeline (executor "celery")."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="individual.import_pipeline.dispatch")
def dispatch_task(upload_id, user_id):
    from individual import import_pipeline

    import_pipeline.run_validation(upload_id, user_id, in_worker=True)


@shared_task(name="individual.import_pipeline.stage_chunk")
def stage_chunk_task(upload_id, user_id, records, first_row):
    from individual import import_pipeline

    try:
        import_pipeline.stage_chunk(upload_id, user_id, records, first_row)
    except Exception as exc:
        import_pipeline._fail(upload_id, exc)
        raise
    import_pipeline.chunk_done(upload_id, user_id)


@shared_task(name="individual.import_pipeline.finish_validation")
def finish_validation_task(upload_id, user_id):
    from individual import import_pipeline

    import_pipeline.finish_validation(upload_id, user_id)
