import pandas as pd
from django.test import SimpleTestCase

from individual.schema import patch_details


class PatchDetailsTest(SimpleTestCase):
    """Exports unfold json_ext into columns; the unfolded columns must not alter the exported values."""

    def _export(self):
        data = pd.DataFrame({
            'id': ['a1', 'b2'],
            'json_ext': [
                {'id': None, 'national_id': 773025346, 'number_of_children': 2, 'score': 2.5},
                {'educated_level': 'Primary'},
            ],
        })
        return patch_details(data)

    def test_whole_numbers_stay_whole_when_some_rows_lack_the_key(self):
        csv = self._export().to_csv(index=False)
        self.assertIn('773025346', csv)
        self.assertNotIn('773025346.0', csv)
        self.assertNotIn(',2.0,', csv)
        self.assertIn('2.5', csv)

    def test_json_ext_key_does_not_duplicate_an_exported_column(self):
        columns = [str(c).lower() for c in self._export().columns]
        self.assertEqual(columns.count('id'), 1)
