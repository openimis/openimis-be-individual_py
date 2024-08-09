from datetime import timedelta

from core.datetimes.ad_datetime import datetime
from individual.models import GroupIndividual

service_add_individual_payload = {
    'first_name': 'TestFN',
    'last_name': 'TestLN',
    'dob': datetime.now(),
    'json_ext': {
        'key': 'value',
        'key2': 'value2'
    }
}

service_add_individual_payload_no_ext = {
    'first_name': 'TestFN',
    'last_name': 'TestLN',
    'dob': datetime.now(),
}

service_update_individual_payload = {
    'first_name': 'TestFNupdated',
    'last_name': 'TestLNupdated',
    'dob': datetime.now(),
    'json_ext': {
        'key': 'value',
        'key2': 'value2 updated'
    }
}

service_group_update_payload = {
    "date_created": datetime.now() - timedelta(days=1)
}

service_group_individual_payload = {
    "role": GroupIndividual.Role.HEAD
}
