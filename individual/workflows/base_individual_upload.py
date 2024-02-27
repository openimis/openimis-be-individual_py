import json
import logging

from django.db import connection
from django.db import ProgrammingError

from core.models import User
from individual.apps import IndividualConfig
from individual.models import (
    IndividualDataSource,
    IndividualDataUploadRecords,
    IndividualDataSourceUpload
)
from individual.services import IndividualImportService
from individual.utils import load_dataframe
from individual.tasks import (
    task_import_individual_workflow,
    task_import_individual_workflow_valid
)
from workflow.exceptions import PythonWorkflowHandlerException

logger = logging.getLogger(__name__)


def validate_dataframe_headers(df, schema, upload_id, user):
    """
    Validates if DataFrame headers:
    1. Are included in the JSON schema properties.
    2. Include 'first_name', 'last_name', and 'dob'.
    """
    df_headers = set(df.columns)
    schema_properties = set(schema.get('properties', {}).keys())
    required_headers = {'first_name', 'last_name', 'dob', 'id'}

    errors = []
    if not (df_headers-required_headers).issubset(schema_properties):
        invalid_headers = df_headers - schema_properties - required_headers
        errors.append(
            F"Uploaded individuals contains invalid columns: {invalid_headers}"
        )

    for field in required_headers:
        if field not in df_headers:
            errors.append(
                F"Uploaded individuals missing essential header: {field}"
            )

    if errors:
        update_individual_upload_data_source(upload_id, user, {'file_structure': "\n".join(errors)})
        raise PythonWorkflowHandlerException("\n".join(errors))


def import_individual_workflow(user_uuid, upload_uuid):
    # Call the records validation service directly with the provided arguments
    user = User.objects.get(id=user_uuid)
    import_service = IndividualImportService(user)
    schema = json.loads(IndividualConfig.individual_schema)
    df = load_dataframe(IndividualDataSource.objects.filter(upload_id=upload_uuid))
    # Valid headers are necessary conditions, breaking whole update. If file is invalid then
    # upload is aborted because no record can be uploaded.
    validate_dataframe_headers(df, schema, upload_uuid, user)

    validation_response = import_service.validate_import_individuals(
        upload_id=upload_uuid,
        individual_sources=IndividualDataSource.objects.filter(upload_id=upload_uuid),
    )

    try:
        if validation_response['summary_invalid_items'] or IndividualConfig.enable_maker_checker_logic_import:
            # If some records were not validated, call the task creation service
            import_service.create_task_with_importing_valid_items(upload_uuid)
        else:
            # All records are fine, execute SQL logic
            execute_sql_logic(upload_uuid, user_uuid)
            import_service.synchronize_data_for_reporting(upload_uuid)
    except ProgrammingError as e:
        # The exception on procedure execution is handled by the procedure itself.
        update_individual_upload_data_source(upload_uuid, user, {'programming_error': str(e)})
        logger.log(logging.WARNING, F'Error during individual upload workflow, details:\n{str(e)}')
        return
    except Exception as e:
        update_individual_upload_data_source(upload_uuid, user, {'exception': str(e)})
        raise PythonWorkflowHandlerException(str(e))


def update_individual_upload_data_source(upload_id, user, error):
    upload = IndividualDataSourceUpload.objects.get(id=upload_id)
    upload.status = IndividualDataSourceUpload.Status.FAIL
    upload.error = error
    upload.save(username=user.login_name)


def import_individual_workflow_valid(user_uuid, upload_uuid, percentage_of_invalid_items):
    user = User.objects.get(id=user_uuid)
    import_service = IndividualImportService(user)
    execute_sql_logic_valid_items(upload_uuid, user_uuid, percentage_of_invalid_items)
    import_service.synchronize_data_for_reporting(upload_uuid)


def execute_sql_logic(upload_uuid, user_uuid):
    with connection.cursor() as cursor:
        current_upload_id = upload_uuid
        userUUID = user_uuid
        # The SQL logic here needs to be carefully translated or executed directly
        # The provided SQL is complex and may require breaking down into multiple steps or ORM operations
        cursor.execute("""
DO $$
 DECLARE
            current_upload_id UUID := %s::UUID;
            userUUID UUID := %s::UUID;
            failing_entries UUID[];
            failing_entries_invalid_json UUID[];
            failing_entries_first_name UUID[];
            failing_entries_last_name UUID[];
            failing_entries_dob UUID[];
            BEGIN
    -- Check if all required fields are present in the entries
    SELECT ARRAY_AGG("UUID") INTO failing_entries_first_name
    FROM individual_individualdatasource
    WHERE upload_id=current_upload_id and individual_id is null and "isDeleted"=False AND NOT "Json_ext" ? 'first_name';
    SELECT ARRAY_AGG("UUID") INTO failing_entries_last_name
    FROM individual_individualdatasource
    WHERE upload_id=current_upload_id and individual_id is null and "isDeleted"=False AND NOT "Json_ext" ? 'last_name';
    SELECT ARRAY_AGG("UUID") INTO failing_entries_dob
    FROM individual_individualdatasource
    WHERE upload_id=current_upload_id and individual_id is null and "isDeleted"=False AND NOT "Json_ext" ? 'dob';  
    
    -- If any entries do not meet the criteria or missing required fields, set the error message in the upload table and do not proceed further
    IF failing_entries_invalid_json IS NOT NULL or failing_entries_first_name IS NOT NULL OR failing_entries_last_name IS NOT NULL OR failing_entries_dob IS NOT NULL THEN
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
       update individual_individualdatasourceupload set status='FAIL' where "UUID" = current_upload_id;
    -- If no invalid entries, then proceed with the data manipulation
    ELSE
        BEGIN
          WITH new_entry AS (
            INSERT INTO individual_individual(
            "UUID", "isDeleted", version, "UserCreatedUUID", "UserUpdatedUUID",
            "Json_ext", first_name, last_name, dob
            )
            SELECT gen_random_uuid(), false, 1, userUUID, userUUID,
            "Json_ext", "Json_ext"->>'first_name', "Json_ext" ->> 'last_name', to_date("Json_ext" ->> 'dob', 'YYYY-MM-DD')
            FROM individual_individualdatasource
            WHERE upload_id=current_upload_id and individual_id is null and "isDeleted"=False
            RETURNING "UUID", "Json_ext"  -- also return the Json_ext
          )
          UPDATE individual_individualdatasource
          SET individual_id = new_entry."UUID"
          FROM new_entry
          WHERE upload_id=current_upload_id
            and individual_id is null
            and "isDeleted"=False
            and individual_individualdatasource."Json_ext" = new_entry."Json_ext";  -- match on Json_ext
            update individual_individualdatasourceupload set status='SUCCESS', error='{}' where "UUID" = current_upload_id;
            EXCEPTION
            WHEN OTHERS then
            update individual_individualdatasourceupload set status='FAIL' where "UUID" = current_upload_id;
                UPDATE individual_individualdatasourceupload
                SET error = coalesce(error, '{}'::jsonb) || jsonb_build_object('errors', jsonb_build_object(
                                    'error', SQLERRM,
                                    'timestamp', NOW()::text,
                                    'upload_id', current_upload_id::text
                                ))
                WHERE "UUID" = current_upload_id;
        END;
    END IF;
END $$;
        """, [current_upload_id, userUUID])
        # Process the cursor results or handle exceptions


def execute_sql_logic_valid_items(upload_uuid, user_uuid, percentage_invalid_items):
    with connection.cursor() as cursor:
        current_upload_id = upload_uuid
        userUUID = user_uuid
        percentage_invalid_items = percentage_invalid_items
        print(percentage_invalid_items)
        # The SQL logic here needs to be carefully translated or executed directly
        # The provided SQL is complex and may require breaking down into multiple steps or ORM operations
        cursor.execute("""
DO $$
        declare
            current_upload_id UUID := %s::UUID;
            userUUID UUID := %s::UUID;
            percentage_invalid_items Decimal(5,2) := %s::Decimal(5,2);
            failing_entries UUID[];
            failing_entries_invalid_json UUID[];
            failing_entries_first_name UUID[];
            failing_entries_last_name UUID[];
            failing_entries_dob UUID[];
        BEGIN

            -- Check if all required fields are present in the entries
            SELECT ARRAY_AGG("UUID") INTO failing_entries_first_name
            FROM individual_individualdatasource
            WHERE upload_id=current_upload_id and individual_id is null and "isDeleted"=False AND NOT "Json_ext" ? 'first_name';

            SELECT ARRAY_AGG("UUID") INTO failing_entries_last_name
            FROM individual_individualdatasource
            WHERE upload_id=current_upload_id and individual_id is null and "isDeleted"=False AND NOT "Json_ext" ? 'last_name';

            SELECT ARRAY_AGG("UUID") INTO failing_entries_dob
            FROM individual_individualdatasource
            WHERE upload_id=current_upload_id and individual_id is null and "isDeleted"=False AND NOT "Json_ext" ? 'dob';

            -- If any entries do not meet the criteria or missing required fields, set the error message in the upload table and do not proceed further
            IF failing_entries_invalid_json IS NOT NULL or failing_entries_first_name IS NOT NULL OR failing_entries_last_name IS NOT NULL OR failing_entries_dob IS NOT NULL THEN
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

               update individual_individualdatasourceupload set status='FAIL' where "UUID" = current_upload_id;
            -- If no invalid entries, then proceed with the data manipulation
            ELSE
                BEGIN
                  WITH new_entry AS (
                    INSERT INTO individual_individual(
                    "UUID", "isDeleted", version, "UserCreatedUUID", "UserUpdatedUUID",
                    "Json_ext", first_name, last_name, dob
                    )
                    SELECT gen_random_uuid(), false, 1, userUUID, userUUID,
                    "Json_ext", "Json_ext"->>'first_name', "Json_ext" ->> 'last_name', to_date("Json_ext" ->> 'dob', 'YYYY-MM-DD')
                    FROM individual_individualdatasource
                    WHERE upload_id=current_upload_id and individual_id is null and "isDeleted"=False and validations ->> 'validation_errors' = '[]'
                    RETURNING "UUID", "Json_ext"  -- also return the Json_ext
                  )
                  UPDATE individual_individualdatasource
                  SET individual_id = new_entry."UUID"
                  FROM new_entry
                  WHERE upload_id=current_upload_id
                    and individual_id is null
                    and "isDeleted"=False
                    and individual_individualdatasource."Json_ext" = new_entry."Json_ext"  -- match on Json_ext
                    and validations ->> 'validation_errors' = '[]';

                    UPDATE individual_individualdatasourceupload
                    SET 
                      status = CASE 
                        WHEN percentage_invalid_items > 0 THEN 'PARTIAL_SUCCESS' 
                        ELSE 'SUCCESS' 
                      END
                    WHERE "UUID" = current_upload_id;
                    EXCEPTION
                    WHEN OTHERS then

                    update individual_individualdatasourceupload set status='FAIL' where "UUID" = current_upload_id;
                        UPDATE individual_individualdatasourceupload
                        SET error = coalesce(error, '{}'::jsonb) || jsonb_build_object('errors', jsonb_build_object(
                                            'error', SQLERRM,
                                            'timestamp', NOW()::text,
                                            'upload_id', current_upload_id::text
                                        ))
                        WHERE "UUID" = current_upload_id;
                END;
            END IF;
        END $$
        """, [current_upload_id, userUUID, percentage_invalid_items])
        # Process the cursor results or handle exceptions


def process_import_individual_workflow(user_uuid, upload_uuid):
    task_import_individual_workflow.delay(user_uuid=user_uuid, upload_uuid=upload_uuid)


def process_import_individual_workflow_valid(user_uuid, upload_uuid, percentage_of_invalid_items):
    task_import_individual_workflow_valid.delay(
        user_uuid=user_uuid,
        upload_uuid=upload_uuid,
        percentage_of_invalid_items=percentage_of_invalid_items
    )
