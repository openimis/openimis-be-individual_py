import uuid
from datetime import datetime

from django.db import migrations

label_rights = [159006, 159007, 159008]
imis_administrator_system = 64

seed_labels = [
    ('INSUREE', 'Insuree'),
    ('PRACTITIONER', 'Practitioner'),
    ('CLAIM_ADMIN', 'Claim administrator'),
    ('BENEFICIARY', 'Beneficiary'),
]


def add_rights(apps, schema_editor):
    RoleRight = apps.get_model('core', 'RoleRight')
    Role = apps.get_model('core', 'Role')
    role = Role.objects.filter(is_system=imis_administrator_system, validity_to__isnull=True).first()
    if not role:
        return
    for right_id in label_rights:
        if not RoleRight.objects.filter(validity_to__isnull=True, role=role, right_id=right_id).exists():
            RoleRight.objects.create(role=role, right_id=right_id, audit_user_id=1)


def remove_rights(apps, schema_editor):
    RoleRight = apps.get_model('core', 'RoleRight')
    RoleRight.objects.filter(
        role__is_system=imis_administrator_system,
        right_id__in=label_rights,
        validity_to__isnull=True
    ).delete()


def add_labels(apps, schema_editor):
    User = apps.get_model('core', 'User')
    IndividualLabel = apps.get_model('individual', 'IndividualLabel')
    # A fresh database (unit tests) has no user yet; labels are then created by whoever needs them.
    user = User.objects.filter(username='Admin').first() or User.objects.order_by('username').first()
    if not user:
        return
    now = datetime.now()
    for code, name in seed_labels:
        if not IndividualLabel.objects.filter(code=code).exists():
            IndividualLabel.objects.create(
                id=uuid.uuid4(), code=code, name=name,
                user_created=user, user_updated=user,
                date_created=now, date_updated=now,
            )


def remove_labels(apps, schema_editor):
    IndividualLabel = apps.get_model('individual', 'IndividualLabel')
    IndividualLabel.objects.filter(code__in=[code for code, _ in seed_labels]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0013_users_api'),
        ('individual', '0019_individuallabel_individual_labels'),
    ]

    operations = [
        migrations.RunPython(add_rights, remove_rights),
        migrations.RunPython(add_labels, remove_labels),
    ]
