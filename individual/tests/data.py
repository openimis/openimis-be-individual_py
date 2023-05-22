from core.datetimes.ad_datetime import datetime

service_add_payload = {
    'first_name': 'TestFN',
    'last_name': 'TestLN',
    'dob': datetime.now(),
    'json_ext': {
        'key': 'value',
        'key2': 'value2'
    }
}

service_add_payload_no_ext = {
    'first_name': 'TestFN',
    'last_name': 'TestLN',
    'dob': datetime.now(),
}

service_update_payload = {
    'first_name': 'TestFNupdated',
    'last_name': 'TestLNupdated',
    'dob': datetime.now(),
    'json_ext': {
        'key': 'value',
        'key2': 'value2'
    }
}