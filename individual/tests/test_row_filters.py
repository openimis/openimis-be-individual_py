"""get_queryset honours the OP-2029 validity contract (epic OP-3317, phase 1).

Explicit validity values return the expected rows; a caller asking for
nothing gets what it got before the contract existed.
"""

from datetime import datetime

from django.test import TestCase

from core.models.row_filters import Validity
from core.test_helpers import assert_row_filters, create_test_interactive_user, mark_deleted
from individual.models import Individual
from individual.tests.test_helpers import create_individual


class IndividualRowFiltersTest(TestCase):
    def test_individual(self):
        user = create_test_interactive_user(username="indrowfilters")
        live = create_individual(user.username)
        deleted = mark_deleted(create_individual(user.username))
        assert_row_filters(
            self, Individual, Individual.objects.filter(id__in=[live.id, deleted.id]), user,
            live.id, deleted.id, default_hides_deleted=False,
        )

    def test_a_validity_date_is_refused(self):
        # Individual has no business validity: a date has nothing to apply to.
        user = create_test_interactive_user(username="indrowfilters")
        with self.assertRaises(ValueError):
            Individual.get_queryset(Individual.objects.all(), user, validity=Validity.at(datetime.now()))
