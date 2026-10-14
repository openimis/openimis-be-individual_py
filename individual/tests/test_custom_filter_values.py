from django.test import TestCase

from core.test_helpers import create_test_interactive_user
from individual.custom_filters import IndividualCustomFilterWizard
from individual.models import Individual
from individual.tests.test_helpers import create_individual


class IndividualCustomFilterStringValueTest(TestCase):
    """A string criterion selects the same records whether its value is bare or JSON-quoted."""

    @classmethod
    def setUpTestData(cls):
        user = create_test_interactive_user(username="cf_string_admin")
        cls.match = create_individual(user.username, {'json_ext': {'source': 'UAT release 26.10'}})
        cls.other = create_individual(user.username, {'json_ext': {'source': 'Other source'}})

    def _filter(self, condition):
        queryset = Individual.objects.filter(id__in=[self.match.id, self.other.id])
        return list(IndividualCustomFilterWizard().apply_filter_to_queryset([condition], queryset)
                    .values_list('id', flat=True))

    def test_bare_value(self):
        # Enrolment criteria and stored advanced criteria send the value without quotes.
        for condition in (
            'source__iexact__string=UAT release 26.10',
            'source__istartswith__string=UAT',
            'source__istartswith__string=U',
            'source__icontains__string=release',
        ):
            with self.subTest(condition=condition):
                self.assertEqual(self._filter(condition), [self.match.id])

    def test_quoted_value(self):
        # Searchers send the value JSON-encoded.
        for condition in (
            'source__iexact__string="UAT release 26.10"',
            'source__istartswith__string="UAT"',
            'source__icontains__string="release"',
        ):
            with self.subTest(condition=condition):
                self.assertEqual(self._filter(condition), [self.match.id])
