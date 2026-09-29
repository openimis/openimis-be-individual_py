import copy
import json
import logging
from datetime import datetime

from django.apps import AppConfig
from django.db.models import Q

from core.custom_filters import CustomFilterRegistryPoint
from core.data_masking import MaskingClassRegistryPoint
from core.module_config_registry import register_validator, register_reloader
from core.rights_declaration import RightsDeclaration

logger = logging.getLogger(__name__)

MODULE_NAME = "individual"

# Rights, by entity then by action, in two distinct blocks of identifiers of the openIMIS
# catalogue: `individual` (159xxx) is the register of people, and its `label` registry
# takes the next free identifiers of that block; `group` (180xxx) is the register of
# households. No identifier is shared between entities.
#
# The django names all carry the `individual` app_label: `Group` is a model of this
# app, not of a "group" app - the entity is named after the business object, the django
# name after the app that hosts the model.
DJANGO_PERMS = {
    "individual": {
        "query": ("individual.view_individual", 159001),
        "create": ("individual.add_individual", 159002),
        "update": ("individual.change_individual", 159003),
        "delete": ("individual.delete_individual", 159004),
        # A business action: restoring a soft-deleted person is neither a creation
        # nor an ordinary modification, and already carries its own identifier.
        "undoDelete": ("individual.undo_delete_individual", 159005),
    },
    # The label registry. Its writes follow the individual block (159006-159008); reading
    # labels is reading individual data, so it stays on the individual query right.
    "label": {
        "create": ("individual.add_individuallabel", 159006),
        "update": ("individual.change_individuallabel", 159007),
        "delete": ("individual.delete_individuallabel", 159008),
    },
    # The system-wide individual schema, stored in the module configuration: no model
    # carries it, the django name exists only to map the right.
    "schema": {
        "update": ("individual.change_individual_schema", 159009),
    },
    "group": {
        "query": ("individual.view_group", 180001),
        "create": ("individual.add_group", 180002),
        "update": ("individual.change_group", 180003),
        "delete": ("individual.delete_group", 180004),
    },
}

_PERM_CFG = {
    "gql_individual_search_perms": ("individual", "query"),
    "gql_individual_create_perms": ("individual", "create"),
    "gql_individual_update_perms": ("individual", "update"),
    "gql_individual_delete_perms": ("individual", "delete"),
    "gql_individual_undo_delete_perms": ("individual", "undoDelete"),
    "gql_individual_label_create_perms": ("label", "create"),
    "gql_individual_label_update_perms": ("label", "update"),
    "gql_individual_label_delete_perms": ("label", "delete"),
    "gql_individual_schema_update_perms": ("schema", "update"),
    "gql_group_search_perms": ("group", "query"),
    "gql_group_create_perms": ("group", "create"),
    "gql_group_update_perms": ("group", "update"),
    "gql_group_delete_perms": ("group", "delete"),
}

RIGHTS = RightsDeclaration(MODULE_NAME, DJANGO_PERMS, _PERM_CFG)

perms = RIGHTS.perms
django_perms = RIGHTS.django_perm_names
configured_perms = RIGHTS.configured
require = RIGHTS.require


DEFAULT_CONFIG = {
    "check_individual_update": True,
    "check_individual_delete": True,
    "check_group_individual_update": True,
    "check_group_create": True,
    "check_group_delete": True,
    "individual_schema": json.dumps({
        "properties": {
            "email": {"type": "string"},
            "able_bodied": {"type": "boolean"},
            "national_id": {"type": "string"},
            "educated_level": {"type": "string"},
            "chronic_illness": {"type": "boolean"},
            "national_id_type": {"type": "string"},
            "number_of_elderly": {"type": "integer"},
            "number_of_children": {"type": "integer"},
            "beneficiary_data_source": {"type": "string"}
        }
    }),
    "individual_accept_enrolment": "individual_service.create_accept_enrolment_task",
    "validation_import_valid_items_workflow": "individual-import-valid-items",
    "validation_calculation_uuid": "4362f958-5894-435b-9bda-df6cadf88352",
    "validation_import_valid_items": "individual_validation.import_valid_items",
    "validation_import_group_valid_items": "individual_validation.import_group_valid_items",
    "validation_upload_valid_items": "individual_validation.upload_valid_items",
    "validation_upload_valid_items_workflow": "individual-upload-valid-items.individual-upload-valid-items",
    "enable_python_workflows": True,
    "enable_maker_checker_logic_import": True,
    "enable_maker_checker_for_individual_upload": True,
    "enable_maker_checker_for_group_upload": True,
    "enable_maker_checker_for_individual_update": True,
    "enable_maker_checker_for_group_update": True,
    "individual_masking_enabled": True,
    "individual_mask_fields": [
        'json_ext.beneficiary_data_source',
        'json_ext.educated_level'
    ],
    "individual_base_fields": [
        'first_name', 'last_name', 'dob', 'location_name', 'location_code', 'id'
    ]
}


def stored_configuration():
    """The module's stored configuration rows that are in force, as `get_or_default` selects them."""
    from core.models import ModuleConfiguration

    return ModuleConfiguration.objects.filter(
        Q(is_disabled_until=None) | Q(is_disabled_until__lt=datetime.now()),
        module=MODULE_NAME, layer='be',
    )


class IndividualConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = MODULE_NAME

    # Rights: constants, no longer overridable. They go neither through DEFAULT_CFG
    # nor through ready(): `ModuleConfiguration.get_or_default` now ignores any
    # `_perms` key stored in the database.
    gql_individual_search_perms = RIGHTS.perms("individual", "query")
    gql_individual_create_perms = RIGHTS.perms("individual", "create")
    gql_individual_update_perms = RIGHTS.perms("individual", "update")
    gql_individual_delete_perms = RIGHTS.perms("individual", "delete")
    gql_individual_undo_delete_perms = RIGHTS.perms("individual", "undoDelete")

    gql_individual_label_create_perms = RIGHTS.perms("label", "create")
    gql_individual_label_update_perms = RIGHTS.perms("label", "update")
    gql_individual_label_delete_perms = RIGHTS.perms("label", "delete")

    gql_individual_schema_update_perms = RIGHTS.perms("schema", "update")

    gql_group_search_perms = RIGHTS.perms("group", "query")
    gql_group_create_perms = RIGHTS.perms("group", "create")
    gql_group_update_perms = RIGHTS.perms("group", "update")
    gql_group_delete_perms = RIGHTS.perms("group", "delete")
    check_individual_update = None
    check_individual_delete = None
    check_group_individual_update = None
    check_group_create = None
    check_group_delete = None
    python_individual_import_workflow_group = None
    python_individual_import_workflow_name = None
    individual_schema = None
    _loaded_individual_schema = None
    individual_accept_enrolment = None
    validation_calculation_uuid = None
    validation_import_valid_items_workflow = None
    validation_import_valid_items = None
    validation_import_group_valid_items = None

    enable_python_workflows = None
    enable_maker_checker_logic_import = None

    validation_upload_valid_items_workflow = None
    validation_upload_valid_items = None

    enable_maker_checker_for_individual_upload = None
    enable_maker_checker_for_group_upload = None
    enable_maker_checker_for_individual_update = None
    enable_maker_checker_for_group_update = None
    individual_mask_fields = None
    individual_masking_enabled = None
    individual_base_fields = None

    def ready(self):
        from core.models import ModuleConfiguration

        cfg = ModuleConfiguration.get_or_default(self.name, DEFAULT_CONFIG)
        self.__load_config(cfg)
        self.__validate_individual_schema(cfg)
        self.__initialize_custom_filters()
        self._set_up_workflows()
        self.__register_masking_class()
        register_validator(self.name, self._validate_module_config)
        register_reloader(self.name, self._reload_module_config)

        from individual.models import IndividualLabel
        from individual.schema_usage import register_schema_owner
        register_schema_owner(IndividualLabel, 'code', 'json_schema')

    def _merge_with_defaults(self, instance):
        # `instance._cfg` has already stripped the `_perms` keys from the stored
        # config, and DEFAULT_CONFIG holds none any more: the merge therefore cannot
        # reintroduce a right, and `__load_config` leaves the class constants intact.
        return {**copy.deepcopy(DEFAULT_CONFIG), **instance._cfg}

    def _validate_module_config(self, instance):
        cfg = self._merge_with_defaults(instance)
        self.__validate_individual_schema(cfg)

    def _reload_module_config(self, instance):
        self._apply_config(self._merge_with_defaults(instance))

    def _apply_config(self, cfg):
        self.__load_config(cfg)

        # Reinitialize custom filters to apply the new schema
        self.__initialize_custom_filters()

        # Workflow needs to be re-registered, otherwise default/invalid ones would apply
        self._set_up_workflows()

        # TODO: handle reloading of masking configs
        logger.info(f"Reloaded app configs (except masking configs) for {self.name} module")

    @classmethod
    def current_individual_schema(cls):
        """
        The system-wide schema, as a dict. Saving the configuration reloads only the process
        that saved it; reading the stored value here lets every other worker follow without a
        restart. It is compared with what this process last loaded, not with the attribute,
        so only a save made elsewhere triggers a reload.
        """
        from django.apps import apps
        from core.models import ModuleConfiguration

        stored = stored_configuration().values_list('config', flat=True).first()
        try:
            stored_schema = json.loads(stored).get('individual_schema') if stored else None
        except ValueError:
            stored_schema = cls._loaded_individual_schema
        if (stored_schema or DEFAULT_CONFIG['individual_schema']) != cls._loaded_individual_schema:
            apps.get_app_config(MODULE_NAME)._apply_config(
                ModuleConfiguration.get_or_default(MODULE_NAME, DEFAULT_CONFIG))
        return json.loads(cls.individual_schema or '{}')

    @classmethod
    def __load_config(cls, cfg):
        """
        Load all config fields that match current AppConfig class fields, all custom fields have to be loaded separately
        """
        for field in cfg:
            if hasattr(IndividualConfig, field):
                setattr(IndividualConfig, field, cfg[field])
        cls._loaded_individual_schema = cfg.get('individual_schema')

    @classmethod
    def __validate_individual_schema(cls, cfg):
        # TODO: validate against cls.individual_schema it is already assigned
        if 'individual_schema' not in cfg:
            logging.error('No individual_schema in individual module config.')
            return

        from individual.validation import schema_errors
        try:
            errors = schema_errors(json.loads(cfg['individual_schema']))
        except (TypeError, ValueError) as error:
            errors = [{'message': str(error)}]

        if errors:
            error_messages = [error['message'] for error in errors]
            logging.error('Schema validation errors in individual schema: %s', ', '.join(error_messages))

    @classmethod
    def __initialize_custom_filters(cls):
        from individual.custom_filters import (
            IndividualCustomFilterWizard,
            GroupCustomFilterWizard,
            GroupIndividualCustomFilterWizard,
        )
        CustomFilterRegistryPoint.register_custom_filters(
            module_name=cls.name,
            custom_filter_class_list=[
                IndividualCustomFilterWizard,
                GroupCustomFilterWizard,
                GroupIndividualCustomFilterWizard
            ]
        )

    def __register_masking_class(cls):
        from individual.data_masking import IndividualMask, IndividualHistoryMask
        MaskingClassRegistryPoint.register_masking_class(
            masking_class_list=[IndividualMask(), IndividualHistoryMask()]
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
        return "individual_upload"
