from core.data_masking import DataMaskAbs
from individual.apps import IndividualConfig


class IndividualMask(DataMaskAbs):
    masking_model = 'Individual'
    anon_fields = IndividualConfig.individual_mask_fields
    masking_enabled = IndividualConfig.individual_masking_enabled


class IndividualHistoryMask(DataMaskAbs):
    masking_model = 'HistoricalIndividual'
    anon_fields = IndividualConfig.individual_mask_fields
    masking_enabled = IndividualConfig.individual_masking_enabled
