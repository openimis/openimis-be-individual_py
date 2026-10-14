import importlib

from django.test import SimpleTestCase

from individual.schema import Mutation


class MutationModuleResolutionTest(SimpleTestCase):
    """
    With async mutations (MODE=PROD) core's task resolves each mutation class as
    <_mutation_module>.schema.<class name>; a wrong _mutation_module only fails there.
    """

    def test_every_mutation_resolves_from_its_module(self):
        for name, field in Mutation._meta.fields.items():
            mutation_class = field.type
            with self.subTest(mutation=name):
                schema = importlib.import_module(f"{mutation_class._mutation_module}.schema")
                self.assertIs(getattr(schema, mutation_class.__name__, None), mutation_class)
