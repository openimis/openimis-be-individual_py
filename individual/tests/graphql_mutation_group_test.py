import json
from individual.tests.test_helpers import (
    IndividualGQLTestCase,
)


class GroupGQLMutationTest(IndividualGQLTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_create_group_general_permission(self):
        query_str = f'''
            mutation {{
              createGroup(
                input: {{
                  code: "GF"
                  individualsData: []
                }}
              ) {{
                clientMutationId
                internalId
              }}
            }}
        '''

        # Anonymous User has no permission
        response = self.query(query_str)

        content = json.loads(response.content)
        id = content['data']['createGroup']['internalId']
        self.assert_mutation_error(id, 'mutation.authentication_required')

        # IMIS admin can do everything
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.admin_token}"}
        )
        content = json.loads(response.content)
        id = content['data']['createGroup']['internalId']
        self.assert_mutation_success(id)

        # Health Enrollment Officier (role=1) has no permission
        response = self.query(
            query_str,
            headers={"HTTP_AUTHORIZATION": f"Bearer {self.med_enroll_officer_token}"}
        )
        content = json.loads(response.content)
        id = content['data']['createGroup']['internalId']
        self.assert_mutation_error(id, 'mutation.authentication_required')
