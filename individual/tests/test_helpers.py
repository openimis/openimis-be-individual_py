import copy
import json
import random
import string
from core.models import Role, RoleRight
from core.models.base_mutation import MutationLog
from core.test_helpers import create_test_interactive_user
from core.utils import TimeUtils
from graphql_jwt.shortcuts import get_token
from individual.models import Individual, Group, GroupIndividual
from individual.tests.data import (
    service_add_individual_payload
)
from location.test_helpers import create_test_village, assign_user_districts
from core.models.openimis_graphql_test_case import openIMISGraphQLTestCase


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


class BaseTestContext:
    def __init__(self, user):
        self.user = user


# Create a role with permissions to CRUD individuals and groups
def create_sp_role(created_by_user):
    sp_role_data = {
        'name': "SP Enrollment Officer",
        'is_blocked': False,
        'is_system': False,
        'audit_user_id': created_by_user.id_for_audit,
    }
    role = Role.objects.create(**sp_role_data)

    for right_id in [159001,159002,159003,159004,159005,180001,180002,180003,180004]:
        RoleRight.objects.create(
            **{
                "role_id": role.id,
                "right_id": right_id,
                "audit_user_id": role.audit_user_id,
                "validity_from": TimeUtils.now(),
            }
        )
    return role

class IndividualGQLTestCase(openIMISGraphQLTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.admin_user = create_test_interactive_user(username="adminSeesEveryone")
        cls.admin_token = get_token(cls.admin_user, BaseTestContext(user=cls.admin_user))

        cls.village_a = create_test_village({
            'name': 'Village A',
            'code': 'ViA',
        })

        cls.village_b = create_test_village({
            'name': 'Village B',
            'code': 'ViB'
        })

        cls.sp_role = create_sp_role(cls.admin_user)

        cls.dist_a_user = create_test_interactive_user(
            username="districtAUser", roles=[cls.sp_role.id])
        district_a_code = cls.village_a.parent.parent.code
        assign_user_districts(cls.dist_a_user, ["R1D1", district_a_code])
        cls.dist_a_user_token = get_token(cls.dist_a_user, BaseTestContext(user=cls.dist_a_user))

        cls.dist_b_user = create_test_interactive_user(
            username="districtBUser", roles=[cls.sp_role.id])
        district_b_code = cls.village_b.parent.parent.code
        assign_user_districts(cls.dist_b_user, [district_b_code])
        cls.dist_b_user_token = get_token(cls.dist_b_user, BaseTestContext(user=cls.dist_b_user))

        cls.med_enroll_officer = create_test_interactive_user(
            username="medEONoRight", roles=[1]) # 1 is the med enrollment officer role
        cls.med_enroll_officer_token = get_token(
            cls.med_enroll_officer, BaseTestContext(user=cls.med_enroll_officer))

    # overriding helper method from core to allow errors
    def get_mutation_result(self, mutation_uuid, token, internal=False):
        content = None
        while True:
            # wait for the mutation to be done
            if internal:
                filter_uuid = f""" id: "{mutation_uuid}" """
            else:
                filter_uuid = f""" clientMutationId: "{mutation_uuid}" """

            response = self.query(
                f"""
                {{
                mutationLogs({filter_uuid})
                {{
                pageInfo {{ hasNextPage, hasPreviousPage, startCursor, endCursor}}
                edges
                {{
                    node
                    {{
                        id,status,error,clientMutationId,clientMutationLabel,clientMutationDetails,requestDateTime,jsonExt
                    }}
                }}
                }}
                }}

                """,
                headers={"HTTP_AUTHORIZATION": f"Bearer {token}"},
            )
            return json.loads(response.content)

            time.sleep(1)

    def assert_mutation_error(self, uuid, expected_error):
        mutation_result = self.get_mutation_result(uuid, self.admin_token, internal=True)
        mutation_error = mutation_result['data']['mutationLogs']['edges'][0]['node']['error']
        self.assertTrue(expected_error in mutation_error, mutation_error)

    def assert_mutation_success(self, uuid):
        mutation_result = self.get_mutation_result(uuid, self.admin_token, internal=True)
        mutation_status = mutation_result['data']['mutationLogs']['edges'][0]['node']['status']
        self.assertEqual(mutation_status, MutationLog.SUCCESS)

