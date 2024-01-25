from django.apps import AppConfig

DEFAULT_CONFIG = {
    "gql_individual_search_perms": ["159001"],
    "gql_individual_create_perms": ["159002"],
    "gql_individual_update_perms": ["159003"],
    "gql_individual_delete_perms": ["159004"],
    "gql_group_search_perms": ["180001"],
    "gql_group_create_perms": ["180002"],
    "gql_group_update_perms": ["180003"],
    "gql_group_delete_perms": ["180004"],
    "check_individual_update": True,
    "check_group_individual_update": True,
    "check_group_create": True,
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

    def ready(self):
        from core.models import ModuleConfiguration

        cfg = ModuleConfiguration.get_or_default(self.name, DEFAULT_CONFIG)
        self.__load_config(cfg)


        from workflow.systems.python import PythonWorkflowAdaptor
        from individual.workflows import import_individual_workflow
        PythonWorkflowAdaptor.register_workflow(
            "example-import-individual",
            "individual-import-group",
            import_individual_workflow
        )

    @classmethod
    def __load_config(cls, cfg):
        """
        Load all config fields that match current AppConfig class fields, all custom fields have to be loaded separately
        """
        for field in cfg:
            if hasattr(IndividualConfig, field):
                setattr(IndividualConfig, field, cfg[field])
