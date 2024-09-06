import random
import string
import copy
from individual.models import Individual, Group, GroupIndividual
from individual.tests.data import (
    service_add_individual_payload
)


def generate_random_string(length=6):
    letters = string.ascii_uppercase
    return ''.join(random.choice(letters) for i in range(length))

def merge_dicts(original, override):
    updated = copy.deepcopy(original)
    for key, value in override.items():
        if isinstance(value, dict) and key in updated:
            updated[key] = merge_dicts(updated.get(key, {}), value)
        else:
            updated[key] = value
    return updated

def create_individual(username, payload_override={}):
    updated_payload = merge_dicts(service_add_individual_payload, payload_override)
    individual = Individual(**updated_payload)
    individual.save(username=username)

    return individual

def create_group(username, payload_override={}):
    updated_payload = merge_dicts({'code': generate_random_string()}, payload_override)
    group = Group(**updated_payload)
    group.save(username=username)
    return group

def add_individual_to_group(username, individual, group, is_head=True):
    object_data = {
        "individual_id": individual.id,
        "group_id": group.id,
    }
    if is_head:
        object_data["role"] = "HEAD"
    group_individual = GroupIndividual(**object_data)
    group_individual.save(username=username)
    return group_individual

def create_group_with_individual(username, group_override={}, individual_override={}):
    individual = create_individual(username, individual_override)
    group = create_group(username, group_override)
    group_individual = add_individual_to_group(username, individual, group)
    return individual, group, group_individual

