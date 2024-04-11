import logging

from core.models import User
from individual.workflows.utils import SqlProcedurePythonWorkflow
from individual.services import IndividualImportService

logger = logging.getLogger(__name__)


def process_import_valid_individuals_workflow(user_uuid, upload_uuid, accepted=None):
    user = User.objects.get(id=user_uuid)
    service = SqlProcedurePythonWorkflow(upload_uuid, user_uuid, accepted)
    service.validate_dataframe_headers()
    if isinstance(accepted, list):
        service.execute(upload_sql_partial, [upload_uuid, user_uuid, accepted])
    else:
        service.execute(upload_sql, [upload_uuid, user_uuid])
    IndividualImportService(user).synchronize_data_for_reporting(upload_uuid)


upload_sql = """
DO $$
DECLARE
    current_upload_id UUID := %s::UUID;
    userUUID UUID := %s::UUID;
    failing_entries UUID[];
    json_schema jsonb;
    failing_entries_invalid_json UUID[];
    failing_entries_first_name UUID[];
    failing_entries_last_name UUID[];
    failing_entries_dob UUID[];
BEGIN
    -- Check if all required fields are present in the entries
    SELECT ARRAY_AGG("UUID") INTO failing_entries_first_name
    FROM individual_individualdatasource
    WHERE upload_id = current_upload_id AND individual_id IS NULL AND "isDeleted" = False AND NOT "Json_ext" ? 'first_name';
    SELECT ARRAY_AGG("UUID") INTO failing_entries_last_name
    FROM individual_individualdatasource
    WHERE upload_id = current_upload_id AND individual_id IS NULL AND "isDeleted" = False AND NOT "Json_ext" ? 'last_name';
    SELECT ARRAY_AGG("UUID") INTO failing_entries_dob
    FROM individual_individualdatasource
    WHERE upload_id = current_upload_id AND individual_id IS NULL AND "isDeleted" = False AND NOT "Json_ext" ? 'dob';
    SELECT ARRAY_AGG("UUID") INTO failing_entries_invalid_json
    FROM individual_individualdatasource
    WHERE upload_id = current_upload_id AND individual_id IS NULL AND "isDeleted" = False AND NOT validate_json_schema(json_schema, "Json_ext");
    -- If any entries do not meet the criteria or missing required fields, set the error message in the upload table and do not proceed further
    IF failing_entries_invalid_json IS NOT NULL OR failing_entries_first_name IS NOT NULL OR failing_entries_last_name IS NOT NULL OR failing_entries_dob IS NOT NULL THEN
        UPDATE individual_individualdatasourceupload
        SET error = coalesce(error, '{}'::jsonb) || jsonb_build_object('errors', jsonb_build_object(
                            'error', 'Invalid entries',
                            'timestamp', NOW()::text,
                            'upload_id', current_upload_id::text,
                            'failing_entries_first_name', failing_entries_first_name,
                            'failing_entries_last_name', failing_entries_last_name,
                            'failing_entries_dob', failing_entries_dob,
                            'failing_entries_invalid_json', failing_entries_invalid_json
                        ))
        WHERE "UUID" = current_upload_id;

        UPDATE individual_individualdatasourceupload SET status = 'FAIL' WHERE "UUID" = current_upload_id;
    ELSE
        -- If no invalid entries, then proceed with the data manipulation
        WITH new_entry AS (
            INSERT INTO individual_individual(
                "UUID", "isDeleted", version, "UserCreatedUUID", "UserUpdatedUUID",
                "Json_ext", first_name, last_name, dob
            )
            SELECT gen_random_uuid(), false, 1, userUUID, userUUID,
                   "Json_ext", "Json_ext"->>'first_name', "Json_ext" ->> 'last_name', to_date("Json_ext" ->> 'dob', 'YYYY-MM-DD')
            FROM individual_individualdatasource
            WHERE upload_id = current_upload_id AND individual_id IS NULL AND "isDeleted" = False AND validations ->> 'validation_errors' = '[]'
            RETURNING "UUID", "Json_ext"
        )
        UPDATE individual_individualdatasource
        SET individual_id = ne."UUID"
        FROM new_entry ne
        WHERE individual_individualdatasource.upload_id = current_upload_id
          AND individual_individualdatasource.individual_id IS NULL
          AND individual_individualdatasource."isDeleted" = False
          AND individual_individualdatasource."Json_ext" = ne."Json_ext"
          AND validations ->> 'validation_errors' = '[]';

        -- Change status to SUCCESS if no invalid items, change to PARTIAL_SUCCESS otherwise 
            UPDATE individual_individualdatasourceupload
            SET 
                status = CASE
                    WHEN (
                        SELECT count(*) 
                        FROM individual_individualdatasource
                        WHERE upload_id=current_upload_id
                            AND "isDeleted"=FALSE
                            AND validations ->> 'validation_errors' = '[]'
                    ) = (
                        SELECT count(*) 
                        FROM individual_individualdatasource
                        WHERE upload_id=current_upload_id
                            AND "isDeleted"=FALSE
                    ) THEN 'SUCCESS'
                    ELSE 'PARTIAL_SUCCESS'
                END,
                error = '{}'
            WHERE "UUID" = current_upload_id;
    END IF;
EXCEPTION WHEN OTHERS THEN
    UPDATE individual_individualdatasourceupload SET status = 'FAIL', error = jsonb_build_object(
        'error', SQLERRM,
        'timestamp', NOW()::text,
        'upload_id', current_upload_id::text
    )
    WHERE "UUID" = current_upload_id;
END $$;
"""

upload_sql_partial = """
DO $$
DECLARE
    current_upload_id UUID := %s::UUID;
    userUUID UUID := %s::UUID;
    accepted UUID[] := %s::UUID[]; -- Placeholder for the accepted UUIDs array, can be NULL
    failing_entries UUID[];
    failing_entries_first_name UUID[];
    failing_entries_last_name UUID[];
    failing_entries_dob UUID[];
    new_entry_results UUID[];
    new_entry_result UUID;
BEGIN
    -- Check if all required fields are present in the entries, with accepted filter applied if not NULL
    SELECT ARRAY_AGG("UUID") INTO failing_entries_first_name
    FROM individual_individualdatasource
    WHERE upload_id = current_upload_id AND individual_id IS NULL AND "isDeleted" = False AND NOT "Json_ext" ? 'first_name'
    AND (accepted IS NULL OR "UUID" = ANY(accepted));
    
    SELECT ARRAY_AGG("UUID") INTO failing_entries_last_name
    FROM individual_individualdatasource
    WHERE upload_id = current_upload_id AND individual_id IS NULL AND "isDeleted" = False AND NOT "Json_ext" ? 'last_name'
    AND (accepted IS NULL OR "UUID" = ANY(accepted));
    
    SELECT ARRAY_AGG("UUID") INTO failing_entries_dob
    FROM individual_individualdatasource
    WHERE upload_id = current_upload_id AND individual_id IS NULL AND "isDeleted" = False AND NOT "Json_ext" ? 'dob'
    AND (accepted IS NULL OR "UUID" = ANY(accepted));
    
    -- If any entries do not meet the criteria or missing required fields, set the error message in the upload table and do not proceed further
    IF failing_entries_first_name IS NOT NULL OR failing_entries_last_name IS NOT NULL OR failing_entries_dob IS NOT NULL THEN
        UPDATE individual_individualdatasourceupload
        SET error = coalesce(error, '{}'::jsonb) || jsonb_build_object('errors', jsonb_build_object(
                            'error', 'Invalid entries',
                            'timestamp', NOW()::text,
                            'upload_id', current_upload_id::text,
                            'failing_entries_first_name', failing_entries_first_name,
                            'failing_entries_last_name', failing_entries_last_name,
                            'failing_entries_dob', failing_entries_dob
                        ))
        WHERE "UUID" = current_upload_id;

        UPDATE individual_individualdatasourceupload SET status = 'FAIL' WHERE "UUID" = current_upload_id;
    ELSE
        -- If no invalid entries, then proceed with the data manipulation, considering the accepted filter
        WITH new_entry AS (
            INSERT INTO individual_individual(
                "UUID", "isDeleted", version, "UserCreatedUUID", "UserUpdatedUUID",
                "Json_ext", first_name, last_name, dob
            )
            SELECT gen_random_uuid(), false, 1, userUUID, userUUID,
                   "Json_ext", "Json_ext"->>'first_name', "Json_ext" ->> 'last_name', to_date("Json_ext" ->> 'dob', 'YYYY-MM-DD')
            FROM individual_individualdatasource
            WHERE upload_id = current_upload_id AND individual_id IS NULL AND "isDeleted" = False AND validations ->> 'validation_errors' = '[]'
            AND (accepted IS NULL OR "UUID" = ANY(accepted))
            RETURNING "UUID", "Json_ext"
        )
        UPDATE individual_individualdatasource
        SET individual_id = ne."UUID"
        FROM new_entry ne
        WHERE individual_individualdatasource.upload_id = current_upload_id
          AND individual_individualdatasource.individual_id IS NULL
          AND individual_individualdatasource."isDeleted" = False
          AND individual_individualdatasource."Json_ext" = ne."Json_ext"
          AND validations ->> 'validation_errors' = '[]'
          AND (accepted IS NULL OR individual_individualdatasource."UUID" = ANY(accepted));
    END IF;
EXCEPTION WHEN OTHERS THEN
    UPDATE individual_individualdatasourceupload SET status = 'FAIL', error = jsonb_build_object(
        'error', SQLERRM,
        'timestamp', NOW()::text,
        'upload_id', current_upload_id::text
    )
    WHERE "UUID" = current_upload_id;
END $$;
"""
