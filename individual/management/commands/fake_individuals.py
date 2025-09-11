import csv
import json
from faker import Faker
from datetime import datetime, timedelta
import random
import json
import tempfile

from django.core.management.base import BaseCommand
from individual.apps import IndividualConfig
from individual.models import GroupIndividual
from individual.tests.test_helpers import generate_random_string
from location.models import Location
from core import filter_validity
from core.models import User

fake = Faker()
individual_schema = json.loads(IndividualConfig.individual_schema)['properties']

def generate_fake_individual(group_code, recipient_info, individual_role, location=None):
    required_info =  {
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "dob": fake.date_of_birth(minimum_age=16, maximum_age=90).isoformat(),
        "group_code": group_code,
        "recipient_info": recipient_info,
        "individual_role": individual_role,
        "location_name": location.name if location else "",
        "location_code": location.code if location else "",
    }

    others = {
        "email": fake.email(),
        "able_bodied": fake.boolean(),
        "national_id": fake.unique.ssn(),
        "national_id_type": fake.random_element(elements=("ID", "Passport", "Driver's License")),
        "educated_level": fake.random_element(elements=("primary", "secondary", "tertiary", "none")),
        "chronic_illness": fake.boolean(),
        "number_of_elderly": fake.random_int(min=0, max=5),
        "number_of_children": fake.random_int(min=0, max=10),
        "beneficiary_data_source": fake.company(),
    }

    allowed_fields = set(individual_schema.keys())

    return {
        **required_info,
        **{k: v for k, v in others.items() if k in allowed_fields}
    }

# Django management command to create a CSV file with fake individuals
class Command(BaseCommand):
    help = "Create test individual csv for uploading"

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help="Specify the username such that their permitted locations are assigned to individuals"
        )
        parser.add_argument(
            '--num-individuals',
            type=int,
            default=100,
            help="Number of individuals to generate (default: 100)"
        )
        parser.add_argument(
            '--num-groups',
            type=int,
            default=20,
            help=(
                "Number of groups to generate (default: 20). "
                "If set to 0, individuals will be generated without group-related fields "
                "(i.e., group_code, recipient_info, individual_role)."
            )
        )

    def handle(self, *args, **options):
        # Retrieves the user with the specified username
        username = options.get('username')
        user = User.objects.filter(username=username).first()

        # Gets the locations permitted for the user
        location_qs = Location.objects
        if user:
            location_qs = Location.get_queryset(location_qs, user)
        permitted_locations = list(location_qs.filter(type='V', *filter_validity()))

        individuals = []  # List to store fake individuals
        num_individuals = options.get('num_individuals')
        num_groups = options.get('num_groups')

        if num_groups > 0:
            # Exclude the HEAD role from available choices to ensure only one head per group
            available_role_choices = [choice for choice in GroupIndividual.Role if choice != GroupIndividual.Role.HEAD]

            base_count = num_individuals // num_groups
            remainder = num_individuals % num_groups

            # Generate individuals for each household/group
            for group_index in range(0, num_groups):
                group_code = generate_random_string()
                assign_location = random.choice([True] * 3 + [False])  # Randomly decide whether to assign a location
                location = random.choice(permitted_locations) if assign_location else None

                # Add one extra individual to groups while distributing the remainder
                group_size = base_count + (1 if group_index < remainder else 0)

                # Generate individuals for the current group
                for i in range(group_size):
                    recipient_info = 1 if i == 0 else 0  # Mark the first individual as a recipient
                    individual_role = GroupIndividual.Role.HEAD if i == 0 else random.choice(available_role_choices)
                    individual = generate_fake_individual(group_code, recipient_info, individual_role, location)
                    individuals.append(individual)
        else:
            for _ in range(num_individuals):
                assign_location = random.choice([True] * 3 + [False])
                location = random.choice(permitted_locations) if assign_location else None
                individual = generate_fake_individual(group_code=None, recipient_info=None, individual_role=None, location=location)
                # Remove group-specific fields
                for field in ['group_code', 'recipient_info', 'individual_role']:
                    individual.pop(field, None)
                individuals.append(individual)

        # Write the generated individuals to a temporary CSV file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='') as tmp_file:
            writer = csv.DictWriter(tmp_file, fieldnames=list(individuals[0].keys()))
            writer.writeheader()
            for individual in individuals:
                writer.writerow(individual)

            self.stdout.write(self.style.SUCCESS(f'Successfully created {num_individuals} fake individuals csv at {tmp_file.name}'))
