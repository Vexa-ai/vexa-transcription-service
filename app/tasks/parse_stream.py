import logging
import asyncio
from aiomisc import entrypoint

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


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Create the service with a desired interval (e.g., 1 second)
    service = ProcessConnectionTask(interval=1)
    
    # Run the service using aiomisc entrypoint
    with entrypoint(service) as loop:
        loop.run_forever()
