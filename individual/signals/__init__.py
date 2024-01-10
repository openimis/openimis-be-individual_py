import logging

from core.service_signals import ServiceSignalBindType
from core.signals import bind_service_signal
from individual.services import GroupIndividualService, IndividualService

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
