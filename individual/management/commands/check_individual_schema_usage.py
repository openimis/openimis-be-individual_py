from django.core.management.base import BaseCommand, CommandError

from individual.apps import IndividualConfig
from individual.schema_usage import owned_schemas
from individual.validation import schema_subset_errors


class Command(BaseCommand):
    help = 'Lists the schemas built from the individual schema (labels, benefit plans, ...) that use ' \
           'fields it does not have, or with another type. Such a schema keeps working, but cannot be ' \
           'edited until the individual schema carries those fields. Exits with an error when any is found.'

    def handle(self, *args, **options):
        system_properties = IndividualConfig.current_individual_schema().get('properties', {})
        found = 0
        for model, code, schema in owned_schemas():
            errors = schema_subset_errors(schema, system_properties)
            if errors:
                found += 1
                messages = '; '.join(error['message'] for error in errors)
                self.stdout.write(f"{model._meta.verbose_name} {code}: {messages}")
        if found:
            raise CommandError(f"{found} schema(s) not aligned with the individual schema")
        self.stdout.write("All schemas are aligned with the individual schema")
