import logging

from django.apps import AppConfig

from core.custom_filters import CustomFilterRegistryPoint

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "gql_individual_search_perms": ["159001"],
    "gql_individual_create_perms": ["159002"],
    "gql_individual_update_perms": ["159003"],
    "gql_individual_delete_perms": ["159004"],
    "gql_group_search_perms": ["180001"],
    "gql_group_create_perms": ["180002"],
    "gql_group_update_perms": ["180003"],
    "gql_group_delete_perms": ["180004"],
    "check_individual_update": False,
    "check_group_individual_update": False,
    "check_group_create": False,
    "individual_schema": "{}",
    "individual_accept_enrolment": "individual_service.create_accept_enrolment_task",
    "validation_import_valid_items_workflow": "individual-import-valid-items",
    "validation_calculation_uuid": "4362f958-5894-435b-9bda-df6cadf88352",
    "validation_import_valid_items": "individual_validation.import_valid_items",
    "unique_class_validation": "DeduplicationIndividualValidationStrategy",
    "validation_upload_valid_items": "validation.upload_valid_items",
    "validation_upload_valid_items_workflow": "individual-upload-valid-items.individual-upload-valid-items",
    "enable_python_workflows": True,
    "enable_maker_checker_logic_import": False,
    "enable_maker_checker_for_individual_upload": True,
    "enable_maker_checker_for_individual_update": True,
}


class IndividualConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'individual'

    gql_individual_search_perms = None
    gql_individual_create_perms = None
    gql_individual_update_perms = None
    gql_individual_delete_perms = None
    gql_group_search_perms = None
    gql_group_create_perms = None
    gql_group_update_perms = None
    gql_group_delete_perms = None
    check_individual_update = None
    check_group_individual_update = None
    check_group_create = None
    python_individual_import_workflow_group = None
    python_individual_import_workflow_name = None
    individual_schema = None
    individual_accept_enrolment = None
    validation_calculation_uuid = None
    validation_import_valid_items_workflow = None
    validation_import_valid_items = None
    unique_class_validation = None

    enable_python_workflows = None
    enable_maker_checker_logic_import = None

    validation_upload_valid_items_workflow = None
    validation_upload_valid_items = None

    enable_maker_checker_for_individual_upload = None
    enable_maker_checker_for_individual_update = None

    def ready(self):
        from core.models import ModuleConfiguration

        cfg = ModuleConfiguration.get_or_default(self.name, DEFAULT_CONFIG)
        self.__load_config(cfg)
        self.__validate_individual_schema(cfg)
        self.__initialize_custom_filters()
        self._set_up_workflows()

    @classmethod
    def __load_config(cls, cfg):
        """
        Load all config fields that match current AppConfig class fields, all custom fields have to be loaded separately
        """
        for field in cfg:
            if hasattr(IndividualConfig, field):
                setattr(IndividualConfig, field, cfg[field])

    @classmethod
    def __validate_individual_schema(self, cfg):
        if 'individual_schema' not in cfg:
            logging.error('No individual_schema in individual module config.')
            return

        from core.utils import validate_json_schema
        errors = validate_json_schema(cfg['individual_schema'])

        if errors:
            error_messages = [error['message'] for error in errors]
            logging.error('Schema validation errors in individual schema: %s', ', '.join(error_messages))

    @classmethod
    def __initialize_custom_filters(cls):
        from individual.custom_filters import IndividualCustomFilterWizard
        CustomFilterRegistryPoint.register_custom_filters(
            module_name=cls.name,
            custom_filter_class_list=[IndividualCustomFilterWizard]
        )

    def _set_up_workflows(self):
        from workflow.systems.python import PythonWorkflowAdaptor
        from individual.workflows import process_import_individuals_workflow, \
            process_update_valid_individuals_workflow, \
            process_import_valid_individuals_workflow, \
            process_update_individuals_workflow

        if self.enable_python_workflows:
            PythonWorkflowAdaptor.register_workflow(
                'Python Import Individuals',
                'individual',
                process_import_individuals_workflow
            )
            PythonWorkflowAdaptor.register_workflow(
                'Python Update Individuals',
                'individual',
                process_update_individuals_workflow
            )
            PythonWorkflowAdaptor.register_workflow(
                'Python Valid Upload Individuals',
                'individual',
                process_import_valid_individuals_workflow
            )
            PythonWorkflowAdaptor.register_workflow(
                'Python Valid Update Individuals',
                'individual',
                process_update_valid_individuals_workflow
            )

            # Replace default setup for invalid workflow to be python one
            if IndividualConfig.enable_python_workflows is True:

                # Resolve Maker-Checker Workflows Overwrite
                if self.validation_import_valid_items_workflow == DEFAULT_CONFIG[
                    'validation_import_valid_items_workflow']:
                    IndividualConfig.validation_import_valid_items_workflow \
                        = 'individual.Python Valid Upload Individuals'

                if self.validation_upload_valid_items_workflow == DEFAULT_CONFIG[
                    'validation_upload_valid_items_workflow']:
                    IndividualConfig.validation_upload_valid_items_workflow \
                        = 'individual.Python Valid Update Individuals'

    @staticmethod
    def get_individual_upload_file_path(filename):
        if filename:
            return f"individual_upload/{filename}"
        return f"individual_upload"
