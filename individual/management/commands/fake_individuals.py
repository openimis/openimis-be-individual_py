import csv
from faker import Faker
from datetime import datetime, timedelta
import random
import json
import tempfile

from django.core.management.base import BaseCommand

fake = Faker()

json_schema = {
    "email": {"type": "string"},
    "able_bodied": {"type": "boolean"},
    "national_id": {"type": "string"},
    "educated_level": {"type": "string"},
    "chronic_illness": {"type": "boolean"},
    "national_id_type": {"type": "string"},
    "number_of_elderly": {"type": "integer"},
    "number_of_children": {"type": "integer"},
    "beneficiary_data_source": {"type": "string"}
}

def generate_fake_individual(group_code, recipient_info):
    return {
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "dob": fake.date_of_birth(minimum_age=16, maximum_age=90).isoformat(),
        "group_code": group_code,
        "recipient_info": recipient_info,
        "email": fake.email(),
        "able_bodied": fake.boolean(),
        "national_id": fake.unique.ssn(),
        "national_id_type": fake.random_element(elements=("ID", "Passport", "Driver's License")),
        "educated_level": fake.random_element(elements=("primary", "secondary", "tertiary", "none")),
        "chronic_illness": fake.boolean(),
        "number_of_elderly": fake.random_int(min=0, max=5),
        "number_of_children": fake.random_int(min=0, max=10),
        "beneficiary_data_source": fake.company()
    }



class Command(BaseCommand):
    help = "Create test individual csv for uploading"

    def handle(self, *args, **options):
        individuals = []
        num_individuals = 100
        num_households = 20

        for group_code in range(1, num_households+1):
            for i in range(num_individuals // num_households):
                recipient_info = 1 if i == 0 else 0
                individual = generate_fake_individual(group_code, recipient_info)
                individuals.append(individual)

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='') as tmp_file:
            writer = csv.DictWriter(tmp_file, fieldnames=list(individuals[0].keys()))
            writer.writeheader()
            for individual in individuals:
                writer.writerow(individual)

            self.stdout.write(self.style.SUCCESS(f'Successfully created {num_individuals} fake individuals csv at {tmp_file.name}'))

