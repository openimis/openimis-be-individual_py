import random
import string

from django.db import migrations, models


def generate_unique_code(existing_codes):
    """Generate a unique 8-digit code."""
    while True:
        code = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        if code not in existing_codes:
            return code


def populate_group_codes(apps, schema_editor):
    Group = apps.get_model('individual', 'Group')
    HistoricalGroup = apps.get_model('individual', 'HistoricalGroup')
    existing_codes = set(Group.objects.values_list('code', flat=True))

    groups_without_code = Group.objects.filter(code__isnull=True)
    for group in groups_without_code:
        generated_code = generate_unique_code(existing_codes)
        group.code = generated_code
        group.save()
        for historical_group in HistoricalGroup.objects.filter(id=group.id):
            historical_group.code = generated_code
            historical_group.save()
        existing_codes.add(group.code)

    historical_groups_without_code = HistoricalGroup.objects.filter(code__isnull=True)
    for historical_group in historical_groups_without_code:
        generated_code = generate_unique_code(existing_codes)
        historical_group.code = generated_code
        historical_group.save()


def reverse_populate_group_codes(apps, schema_editor):
    Group = apps.get_model('individual', 'Group')
    HistoricalGroup = apps.get_model('individual', 'HistoricalGroup')
    for group in Group.objects.filter(code__isnull=False):
        group.code = None
        group.save()

    for historical_group in HistoricalGroup.objects.filter(code__isnull=False):
        historical_group.code = None
        historical_group.save()


class Migration(migrations.Migration):
    dependencies = [
        ('individual', '0012_auto_20240516_1029'),
    ]

    operations = [
        migrations.AddField(
            model_name='group',
            name='code',
            field=models.CharField(max_length=64, blank=True, null=True)
        ),
        migrations.AddField(
            model_name='historicalgroup',
            name='code',
            field=models.CharField(max_length=64, blank=True, null=True)
        ),
        migrations.RunPython(populate_group_codes, reverse_code=reverse_populate_group_codes),
        migrations.AlterField(
            model_name='group',
            name='code',
            field=models.CharField(max_length=64, blank=False, null=False)
        ),
        migrations.AlterField(
            model_name='historicalgroup',
            name='code',
            field=models.CharField(max_length=64, blank=False, null=False),
        ),
    ]
