from django.db import migrations

schema_rights = [159009]
imis_administrator_system = 64


def add_rights(apps, schema_editor):
    RoleRight = apps.get_model('core', 'RoleRight')
    Role = apps.get_model('core', 'Role')
    role = Role.objects.filter(is_system=imis_administrator_system, validity_to__isnull=True).first()
    if not role:
        return
    for right_id in schema_rights:
        if not RoleRight.objects.filter(validity_to__isnull=True, role=role, right_id=right_id).exists():
            RoleRight.objects.create(role=role, right_id=right_id, audit_user_id=1)


def remove_rights(apps, schema_editor):
    RoleRight = apps.get_model('core', 'RoleRight')
    RoleRight.objects.filter(
        role__is_system=imis_administrator_system,
        right_id__in=schema_rights,
        validity_to__isnull=True
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('individual', '0020_label_rights_and_seed'),
    ]

    operations = [
        migrations.RunPython(add_rights, remove_rights),
    ]
