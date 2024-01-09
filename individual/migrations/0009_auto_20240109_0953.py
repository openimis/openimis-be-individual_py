# Generated by Django 3.2.19 on 2024-01-09 09:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('individual', '0008_auto_20240105_1527'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicalindividualdatasourceupload',
            name='status',
            field=models.CharField(choices=[('PENDING', 'Pending'), ('TRIGGERED', 'Triggered'), ('IN_PROGRESS', 'In progress'), ('SUCCESS', 'Success'), ('WAITING_FOR_VERIFICATION', 'WAITING_FOR_VERIFICATION'), ('FAIL', 'Fail')], default='PENDING', max_length=255),
        ),
        migrations.AlterField(
            model_name='individualdatasourceupload',
            name='status',
            field=models.CharField(choices=[('PENDING', 'Pending'), ('TRIGGERED', 'Triggered'), ('IN_PROGRESS', 'In progress'), ('SUCCESS', 'Success'), ('WAITING_FOR_VERIFICATION', 'WAITING_FOR_VERIFICATION'), ('FAIL', 'Fail')], default='PENDING', max_length=255),
        ),
    ]
