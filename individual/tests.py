from django.test import TestCase


class IndividualTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_example_module_loaded_correctly(self):
        self.assertTrue(True)
