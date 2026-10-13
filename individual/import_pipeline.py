"""Python import pipeline for individuals: chunked, parallel, with upload-wide deduplication.

Opt-in. It runs when an upload picks the ``Python Pipeline Import Individuals``
workflow; the SQL workflows stay the default and are untouched.

Stages:

1. **Stage and validate** (map, one task per chunk, parallel). Parse a chunk of
   the file, validate each row (required fields, validation calculations,
   location), and insert the rows with their result. The village is resolved
   once, here, and kept with the row.
2. **Deduplicate** (reduce, once). Set-based comparison of the ``uniqueness``
   fields over the whole upload, the other uploads still pending, and the
   existing individuals. Chunks only produce rows; comparing happens after all
   of them are in, so a duplicate split across two chunks is still found.
3. **Review**. The usual maker-checker task, or an immediate import when
   maker-checker is off.
4. **Import** (map, one task per chunk). Create the individuals of the valid,
   accepted rows. Each row is linked to the individual created from it by id.

Executors (``individual_import_pipeline_executor``):

* ``inline``: in the calling process, chunk by chunk.
* ``process``: a local process pool of ``individual_import_pipeline_workers``.
* ``celery``: one celery task per chunk for stage 1; the last chunk to finish
  triggers stage 2. Stage 4 then runs inline: it is followed by the group step
  of the same approval, which needs the individuals to exist.
"""
import datetime
import json
import logging
import multiprocessing
import uuid
from collections import deque
from concurrent.futures import ProcessPoolExecutor

import pandas as pd
from django.conf import settings
from django.core.files.storage import default_storage
from django.db import connections, transaction
from django.db.models import Count, Exists, OuterRef
from django.db.models.fields.json import KeyTextTransform

from core.models import User
from individual.apps import IndividualConfig
from individual.models import (
    Individual,
    IndividualDataSource,
    IndividualDataSourceUpload,
)

logger = logging.getLogger(__name__)

WORKFLOW_GROUP = "individual"
PIPELINE_IMPORT_WORKFLOW = "Python Pipeline Import Individuals"
PIPELINE_VALID_WORKFLOW = "Python Pipeline Valid Upload Individuals"

CSV_CONTENT_TYPE = "text/csv"
SUPPORTED_CONTENT_TYPES = (
    CSV_CONTENT_TYPE,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/vnd.oasis.opendocument.spreadsheet",
)
PENDING_STATUSES = (
    IndividualDataSourceUpload.Status.TRIGGERED,
    IndividualDataSourceUpload.Status.IN_PROGRESS,
    IndividualDataSourceUpload.Status.WAITING_FOR_VERIFICATION,
)


def is_pipeline_workflow(workflow_name):
    return workflow_name == PIPELINE_IMPORT_WORKFLOW


def valid_items_workflow(upload_record):
    """The workflow that imports an upload's valid rows once they are approved."""
    if upload_record is not None and is_pipeline_workflow(upload_record.workflow):
        return f"{WORKFLOW_GROUP}.{PIPELINE_VALID_WORKFLOW}"
    return IndividualConfig.validation_import_valid_items_workflow


# --- configuration -----------------------------------------------------------

def _executor():
    return IndividualConfig.individual_import_pipeline_executor or "inline"


def _chunk_size():
    return int(IndividualConfig.individual_import_pipeline_chunk_size or 5000)


def _workers():
    return int(IndividualConfig.individual_import_pipeline_workers or 4)


def _dispatch_in_worker():
    return (IndividualConfig.individual_import_pipeline_dispatch or "worker") == "worker"


def _schema_properties():
    return json.loads(IndividualConfig.individual_schema).get("properties", {})


# --- pipeline state on the upload ------------------------------------------

def _update_state(upload_id, **changes):
    """Merge ``changes`` into the upload's pipeline state, atomically, and return it.

    A queryset update, not ``save()``: a state change is bookkeeping and must
    not add a history row per chunk.
    """
    with transaction.atomic():
        upload = IndividualDataSourceUpload.objects.select_for_update().get(id=upload_id)
        json_ext = upload.json_ext or {}
        state = {**json_ext.get("pipeline", {}), **changes}
        IndividualDataSourceUpload.objects.filter(id=upload_id).update(
            json_ext={**json_ext, "pipeline": state}
        )
        return state


def _set_status(upload_id, status, error=None):
    values = {"status": status}
    if error is not None:
        values["error"] = error
    IndividualDataSourceUpload.objects.filter(id=upload_id).update(**values)


def _fail(upload_id, exc):
    logger.error("Individual import pipeline failed for upload %s", upload_id, exc_info=exc)
    _set_status(
        upload_id,
        IndividualDataSourceUpload.Status.FAIL,
        {"pipeline": str(exc), "timestamp": datetime.datetime.now().isoformat()},
    )


# --- stage 0: register the upload (in the request) -------------------------

def register_upload(user, import_file):
    """Create the upload entry pointing at the stored file, without reading it.

    The request only records where the file is; parsing and validating happen
    in the pipeline, so a large file does not hold the request.
    """
    if import_file.content_type not in SUPPORTED_CONTENT_TYPES:
        raise ValueError("Unsupported content type: {}".format(import_file.content_type))
    upload = IndividualDataSourceUpload(
        source_name=import_file.name,
        source_type="individual import",
        json_ext={"pipeline": {
            "file": IndividualConfig.get_individual_upload_file_path(import_file.name),
            "content_type": import_file.content_type,
        }},
    )
    upload.save(username=user.login_name)
    return upload


# --- reading the file --------------------------------------------------------

def _iter_chunks(path, content_type, chunk_size):
    with default_storage.open(path, "rb") as handle:
        if content_type == CSV_CONTENT_TYPE:
            for chunk in pd.read_csv(handle, dtype={"location_code": str}, chunksize=chunk_size):
                yield chunk
        else:
            frame = pd.read_excel(handle, dtype={"location_code": str})
            for start in range(0, len(frame), chunk_size):
                yield frame.iloc[start:start + chunk_size]


def _records(chunk):
    if "Unnamed: 0" in chunk.columns:
        chunk = chunk.drop("Unnamed: 0", axis=1)
    # Same conversion as the SQL path's per-row `row.to_json()`, once per chunk.
    return json.loads(chunk.to_json(orient="records"))


def check_headers(columns):
    from individual.workflows.utils import check_dataframe_headers

    # "id" is a base field the SQL workflows add to every row before this check;
    # here rows get their id when staged.
    check_dataframe_headers(set(columns) | {"id"}, json.loads(IndividualConfig.individual_schema))


# --- row validation (stage 1, per worker) -----------------------------------

class _ValidationContext:
    """What every row of an upload is checked against, loaded once per process."""

    def __init__(self, user):
        from location.models import Location, LocationManager

        self.user = user
        self.properties = _schema_properties()
        villages = {}
        ambiguous = set()
        rows = Location.objects.filter(type="V", *Location.filter_validity()).values_list(
            "id", "name", "code", "parent_id", "parent__parent_id", "parent__parent__parent_id"
        )
        for village_id, name, code, *ancestors in rows:
            key = (name, code)
            if key in villages:
                ambiguous.add(key)
            villages[key] = (village_id, *ancestors)
        self.villages = villages
        self.ambiguous = ambiguous
        unrestricted = (
            not settings.ROW_SECURITY or user.is_superuser or getattr(user, "is_imis_admin", False)
        )
        # A user is granted locations at some level (officer villages, user
        # districts): a village is allowed when it, or one of its ancestors, is.
        self.allowed = None if unrestricted else set(LocationManager().get_allowed_ids(user))


_CONTEXTS = {}


def _context(user_id):
    context = _CONTEXTS.get(user_id)
    if context is None:
        context = _CONTEXTS[user_id] = _ValidationContext(User.objects.get(id=user_id))
    return context


def _blank(value):
    return value is None or (isinstance(value, str) and value.strip() == "")


def _validate_record(record, context):
    """The row's validation errors, and the village it resolves to."""
    from individual.services import IndividualImportService

    errors = []
    for field in ("first_name", "last_name"):
        if _blank(record.get(field)):
            errors.append({"field_name": field, "note": f"'{field}' is required"})
    try:
        datetime.datetime.strptime(str(record.get("dob")), "%Y-%m-%d")
    except ValueError:
        errors.append({"field_name": "dob", "note": "'dob' must be a date formatted YYYY-MM-DD"})

    for field, properties in context.properties.items():
        if "validationCalculation" in properties and field in record:
            result = IndividualImportService._handle_validation_calculation(record, field, properties)
            if not result.get("success", False):
                errors.append({"field_name": result.get("field_name", field), "note": result.get("note")})

    location_id = None
    name, code = record.get("location_name"), record.get("location_code")
    if not (_blank(name) and _blank(code)):
        key = (name, code)
        if key not in context.villages:
            note = (f"Location with name '{name}' and code '{code}' is not valid. Please check the "
                    f"spelling against the list of locations in the system.")
        elif key in context.ambiguous:
            note = (f"Location with name '{name}' and code '{code}' is ambiguous, because there are "
                    f"more than one location with this name and code found in the system.")
        elif context.allowed is not None and not context.allowed.intersection(context.villages[key]):
            note = (f"Location with name '{name}' and code '{code}' is outside the current user's "
                    f"location permissions.")
        else:
            note = None
            location_id = context.villages[key][0]
        if note:
            errors.append({"field_name": "location_name", "note": note})
    return errors, location_id


def stage_chunk(upload_id, user_id, records, first_row):
    """Stage 1 for one chunk: validate its rows and insert them with the result."""
    context = _context(user_id)
    rows = []
    for offset, record in enumerate(records):
        errors, location_id = _validate_record(record, context)
        rows.append(IndividualDataSource(
            id=uuid.uuid4(),
            upload_id=upload_id,
            json_ext=record,
            validations={
                "validation_errors": errors,
                "row": first_row + offset,
                "location_id": location_id,
            },
            user_created_id=user_id,
            user_updated_id=user_id,
        ))
    IndividualDataSource.objects.bulk_create(rows, batch_size=1000)
    return len(rows)


# --- executors ----------------------------------------------------------------

def _process_pool():
    # Forked workers must not share the parent's database connection.
    connections.close_all()
    return ProcessPoolExecutor(max_workers=_workers(), mp_context=multiprocessing.get_context("fork"))


def _run_chunks(function, argument_list):
    """Run ``function(*arguments)`` for each item, inline or on the process pool."""
    if _executor() == "process":
        with _process_pool() as pool:
            futures = [pool.submit(function, *arguments) for arguments in argument_list]
            return [future.result() for future in futures]
    return [function(*arguments) for arguments in argument_list]


# --- stage 1 driver ----------------------------------------------------------

def run_validation(upload_id, user_id, in_worker=False):
    """Read the file in chunks and stage them; then deduplicate and open the review.

    With the celery executor and ``individual_import_pipeline_dispatch`` set to
    "worker", the request only queues the dispatch: reading the file and
    queueing its chunks happen in a worker too, so the request returns at once.
    """
    upload = IndividualDataSourceUpload.objects.get(id=upload_id)
    state = (upload.json_ext or {}).get("pipeline", {})
    _set_status(upload_id, IndividualDataSourceUpload.Status.IN_PROGRESS)
    try:
        if _executor() == "celery" and not in_worker and _dispatch_in_worker():
            from individual.tasks import dispatch_task

            dispatch_task.delay(str(upload_id), str(user_id))
            return
        chunks = _iter_chunks(state["file"], state["content_type"], _chunk_size())
        if _executor() == "celery":
            _dispatch_celery(upload_id, user_id, chunks)
            return
        rows, count = _stage_all(upload_id, user_id, chunks)
        _update_state(upload_id, rows=rows, chunks_total=count)
        finish_validation(upload_id, user_id)
    except Exception as exc:
        _fail(upload_id, exc)
        raise


def _stage_all(upload_id, user_id, chunks):
    """Stage every chunk as it is read, never holding more than a few in memory."""
    pool = _process_pool() if _executor() == "process" else None
    in_flight = deque()
    first_row = 0
    count = 0
    try:
        for index, chunk in enumerate(chunks):
            if index == 0:
                check_headers(chunk.columns)
            arguments = (upload_id, user_id, _records(chunk), first_row)
            first_row += len(chunk)
            count += 1
            if pool is None:
                stage_chunk(*arguments)
                continue
            in_flight.append(pool.submit(stage_chunk, *arguments))
            while len(in_flight) >= 2 * _workers():
                in_flight.popleft().result()
        while in_flight:
            in_flight.popleft().result()
    finally:
        if pool is not None:
            pool.shutdown(cancel_futures=True)
    if not count:
        raise ValueError("Import file is empty")
    return first_row, count


def _dispatch_celery(upload_id, user_id, chunks):
    from individual.tasks import stage_chunk_task

    first_row = 0
    count = 0
    for index, chunk in enumerate(chunks):
        if index == 0:
            check_headers(chunk.columns)
        stage_chunk_task.delay(str(upload_id), str(user_id), _records(chunk), first_row)
        first_row += len(chunk)
        count += 1
    if not count:
        raise ValueError("Import file is empty")
    _update_state(upload_id, rows=first_row, chunks_total=count)
    chunk_done(upload_id, user_id, increment=0)


def chunk_done(upload_id, user_id, increment=1):
    """Count a finished chunk; whoever sees the last one triggers the reduce, once."""
    with transaction.atomic():
        upload = IndividualDataSourceUpload.objects.select_for_update().get(id=upload_id)
        state = (upload.json_ext or {}).get("pipeline", {})
        done = state.get("chunks_done", 0) + increment
        total = state.get("chunks_total")
        ready = total is not None and done >= total and not state.get("reduced")
        _update_state(upload_id, chunks_done=done, reduced=state.get("reduced") or ready)
    if ready:
        from individual.tasks import finish_validation_task

        finish_validation_task.delay(str(upload_id), str(user_id))


# --- stage 2: deduplicate -----------------------------------------------------

def _unique_fields():
    return [field for field, props in _schema_properties().items() if "uniqueness" in props]


def find_duplicates(upload_id, policy=None):
    """Rows of the upload duplicating another row, keyed by row id, with their notes."""
    policy = policy or IndividualConfig.individual_import_duplicate_policy or "flag_all"
    duplicates = {}

    def flag(row_id, field, note):
        duplicates.setdefault(row_id, []).append({"field_name": field, "note": note})

    for field in _unique_fields():
        value = KeyTextTransform(field, "json_ext")
        rows = (
            IndividualDataSource.objects.filter(upload_id=upload_id, is_deleted=False)
            .annotate(value=value)
            .exclude(value__isnull=True)
            .exclude(value="")
        )

        # Within the upload: one comparison over all chunks.
        repeated = (
            rows.values("value").annotate(n=Count("id")).filter(n__gt=1).values("value")
        )
        groups = {}
        for row_id, field_value, validations in (
            rows.filter(value__in=repeated).values_list("id", "value", "validations")
        ):
            groups.setdefault(field_value, []).append(((validations or {}).get("row", 0), row_id))
        for field_value, members in groups.items():
            members.sort()
            flagged = members[1:] if policy == "keep_first" else members
            for __, row_id in flagged:
                flag(row_id, field, f"'{field}' Field value '{field_value}' is duplicated in this upload")

        # Against the individuals already registered.
        existing = (
            Individual.objects.filter(is_deleted=False)
            .annotate(existing_value=KeyTextTransform(field, "json_ext"))
            .filter(existing_value=OuterRef("value"))
        )
        for row_id, field_value in rows.filter(Exists(existing)).values_list("id", "value"):
            flag(row_id, field, f"'{field}' Field value '{field_value}' already belongs to an individual")

        # Against the other uploads still waiting to be imported.
        pending = (
            IndividualDataSource.objects.filter(
                is_deleted=False,
                individual__isnull=True,
                validations__validation_errors=[],
                upload__status__in=PENDING_STATUSES,
            )
            .exclude(upload_id=upload_id)
            .annotate(pending_value=KeyTextTransform(field, "json_ext"))
            .filter(pending_value=OuterRef("value"))
        )
        for row_id, field_value in rows.filter(Exists(pending)).values_list("id", "value"):
            flag(row_id, field, f"'{field}' Field value '{field_value}' is pending in another upload")
    return duplicates


def _record_duplicates(duplicates):
    ids = list(duplicates)
    for start in range(0, len(ids), 5000):
        batch = list(IndividualDataSource.objects.filter(id__in=ids[start:start + 5000]))
        for row in batch:
            validations = row.validations or {}
            validations["validation_errors"] = validations.get("validation_errors", []) + duplicates[row.id]
            row.validations = validations
        IndividualDataSource.objects.bulk_update(batch, ["validations"], batch_size=1000)


def finish_validation(upload_id, user_id):
    """Stage 2 and 3: deduplicate over the whole upload, then open the review."""
    from individual.services import IndividualImportService

    try:
        duplicates = find_duplicates(upload_id)
        _record_duplicates(duplicates)
        _update_state(upload_id, duplicates=len(duplicates))
        user = User.objects.get(id=user_id)
        IndividualImportService(user).create_task_with_importing_valid_items(upload_id)
    except Exception as exc:
        _fail(upload_id, exc)
        raise


# --- stage 4: import the approved rows ---------------------------------------

def import_chunk(user_id, row_ids):
    """Create the individuals of one chunk of valid rows, linked by row id."""
    with transaction.atomic():
        rows = list(
            IndividualDataSource.objects.select_for_update()
            .filter(id__in=row_ids, individual__isnull=True)
        )
        individuals = []
        for row in rows:
            data = row.json_ext or {}
            individual = Individual(
                id=uuid.uuid4(),
                first_name=data.get("first_name"),
                last_name=data.get("last_name"),
                dob=datetime.datetime.strptime(str(data.get("dob")), "%Y-%m-%d").date(),
                location_id=(row.validations or {}).get("location_id"),
                json_ext=data,
                user_created_id=user_id,
                user_updated_id=user_id,
            )
            individuals.append(individual)
            row.individual_id = individual.id
        Individual.objects.bulk_create(individuals, batch_size=1000)
        IndividualDataSource.objects.bulk_update(rows, ["individual"], batch_size=1000)
    return len(individuals)


def run_import(upload_id, user_id, accepted=None):
    """Import the valid rows of the upload (only ``accepted`` ones when given)."""
    rows = IndividualDataSource.objects.filter(
        upload_id=upload_id,
        individual__isnull=True,
        is_deleted=False,
        validations__validation_errors=[],
    )
    if isinstance(accepted, list):
        rows = rows.filter(id__in=accepted)
    ids = list(rows.values_list("id", flat=True))
    size = _chunk_size()
    argument_list = [(str(user_id), ids[start:start + size]) for start in range(0, len(ids), size)]
    if _executor() == "process":
        _run_chunks(import_chunk, argument_list)
    else:
        # Celery included: the group step of the same approval runs right after
        # and needs the individuals to exist.
        for arguments in argument_list:
            import_chunk(*arguments)
    _finish_import(upload_id)
    return len(ids)


def _finish_import(upload_id):
    rows = IndividualDataSource.objects.filter(upload_id=upload_id, is_deleted=False)
    total = rows.count()
    valid = rows.filter(validations__validation_errors=[]).count()
    if valid == total:
        _set_status(upload_id, IndividualDataSourceUpload.Status.SUCCESS, {})
    else:
        _set_status(upload_id, IndividualDataSourceUpload.Status.PARTIAL_SUCCESS, {
            "error": "Partial success due to some invalid entries",
            "timestamp": datetime.datetime.now().isoformat(),
            "upload_id": str(upload_id),
            "total_valid_entries": valid,
            "total_entries": total,
        })


# --- workflow entry points ---------------------------------------------------

def process_pipeline_import_individuals_workflow(user_uuid, upload_uuid):
    run_validation(upload_uuid, user_uuid)


def process_pipeline_valid_individuals_workflow(user_uuid, upload_uuid, accepted=None):
    from individual.services import IndividualImportService

    imported = run_import(upload_uuid, user_uuid, accepted)
    try:
        IndividualImportService(User.objects.get(id=user_uuid)).synchronize_data_for_reporting(upload_uuid)
    except Exception as exc:
        # Reporting is a copy; an unreachable index must not fail an import that succeeded.
        logger.warning("Reporting synchronisation failed for upload %s", upload_uuid, exc_info=exc)
    return {"imported": imported}
