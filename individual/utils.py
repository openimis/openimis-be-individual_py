from typing import Iterable

import pandas as pd

from django.db.models import Q, Value, Func, F

from individual.models import IndividualDataSource


def load_dataframe(individual_sources: Iterable[IndividualDataSource]) -> pd.DataFrame:
    data_from_source = []
    for individual_source in individual_sources:
        json_ext = individual_source.json_ext
        individual_source.json_ext["id"] = individual_source.id
        data_from_source.append(json_ext)
    recreated_df = pd.DataFrame(data_from_source)

    # Ensure 'location_code' is treated as a string if it exists
    if "location_code" in recreated_df.columns:
        recreated_df["location_code"] = recreated_df["location_code"].astype("string")

    return recreated_df


def fetch_summary_of_broken_items(upload_id):
    return list(IndividualDataSource.objects.filter(
        Q(is_deleted=False) &
        Q(upload_id=upload_id) &
        ~Q(validations__validation_errors=[])
    ).values_list('uuid', flat=True))


def fetch_summary_of_valid_items(upload_id):
    return list(IndividualDataSource.objects.filter(
        Q(is_deleted=False) &
        Q(upload_id=upload_id) &
        Q(validations__validation_errors=[])
    ).values_list('uuid', flat=True))
