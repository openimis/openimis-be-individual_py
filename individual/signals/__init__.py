import logging

from core.service_signals import ServiceSignalBindType
from core.signals import bind_service_signal
from individual.services import GroupIndividualService, IndividualService, CreateGroupAndMoveIndividualService, \
     GroupService
from individual.signals.on_validation_import_valid_items import on_task_complete_import_validated, on_task_resolve

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
        on_task_complete_service_handler(GroupService),
        bind_type=ServiceSignalBindType.AFTER
    )
    bind_service_signal(
        'task_service.complete_task',
        on_task_complete_service_handler(CreateGroupAndMoveIndividualService),
        bind_type=ServiceSignalBindType.AFTER
    )
    bind_service_signal(
        'task_service.complete_task',
        on_task_complete_import_validated,
        bind_type=ServiceSignalBindType.AFTER
    )
    bind_service_signal(
        'task_service.resolve_task',
        on_task_resolve,
        bind_type=ServiceSignalBindType.AFTER
    )
