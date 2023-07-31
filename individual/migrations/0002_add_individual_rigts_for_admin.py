from django.db import migrations

from core.models import Role, RoleRight

individual_rights = [159001, 159002, 159003, 159004]
imis_administrator_system = 64


def add_rights(apps, schema_editor):
    role = Role.objects.get(is_system=imis_administrator_system)
    for right_id in individual_rights:
        if not RoleRight.objects.filter(validity_to__isnull=True, role=role, right_id=right_id).exists():
            _add_right_for_role(role, right_id)


def _add_right_for_role(role, right_id):
    RoleRight.objects.create(role=role, right_id=right_id, audit_user_id=1)


def remove_rights(apps, schema_editor):
    RoleRight.objects.filter(
        role__is_system=imis_administrator_system,
        right_id__in=individual_rights,
        validity_to__isnull=True
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('individual', '0001_initial')
    ]

    operations = [
        migrations.RunPython(add_rights, remove_rights),
    ]
