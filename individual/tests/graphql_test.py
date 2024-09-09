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
from individual.tests.test_helpers import (
    create_individual,
    create_group_with_individual,
    add_individual_to_group,
)
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
        cls.individual_a, cls.group_a, _ = create_group_with_individual(
            cls.admin_user.username,
            group_override={'village': cls.village_a},
            individual_override={'village': cls.village_a},
        )
        cls.individual_a_no_group = create_individual(
            cls.admin_user.username,
            payload_override={'village': cls.village_a},
        )
        cls.individual_a_group_no_loc, cls.group_no_loc, _ = create_group_with_individual(
            cls.admin_user.username,
            individual_override={'village': cls.village_a},
        )

        cls.individual_no_loc_group_a = create_individual(cls.admin_user.username)
        add_individual_to_group(
            cls.admin_user.username,
            cls.individual_no_loc_group_a,
            cls.group_a,
        )

        cls.individual_no_loc_no_group = create_individual(cls.admin_user.username)

        cls.village_b = create_test_village({
            'name': 'Village B',
            'code': 'ViB'
        })
        cls.individual_b, cls.group_b, _ = create_group_with_individual(
            cls.admin_user.username,
            group_override={'village': cls.village_b},
            individual_override={'village': cls.village_b},
        )

        cls.sp_role = create_sp_role(cls.admin_user)

        cls.dist_a_user = create_test_interactive_user(
            username="districtUserSeesDistrict", roles=[cls.sp_role.id])
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


    def test_group_query_general_permission(self):
        date_created = str(self.group_a.date_created).replace(' ', 'T')
        query_str = f'''query {{
          group(dateCreated_Gte: "{date_created}") {{
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
                code
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
        group_data = content['data']['group']

        group_uuids = list(
            e['node']['uuid'] for e in group_data['edges']
        )
        self.assertTrue(str(self.group_a.uuid) in group_uuids)
        self.assertTrue(str(self.group_b.uuid) in group_uuids)
        self.assertTrue(str(self.group_no_loc.uuid) in group_uuids)

        # Health Enrollment Officier (role=1) sees nothing
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.med_enroll_officer_token}"}
        )
        content = json.loads(response.content)
        self.assertEqual(content['errors'][0]['message'], 'Unauthorized')

    def test_group_query_row_security(self):
        date_created = str(self.group_a.date_created).replace(' ', 'T')
        query_str = f'''query {{
          group(dateCreated_Gte: "{date_created}") {{
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
                code
                village {{
                  id uuid code name type
                  parent {{
                    id uuid code name type
                    parent {{
                      id uuid code name type
                      parent {{
                        id uuid code name type
                      }}
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}'''

        # SP officer A sees only groups from their assigned districts
        # and groups without location
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_a_user_token}"}
        )
        self.assertResponseNoErrors(response)

        content = json.loads(response.content)
        group_data = content['data']['group']

        group_uuids = list(
            e['node']['uuid'] for e in group_data['edges']
        )
        self.assertTrue(str(self.group_a.uuid) in group_uuids)
        self.assertFalse(str(self.group_b.uuid) in group_uuids)
        self.assertTrue(str(self.group_no_loc.uuid) in group_uuids)

        # SP officer B sees only group from their assigned district
        # and groups without location
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        self.assertResponseNoErrors(response)

        content = json.loads(response.content)
        group_data = content['data']['group']

        group_uuids = list(
            e['node']['uuid'] for e in group_data['edges']
        )
        self.assertFalse(str(self.group_a.uuid) in group_uuids)
        self.assertTrue(str(self.group_b.uuid) in group_uuids)
        self.assertTrue(str(self.group_no_loc.uuid) in group_uuids)


    def test_group_history_query_row_security(self):
        def send_group_history_query(group_uuid, as_user_token):
            date_created = str(self.group_a.date_created).replace(' ', 'T')
            query_str = f'''query {{
              groupHistory(
                isDeleted: false,
                id: "{group_uuid}",
                first: 10,
                orderBy: ["-version"]
              ) {{
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
                    isDeleted
                    dateCreated
                    dateUpdated
                    code
                    jsonExt
                    version
                    userUpdated {{
                      username
                    }}
                  }}
                }}
              }}
            }}'''

            return self.query(
                query_str,
                headers={"HTTP_AUTHORIZATION": f"Bearer {as_user_token}"}
            )

        # SP officer A sees only group from their assigned districts and
        # groups wihtout location
        permitted_uuids = [
            self.group_a.uuid,
            self.group_no_loc.uuid,
        ]

        not_permitted_uuids = [
            self.group_b.uuid,
        ]

        for uuid in permitted_uuids:
            response = send_group_history_query(uuid, self.dist_a_user_token)
            self.assertResponseNoErrors(response)
            content = json.loads(response.content)
            self.assertTrue(content['data']['groupHistory']['totalCount'] > 0)

        for uuid in not_permitted_uuids:
            response = send_group_history_query(uuid, self.dist_a_user_token)
            self.assertResponseNoErrors(response)
            content = json.loads(response.content)
            self.assertEqual(content['data']['groupHistory']['totalCount'], 0)


        # SP officer B sees only group from their assigned district and
        # groups wihtout location
        permitted_uuids = [
            self.group_b.uuid,
            self.group_no_loc.uuid,
        ]

        not_permitted_uuids = [
            self.group_a.uuid,
        ]

        for uuid in permitted_uuids:
            response = send_group_history_query(uuid, self.dist_b_user_token)
            self.assertResponseNoErrors(response)
            content = json.loads(response.content)
            self.assertTrue(content['data']['groupHistory']['totalCount'] > 0)

        for uuid in not_permitted_uuids:
            response = send_group_history_query(uuid, self.dist_b_user_token)
            self.assertResponseNoErrors(response)
            content = json.loads(response.content)
            self.assertEqual(content['data']['groupHistory']['totalCount'], 0)


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
        self.assertTrue(str(self.individual_a_no_group.uuid) in individual_uuids)
        self.assertTrue(str(self.individual_a_group_no_loc.uuid) in individual_uuids)
        self.assertTrue(str(self.individual_no_loc_no_group.uuid) in individual_uuids)
        self.assertTrue(str(self.individual_no_loc_group_a.uuid) in individual_uuids)

        # Health Enrollment Officier (role=1) sees nothing
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.med_enroll_officer_token}"}
        )
        content = json.loads(response.content)
        self.assertEqual(content['errors'][0]['message'], 'Unauthorized')


    def test_individual_query_row_security(self):
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
                village {{
                  id uuid code name type
                  parent {{
                    id uuid code name type
                    parent {{
                      id uuid code name type
                      parent {{
                        id uuid code name type
                      }}
                    }}
                  }}
                }}
              }}
            }}
          }}
        }}'''

        # SP officer A sees only individual from their assigned districts
        # individuals wihtout location, and individuals whose group has no location
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_a_user_token}"}
        )
        self.assertResponseNoErrors(response)

        content = json.loads(response.content)
        individual_data = content['data']['individual']

        individual_uuids = list(
            e['node']['uuid'] for e in individual_data['edges']
        )
        self.assertTrue(str(self.individual_a.uuid) in individual_uuids)
        self.assertFalse(str(self.individual_b.uuid) in individual_uuids)
        self.assertTrue(str(self.individual_a_no_group.uuid) in individual_uuids)
        self.assertTrue(str(self.individual_a_group_no_loc.uuid) in individual_uuids)
        self.assertTrue(str(self.individual_no_loc_no_group.uuid) in individual_uuids)
        self.assertTrue(str(self.individual_no_loc_group_a.uuid) in individual_uuids)

        # SP officer B sees only individual from their assigned district,
        # individuals wihtout location, and individuals whose group has no location
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.dist_b_user_token}"}
        )
        self.assertResponseNoErrors(response)

        content = json.loads(response.content)
        individual_data = content['data']['individual']

        individual_uuids = list(
            e['node']['uuid'] for e in individual_data['edges']
        )
        self.assertFalse(str(self.individual_a.uuid) in individual_uuids)
        self.assertTrue(str(self.individual_b.uuid) in individual_uuids)
        self.assertFalse(str(self.individual_a_no_group.uuid) in individual_uuids)
        self.assertTrue(str(self.individual_a_group_no_loc.uuid) in individual_uuids)
        self.assertTrue(str(self.individual_no_loc_no_group.uuid) in individual_uuids)
        self.assertTrue(str(self.individual_no_loc_group_a.uuid) in individual_uuids)


    def test_individual_history_query_row_security(self):
        def send_individual_history_query(individual_uuid, as_user_token):
            date_created = str(self.individual_a.date_created).replace(' ', 'T')
            query_str = f'''query {{
              individualHistory(
                isDeleted: false,
                id: "{individual_uuid}",
                first: 10,
                orderBy: ["-version"]
              ) {{
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
                    isDeleted
                    dateCreated
                    dateUpdated
                    firstName
                    lastName
                    dob
                    jsonExt
                    version
                    userUpdated {{
                      username
                    }}
                  }}
                }}
              }}
            }}'''

            return self.query(
                query_str,
                headers={"HTTP_AUTHORIZATION": f"Bearer {as_user_token}"}
            )

        # SP officer A sees only individual from their assigned districts
        # individuals wihtout location, and individuals whose group has no location
        permitted_uuids = [
            self.individual_a.uuid,
            self.individual_a_no_group.uuid,
            self.individual_a_group_no_loc.uuid,
            self.individual_no_loc_no_group.uuid,
            self.individual_no_loc_group_a.uuid,
        ]

        not_permitted_uuids = [
            self.individual_b.uuid,
        ]

        for uuid in permitted_uuids:
            response = send_individual_history_query(uuid, self.dist_a_user_token)
            self.assertResponseNoErrors(response)
            content = json.loads(response.content)
            self.assertTrue(content['data']['individualHistory']['totalCount'] > 0)

        for uuid in not_permitted_uuids:
            response = send_individual_history_query(uuid, self.dist_a_user_token)
            self.assertResponseNoErrors(response)
            content = json.loads(response.content)
            self.assertEqual(content['data']['individualHistory']['totalCount'], 0)


        # SP officer B sees only individual from their assigned district,
        # individuals wihtout location, and individuals whose group has no location
        permitted_uuids = [
            self.individual_b.uuid,
            self.individual_a_group_no_loc.uuid,
            self.individual_no_loc_no_group.uuid,
            self.individual_no_loc_group_a.uuid,
        ]

        not_permitted_uuids = [
            self.individual_a.uuid,
            self.individual_a_no_group.uuid,
        ]

        for uuid in permitted_uuids:
            response = send_individual_history_query(uuid, self.dist_b_user_token)
            self.assertResponseNoErrors(response)
            content = json.loads(response.content)
            self.assertTrue(content['data']['individualHistory']['totalCount'] > 0)

        for uuid in not_permitted_uuids:
            response = send_individual_history_query(uuid, self.dist_b_user_token)
            self.assertResponseNoErrors(response)
            content = json.loads(response.content)
            self.assertEqual(content['data']['individualHistory']['totalCount'], 0)
