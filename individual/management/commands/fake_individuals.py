import csv
from faker import Faker
from datetime import datetime, timedelta
import random
import json
import tempfile

from django.core.management.base import BaseCommand
from individual.models import GroupIndividual
from individual.tests.test_helpers import generate_random_string
from location.models import Location
from core import filter_validity
from core.models import User


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

def generate_fake_individual(group_code, recipient_info, individual_role, location=None):
    return {
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "dob": fake.date_of_birth(minimum_age=16, maximum_age=90).isoformat(),
        "group_code": group_code,
        "recipient_info": recipient_info,
        "individual_role": individual_role,
        "email": fake.email(),
        "able_bodied": fake.boolean(),
        "national_id": fake.unique.ssn(),
        "national_id_type": fake.random_element(elements=("ID", "Passport", "Driver's License")),
        "educated_level": fake.random_element(elements=("primary", "secondary", "tertiary", "none")),
        "chronic_illness": fake.boolean(),
        "number_of_elderly": fake.random_int(min=0, max=5),
        "number_of_children": fake.random_int(min=0, max=10),
        "beneficiary_data_source": fake.company(),
        "location_name": location.name if location else "",
        "location_code": location.code if location else "",
    }



class Command(BaseCommand):
    help = "Create test individual csv for uploading"

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help="Specify the username such that their permitted locations are assigned to individuals"
        )

    def handle(self, *args, **options):
        username = options.get('username')
        user = User.objects.filter(username=username).first()
        location_qs = Location.objects
        if user:
            location_qs = Location.get_queryset(location_qs, user)
        permitted_locations = list(location_qs.filter(type='V', *filter_validity()))

        individuals = []
        num_individuals = 100
        num_households = 20

        # Exclude the head from role choices so that one group only has one head in randomnes
        available_role_choices = [choice for choice in GroupIndividual.Role if choice != GroupIndividual.Role.HEAD]

        for group_index in range(0, num_households):
            group_code = generate_random_string()
            assign_location = random.choice([True, False])
            location = random.choice(permitted_locations) if assign_location else None

            for i in range(num_individuals // num_households):
                recipient_info = 1 if i == 0 else 0
                individual_role = GroupIndividual.Role.HEAD if i == 0 else random.choice(available_role_choices)
                individual = generate_fake_individual(group_code, recipient_info, individual_role, location)
                individuals.append(individual)

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='') as tmp_file:
            writer = csv.DictWriter(tmp_file, fieldnames=list(individuals[0].keys()))
            writer.writeheader()
            for individual in individuals:
                writer.writerow(individual)

            self.stdout.write(self.style.SUCCESS(f'Successfully created {num_individuals} fake individuals csv at {tmp_file.name}'))

