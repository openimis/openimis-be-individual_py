"""
Guard rails on individual's rights declaration.

Same structure as `claim` and `core`: `DJANGO_PERMS` by entity then by action, and
`_PERM_CFG` deriving the config keys from it. What is particular to individual is that
it carries **two** entities, in two distinct blocks of identifiers of the openIMIS
catalogue: `individual` (159xxx, the register of people) and `group` (180xxx, the
households). The test locks that separation down - it is what the flat shape hid.

What is locked down here:
  * the identifiers 159001-159005 and 180001-180004, as deployed and as
    `permissions_map.json` carries them - changing one withdraws access from the roles
    that hold it;
  * a config key with no class attribute is never loaded by `__load_config` and
    reading it raises AttributeError - the right becomes unenforceable;
  * `has_perms([])` returns True, so an empty list grants to everybody;
  * `GroupIndividual.scope_parent` points at the household: that is what makes a
    membership link inherit the group's right rather than have none at all.
"""

import json
import os

from django.test import TestCase

from individual.apps import (
    DJANGO_PERMS,
    IndividualConfig,
    _PERM_CFG,
    configured_perms,
    django_perms,
    perms,
)
from individual.models import Group, GroupIndividual, Individual

# The identifiers as deployed. Changing one is incompatible with the existing roles:
# this test has to be updated *and* the new right granted.
EXPECTED_RIGHTS = {
    "gql_individual_search_perms": ["159001"],
    "gql_individual_create_perms": ["159002"],
    "gql_individual_update_perms": ["159003"],
    "gql_individual_delete_perms": ["159004"],
    "gql_individual_undo_delete_perms": ["159005"],
    "gql_group_search_perms": ["180001"],
    "gql_group_create_perms": ["180002"],
    "gql_group_update_perms": ["180003"],
    "gql_group_delete_perms": ["180004"],
}

# The `permissions_map.json` keys that carry these same identifiers.
EXPECTED_MAP_ENTRIES = {
    "individual.individual_search": "159001",
    "individual.individual_create": "159002",
    "individual.individual_update": "159003",
    "individual.individual_delete": "159004",
    "individual.individual_undo_delete": "159005",
    "individual.group_search": "180001",
    "individual.group_create": "180002",
    "individual.group_update": "180003",
    "individual.group_delete": "180004",
}


def _load_permissions_map():
    """`permissions_map.json` lives in the assembly, not in the package."""
    from django.conf import settings

    candidates = [
        os.path.join(str(settings.BASE_DIR), "permissions_map.json"),
        os.path.join(os.path.dirname(str(settings.BASE_DIR)), "permissions_map.json"),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path) as handle:
                return json.load(handle)
    return None


class IndividualPermissionDeclarationTestCase(TestCase):
    def test_right_ids_unchanged(self):
        self.assertEqual(
            {key: getattr(IndividualConfig, key) for key in EXPECTED_RIGHTS},
            EXPECTED_RIGHTS,
        )

    def test_perm_cfg_covers_every_declared_action(self):
        declared = {
            (entity, action)
            for entity, actions in DJANGO_PERMS.items()
            for action in actions
        }
        self.assertEqual(set(_PERM_CFG.values()), declared)

    def test_perm_cfg_matches_config_attributes(self):
        """`__load_config` ignores the keys with no class attribute."""
        missing = [key for key in _PERM_CFG if not hasattr(IndividualConfig, key)]
        self.assertEqual(missing, [])

    def test_no_right_list_is_empty(self):
        empty = [key for key in _PERM_CFG if not getattr(IndividualConfig, key)]
        self.assertEqual(empty, [])

    def test_attributes_carry_the_declared_right(self):
        """
        The rights are constants set from DJANGO_PERMS: the attribute must equal the
        declaration, without going through the config.
        """
        for key, (entity, action) in _PERM_CFG.items():
            with self.subTest(key=key):
                self.assertEqual(getattr(IndividualConfig, key), perms(entity, action))

    def test_the_two_entities_are_declared_separately(self):
        self.assertEqual(set(DJANGO_PERMS), {"individual", "group"})

    def test_individual_and_group_never_share_a_right(self):
        """
        The person and the household are two registers: holding the right to read
        people must never amount to the right to read households, nor the reverse.
        """
        individual_ids = {rid for _, rid in DJANGO_PERMS["individual"].values()}
        group_ids = {rid for _, rid in DJANGO_PERMS["group"].values()}
        self.assertEqual(individual_ids & group_ids, set())

    def test_no_shared_right_ids(self):
        """No identifier sharing is intended in this module."""
        seen = {}
        for entity, actions in DJANGO_PERMS.items():
            for action, (_, right_id) in actions.items():
                seen.setdefault(right_id, []).append((entity, action))
        shared = {rid: who for rid, who in seen.items() if len(who) > 1}
        self.assertEqual(shared, {})

    def test_django_permission_names_are_unique(self):
        seen = {}
        for entity, actions in DJANGO_PERMS.items():
            for action, (name, _) in actions.items():
                seen.setdefault(name, []).append(f"{entity}.{action}")
        shared = {name: who for name, who in seen.items() if len(who) > 1}
        self.assertEqual(shared, {})

    def test_django_permission_names_use_the_app_label(self):
        """
        `Group` is a model of the `individual` app: its django name therefore carries
        `individual.`, even though the entity is called `group`.
        """
        self.assertEqual(Individual._meta.app_label, "individual")
        self.assertEqual(Group._meta.app_label, "individual")
        for entity, actions in DJANGO_PERMS.items():
            for action, (name, _) in actions.items():
                with self.subTest(entity=entity, action=action):
                    self.assertTrue(name.startswith("individual."))

    def test_unknown_entity_or_action_raises(self):
        with self.assertRaises(KeyError):
            perms("nosuchentity", "query")
        with self.assertRaises(KeyError):
            perms("individual", "nosuchaction")
        with self.assertRaises(KeyError):
            django_perms("group", "nosuchaction")

    # --- the access point through the model -------------------------------
    def test_individual_exposes_every_action_of_its_entity(self):
        for action in DJANGO_PERMS["individual"]:
            with self.subTest(action=action):
                self.assertEqual(
                    Individual.get_rights(action), configured_perms("individual", action)
                )
                self.assertTrue(Individual.get_rights(action))

    def test_group_exposes_every_action_of_its_entity(self):
        for action in DJANGO_PERMS["group"]:
            with self.subTest(action=action):
                self.assertEqual(
                    Group.get_rights(action), configured_perms("group", action)
                )
                self.assertTrue(Group.get_rights(action))

    def test_model_returns_none_for_an_undeclared_action(self):
        """None means "no rule": the caller must fail closed."""
        self.assertIsNone(Individual.get_rights("nosuchaction"))
        self.assertIsNone(Group.get_rights("undoDelete"))

    def test_model_reads_the_configured_value_not_the_declared_default(self):
        """
        ModuleConfiguration may override a right; the check must read the configured
        value, where `perms()` returns the declared default.
        """
        original = IndividualConfig.gql_group_search_perms
        try:
            IndividualConfig.gql_group_search_perms = ["999999"]
            self.assertEqual(Group.get_rights("query"), ["999999"])
            self.assertEqual(perms("group", "query"), ["180001"])
        finally:
            IndividualConfig.gql_group_search_perms = original

    # --- the sub-resource --------------------------------------------------
    def test_group_individual_is_scoped_on_the_group(self):
        """
        Of GroupIndividual's two foreign keys, the household is the owner: every
        existing check on this model requires a 180xxx right, none requires a 159xxx
        one.
        """
        from core.rights_scope import model_rights, scope_parent_of

        self.assertEqual(scope_parent_of(GroupIndividual), Group)
        self.assertIsNone(GroupIndividual.__dict__.get("get_rights"))
        for action in ("query", "create", "update", "delete"):
            with self.subTest(action=action):
                self.assertEqual(
                    model_rights(GroupIndividual, action),
                    configured_perms("group", action),
                )

    def test_ids_match_permissions_map(self):
        """The assembly's rights map must carry the same integers."""
        mapping = _load_permissions_map()
        if mapping is None:
            self.skipTest("permissions_map.json not found in this assembly")
        for key, right_id in EXPECTED_MAP_ENTRIES.items():
            with self.subTest(key=key):
                self.assertEqual(str(mapping.get(key)), right_id)
        declared_ids = {
            str(right_id)
            for actions in DJANGO_PERMS.values()
            for _, right_id in actions.values()
        }
        self.assertEqual(set(EXPECTED_MAP_ENTRIES.values()), declared_ids)
