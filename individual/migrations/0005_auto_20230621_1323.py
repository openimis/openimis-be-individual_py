# Generated by Django 3.2.19 on 2023-06-21 13:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('individual', '0004_add_group_rights_to_admin'),
    ]

    operations = [
        migrations.AlterField(
            model_name='group',
            name='json_ext',
            field=models.JSONField(db_column='Json_ext', default=dict),
        ),
        migrations.AlterField(
            model_name='historicalgroup',
            name='json_ext',
            field=models.JSONField(db_column='Json_ext', default=dict),
        ),
        migrations.AlterField(
            model_name='historicalindividual',
            name='json_ext',
            field=models.JSONField(db_column='Json_ext', default=dict),
        ),
        migrations.AlterField(
            model_name='individual',
            name='json_ext',
            field=models.JSONField(db_column='Json_ext', default=dict),
        ),
    ]
