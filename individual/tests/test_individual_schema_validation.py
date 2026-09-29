import json

from django.test import TestCase

from individual.apps import DEFAULT_CONFIG
from individual.validation import schema_dict, schema_errors


class SchemaValidationTest(TestCase):

    def assertRejected(self, schema, detail):
        errors = schema_errors(schema)
        self.assertTrue(errors, schema)
        self.assertTrue(any(detail in error['message'] for error in errors), errors)

    def test_shipped_default_schema_is_valid(self):
        self.assertEqual(schema_errors(json.loads(DEFAULT_CONFIG['individual_schema'])), [])

    def test_every_filter_type_and_option_is_accepted(self):
        schema = {"properties": {
            "email": {"type": "string", "description": "Contact address", "uniqueness": True},
            "household_size": {"type": "integer", "validationCalculation": {"name": "size_check"}},
            "income": {"type": "decimal"},
            "registered_on": {"type": "date"},
            "EmployedFlag": {"type": "boolean"},
        }}
        self.assertEqual(schema_errors(schema), [])

    def test_readme_example_is_valid(self):
        schema = {
            "$id": "https://example.com/beneficiares.schema.json", "type": "object",
            "$schema": "http://json-schema.org/draft-04/schema#",
            "properties": {"email": {
                "type": "string", "description": "email address",
                "validationCalculation": {"name": "EmailValidationStrategy"},
            }},
        }
        self.assertEqual(schema_errors(schema), [])

    def test_schema_without_properties_is_valid(self):
        self.assertEqual(schema_errors({}), [])

    def test_string_encoded_schema_is_rejected(self):
        errors = schema_errors(json.dumps({"properties": {"email": {"type": "string"}}}))
        self.assertEqual(len(errors), 1)

    def test_properties_must_be_an_object(self):
        self.assertRejected({"properties": ["email"]}, "properties")

    def test_invalid_json_schema_is_rejected(self):
        self.assertTrue(schema_errors({"properties": {"email": {"type": "string", "maxLength": "abc"}}}))
        self.assertTrue(schema_errors({"properties": {"fee": {"type": "decimal", "minimum": "abc"}}}))
        self.assertTrue(schema_errors({"type": "nope"}))

    def test_types_the_filter_wizard_cannot_map_are_rejected(self):
        # `number` is valid JSON Schema but has no filter.
        self.assertRejected({"properties": {"score": {"type": "number"}}}, "score")
        self.assertRejected({"properties": {"tags": {"type": "array"}}}, "tags")
        self.assertRejected({"properties": {"untyped": {}}}, "untyped")
        self.assertRejected({"properties": {"nullable": {"type": ["string", "null"]}}}, "nullable")

    def test_names_that_break_the_filter_lookup_are_rejected(self):
        self.assertRejected({"properties": {"first__name": {"type": "string"}}}, "first__name")
        self.assertRejected({"properties": {"name_": {"type": "string"}}}, "name_")
        self.assertRejected({"properties": {"a=b": {"type": "string"}}}, "a=b")
        self.assertTrue(schema_errors({"properties": {"": {"type": "string"}}}))

    def test_description_must_be_text(self):
        self.assertRejected({"properties": {"email": {"type": "string", "description": 3}}}, "email")

    def test_uniqueness_false_is_rejected(self):
        self.assertRejected({"properties": {"email": {"type": "string", "uniqueness": False}}}, "email")
        self.assertRejected({"properties": {"email": {"type": "string", "uniqueness": "yes"}}}, "email")

    def test_validation_calculation_needs_a_name(self):
        for calculation in [{}, {"name": ""}, {"name": 5}, "size_check"]:
            with self.subTest(calculation=calculation):
                self.assertRejected(
                    {"properties": {"size": {"type": "integer", "validationCalculation": calculation}}}, "size"
                )

    def test_stored_schema_as_dict(self):
        self.assertEqual(schema_dict({"properties": {}}), {"properties": {}})
        self.assertEqual(schema_dict('{"properties": {}}'), {"properties": {}})
        self.assertIsNone(schema_dict('not json'))
        self.assertIsNone(schema_dict('["a"]'))
        self.assertIsNone(schema_dict(None))
