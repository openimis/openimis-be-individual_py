# Generated by Django 3.2.20 on 2023-07-24 13:55

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('individual', '0007_auto_20230630_0950'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='historicalindividualdatasourceupload',
            name='individual',
        ),
        migrations.RemoveField(
            model_name='individualdatasourceupload',
            name='individual',
        ),
    ]
