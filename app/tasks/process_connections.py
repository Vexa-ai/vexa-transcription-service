import logging

from aiomisc.service.periodic import PeriodicService

from app.services.audio.processor import Processor

logger = logging.getLogger(__name__)


class ProcessConnectionTask(PeriodicService):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__processor = Processor()

    async def callback(self):
        try:
            await self.__processor.process_connections()

        except Exception as ex:
            logger.exception(ex)
