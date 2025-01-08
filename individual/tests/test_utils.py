from django.test import TestCase
from individual.models import IndividualDataSource
from individual.utils import load_dataframe
import pandas as pd
import json

class UtilsTest(TestCase):

    def test_load_dataframe_basic(self):
        sources = [
            IndividualDataSource(id=1, json_ext={"name": "Alice", "age": 30}),
            IndividualDataSource(id=2, json_ext={"name": "Bob", "age": 25})
        ]
        df = load_dataframe(sources)

        # Verify structure and values
        self.assertEqual(len(df), 2)
        self.assertListEqual(df["id"].tolist(), [1, 2])
        self.assertListEqual(df["name"].tolist(), ["Alice", "Bob"])
        self.assertListEqual(df["age"].tolist(), [30, 25])

    def test_load_dataframe_empty_input(self):
        sources = []
        df = load_dataframe(sources)
        self.assertTrue(df.empty)

    def test_load_dataframe_blank_values_in_json_ext(self):
        source_df = pd.DataFrame([{"name": "Alice"}, {"name": ""}, {"name": None}])
        sources = []
        for id, row in source_df.iterrows():
            json_ext = json.loads(row.to_json())
            sources.append(IndividualDataSource(id=id+1, json_ext=json_ext))

        df = load_dataframe(sources)

        # Verify 'id' is added even when json_ext is incomplete
        self.assertEqual(len(df), 3)
        self.assertListEqual(df["id"].tolist(), [1, 2, 3])

        # Check empty values are loaded as expected
        self.assertIn("name", df.columns)
        self.assertEqual(df.at[0, "name"], 'Alice')
        self.assertEqual(df.at[1, "name"], '')
        self.assertIsNone(df.at[2, "name"])
