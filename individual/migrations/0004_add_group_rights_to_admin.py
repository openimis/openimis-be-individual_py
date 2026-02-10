from django.db import migrations
from core.utils import insert_role_right_for_system, remove_role_right_for_system


group_rights = [180001, 180002, 180003, 180004]
imis_administrator_system = 64


def add_rights(apps, schema_editor):
    for right_id in group_rights:
        insert_role_right_for_system(imis_administrator_system, right_id, apps)


def remove_rights(apps, schema_editor):
    for right_id in group_rights:
        remove_role_right_for_system(imis_administrator_system, right_id, apps)


class Migration(migrations.Migration):
    dependencies = [
        ('individual', '0003_group_groupindividual_historicalgroup_historicalgroupindividual')
    ]

    operations = [
        migrations.RunPython(add_rights, remove_rights),
    ]
