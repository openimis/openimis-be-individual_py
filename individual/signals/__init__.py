import logging

from core.service_signals import ServiceSignalBindType
from core.signals import bind_service_signal
from individual.services import GroupIndividualService, IndividualService, CreateGroupAndMoveIndividualService, \
    group_on_task_complete_service_handler
from individual.signals.on_validation_import_valid_items import on_task_complete_validation_individual_import_valid_items
from individual.signals.on_individuals_data_upload import on_individuals_data_upload

from tasks_management.services import on_task_complete_service_handler

logger = logging.getLogger(__name__)


def bind_service_signals():
    bind_service_signal(
        'task_service.complete_task',
        on_task_complete_service_handler(GroupIndividualService),
        bind_type=ServiceSignalBindType.AFTER
    )
    bind_service_signal(
        'task_service.complete_task',
        on_task_complete_service_handler(IndividualService),
        bind_type=ServiceSignalBindType.AFTER
    )
    bind_service_signal(
        'task_service.complete_task',
        group_on_task_complete_service_handler(CreateGroupAndMoveIndividualService),
        bind_type=ServiceSignalBindType.AFTER
    )
    bind_service_signal(
        'task_service.complete_task',
        on_task_complete_validation_individual_import_valid_items,
        bind_type=ServiceSignalBindType.AFTER
    )
    bind_service_signal(
        'individual.import_individuals',
        on_individuals_data_upload,
        bind_type=ServiceSignalBindType.AFTER
    )
