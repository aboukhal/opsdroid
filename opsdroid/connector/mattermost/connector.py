"""A connector for Mattermost."""
import logging
import json

from voluptuous import Required

from opsdroid.connector import Connector, register_event
from opsdroid.events import Message

from .driver import Driver

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = {
    Required("token"): str,
    Required("url"): str,
    Required("team-name"): str,
    "scheme": str,
    "port": int,
    "ssl-verify": bool,
    "connect-timeout": int,
}


class ConnectorMattermost(Connector):
    """A connector for Mattermost."""

    def __init__(self, config, opsdroid=None):
        """Create the connector."""
        super().__init__(config, opsdroid=opsdroid)
        _LOGGER.debug(_("Starting Mattermost connector"))
        self.name = config.get("name", "mattermost")
        self._token = config["token"]
        self._url = config["url"]
        self._team_name = config["team-name"]
        self._scheme = config.get("scheme", "https")
        self._port = config.get("port", 8065)
        self._verify = config.get("ssl-verify", True)
        self._timeout = config.get("connect-timeout", 30)

        self._bot_id = None

        self._mm_driver = Driver(
            {
                "url": self._url,
                "token": self._token,
                "scheme": self._scheme,
                "port": self._port,
                "verify": self._verify,
                "timeout": self._timeout,
            }
        )

    async def connect(self):
        """Connect to the chat service."""
        _LOGGER.info(_("Connecting to Mattermost"))

        await self._mm_driver.__aenter__()
        login_response = await self._mm_driver.connect()

        body = await login_response.json()
        _LOGGER.info(
            "Mattermost responded with the identity of the token's user: '%s'",
            repr(body),
        )

        if "id" not in body:
            raise ValueError(
                "Mattermost response must contain our own client ID. Otherwise OpsDroid would respond to itself indefinitely."
            )
        self._bot_id = body["id"]

        if "username" in body:
            _LOGGER.info(_("Connected as %s"), body["username"])

        _LOGGER.info(_("Connected successfully"))

    async def disconnect(self):
        """Disconnect from Mattermost."""
        await self._mm_driver.__aexit__()

    async def listen(self):
        """Listen for and parse new messages."""
        await self._mm_driver.listen(self.process_message)

    async def process_message(self, raw_message):
        """Process a raw message and pass it to the parser."""
        _LOGGER.info(raw_message)

        message = json.loads(raw_message)

        if "event" in message and message["event"] == "posted":
            data = message["data"]
            post = json.loads(data["post"])
            # if connected to Mattermost, don't parse our own messages
            # (https://github.com/opsdroid/opsdroid/issues/1775)
            if self._bot_id != post["user_id"]:
                await self.opsdroid.parse(
                    Message(
                        text=post["message"],
                        user=data["sender_name"],
                        target=data["channel_name"],
                        connector=self,
                        raw_event=message,
                    )
                )

    @register_event(Message)
    async def send_message(self, message):
        """Respond with a message."""
        _LOGGER.debug(
            _("Responding with: '%s' in room  %s"), message.text, message.target
        )
        channel_id = self._mm_driver.channels.get_channel_by_name_and_team_name(
            self._team_name, message.target
        )["id"]
        self._mm_driver.posts.create_post(
            options={"channel_id": channel_id, "message": message.text}
        )
