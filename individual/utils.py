from typing import Iterable

import pandas as pd

from individual.models import IndividualDataSource


def load_dataframe(individual_sources: Iterable[IndividualDataSource]) -> pd.DataFrame:
    data_from_source = []
    for individual_source in individual_sources:
        json_ext = individual_source.json_ext
        individual_source.json_ext["id"] = individual_source.id
        data_from_source.append(json_ext)
    recreated_df = pd.DataFrame(data_from_source)
    return recreated_df
