import json
from core.models import User, filter_validity, Role, RoleRight
from core.models.openimis_graphql_test_case import openIMISGraphQLTestCase
from core.test_helpers import create_test_interactive_user
from core.utils import TimeUtils
from django.conf import settings
from django.utils import timezone
from graphql_jwt.shortcuts import get_token
from location.models import Location
from rest_framework import status
from individual.tests.test_helpers import create_individual
from location.test_helpers import create_test_village, assign_user_districts


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


class IndividualGQLTest(openIMISGraphQLTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.admin_user = create_test_interactive_user(username="adminSeesEveryone")
        cls.admin_token = get_token(cls.admin_user, BaseTestContext(user=cls.admin_user))

        cls.village_a = create_test_village({
            'name': 'Village A',
            'code': 'ViA',
        })
        cls.individual_a = create_individual(
            cls.admin_user.username,
            payload_override={'village': cls.village_a}
        )

        cls.village_b = create_test_village({
            'name': 'Village B',
            'code': 'ViB'
        })
        cls.individual_b = create_individual(
            cls.admin_user.username,
            payload_override={'village': cls.village_b}
        )

        cls.sp_role = create_sp_role(cls.admin_user)

        cls.dist_a_user = create_test_interactive_user(
            username="districtUserSeesDistrict", roles=[cls.sp_role.id])
        assign_user_districts(cls.dist_a_user, ["R1D1", cls.village_a.parent.parent.code])
        cls.dist_a_user_token = get_token(cls.dist_a_user, BaseTestContext(user=cls.dist_a_user))

        cls.dist_b_user = create_test_interactive_user(
            username="districtBUser", roles=[cls.sp_role.id])
        assign_user_districts(cls.dist_b_user, [cls.village_b.parent.parent.code])
        cls.dist_b_user_token = get_token(cls.dist_b_user, BaseTestContext(user=cls.dist_b_user))

        cls.med_enroll_officer = create_test_interactive_user(
            username="medEONoRight", roles=[1]) # 1 is the med enrollment officer role
        cls.med_enroll_officer_token = get_token(
            cls.med_enroll_officer, BaseTestContext(user=cls.med_enroll_officer))


    def test_individual_query_general_permission(self):
        date_created = str(self.individual_a.date_created).replace(' ', 'T')
        query_str = f'''query {{
          individual(dateCreated_Gte: "{date_created}") {{
            totalCount
            pageInfo {{
              hasNextPage
              hasPreviousPage
              startCursor
              endCursor
            }}
            edges {{
              node {{
                id
                uuid
                firstName
                lastName
                dob
              }}
            }}
          }}
        }}'''

        # Anonymous User sees nothing
        response = self.query(query_str)

        content = json.loads(response.content)
        self.assertEqual(content['errors'][0]['message'], 'Unauthorized')

        # IMIS admin sees everything
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"}
        )
        self.assertResponseNoErrors(response)

        content = json.loads(response.content)
        individual_data = content['data']['individual']

        individual_uuids = list(
            e['node']['uuid'] for e in individual_data['edges']
        )
        self.assertTrue(str(self.individual_a.uuid) in individual_uuids)
        self.assertTrue(str(self.individual_b.uuid) in individual_uuids)

        # Health Enrollment Officier (role=1) sees nothing
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.med_enroll_officer_token}"}
        )
        content = json.loads(response.content)
        self.assertEqual(content['errors'][0]['message'], 'Unauthorized')
