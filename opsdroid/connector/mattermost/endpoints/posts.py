import logging
from .base import Base

_LOGGER = logging.getLogger(__name__)


class Posts(Base):
    endpoint = "/posts"

    async def create_post(self, options):
        _LOGGER.debug("Sending post with options '%s'", repr(options))
        return await self.post(self.endpoint, options=options)
