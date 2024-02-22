import copy
import logging

from django.db import transaction

from core.models import User
from individual.models import IndividualDataSourceUpload, IndividualDataSource, Group, Individual, GroupIndividual

logger = logging.getLogger(__name__)

_group_label_field = 'hhid'
_group_head_field = 'hh_head'
_full_name_field = 'nome'
_dob_field = 'data_de_nascimento'


def example_import_individual_workflow(*args, user_uuid=None, upload_uuid=None, **kwargs):
    try:
        with transaction.atomic():
            user = User.objects.get(id=user_uuid)

            upload = IndividualDataSourceUpload.objects.get(id=upload_uuid)
            upload.status = IndividualDataSourceUpload.Status.TRIGGERED
            upload.save(username=user.username)

            rows = IndividualDataSource.objects.filter(upload=upload)
            groups = {}

            for row in rows:
                data = copy.deepcopy(row.json_ext)
                group_label = data.pop(_group_label_field)

                group = groups.get(group_label, None)
                if not group:
                    group = Group()
                    group.save(username=user.username)
                    groups[group_label] = group

                first_name, last_name = data.pop(_full_name_field).split(' ', 1)
                dob = data.pop(_dob_field)
                is_head = data.pop(_group_head_field)

                individual = Individual(first_name=first_name, last_name=last_name, dob=dob, json_ext=data)
                individual.save(username=user.username)

                group_individual = GroupIndividual(group=group, individual=individual)
                if is_head:
                    group_individual.role = GroupIndividual.Role.HEAD
                group_individual.save(username=user.username)

                row.individual = individual
                row.save(username=user.username)

            upload.status = IndividualDataSourceUpload.Status.SUCCESS
            upload.save(username=user.username)
    except Exception as exc:
        logger.error("Error in import_individual_workflow", exc_info=exc)
        raise
