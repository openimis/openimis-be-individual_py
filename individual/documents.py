from django.apps import apps

# Check if the 'opensearch_reports' app is in INSTALLED_APPS
if 'opensearch_reports' in apps.app_configs:
    from django_opensearch_dsl import Document, fields as opensearch_fields
    from django_opensearch_dsl.registries import registry
    from individual.models import Individual

    @registry.register_document
    class IndividualDocument(Document):
        first_name = opensearch_fields.KeywordField(),
        last_name = opensearch_fields.KeywordField(),
        dob = opensearch_fields.DateField(),
        date_created = opensearch_fields.DateField()
        json_ext = opensearch_fields.ObjectField()

        class Index:
            name = 'individual'
            settings = {
                'number_of_shards': 1,
                'number_of_replicas': 0
            }
            auto_refresh = True

        class Django:
            model = Individual
            fields = [
                'id', 'first_name', 'last_name'
            ]
            queryset_pagination = 5000

        def prepare_json_ext(self, instance):
            json_ext_data = instance.json_ext
            json_data = self.__flatten_dict(json_ext_data)
            return json_data

        def __flatten_dict(self, d, parent_key='', sep='__'):
            items = {}
            for k, v in d.items():
                new_key = f"{parent_key}{sep}{k}" if parent_key else k
                if isinstance(v, dict):
                    items.update(self.__flatten_dict(v, new_key, sep=sep))
                else:
                    items[new_key] = v
            return items
