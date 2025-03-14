import asyncio
import logging
import aiohttp
from typing import Coroutine, Callable, Any
from .endpoints.channels import Channels
from .endpoints.posts import Posts
from .endpoints.teams import Teams
from .endpoints.users import Users

_LOGGER = logging.getLogger(__name__)


class Driver:
    """
    Contains the client, api and provides you with functions for
    login, logout and initializing a websocket connection.
    """

    _default_options = {
        "scheme": "https",
        "url": "localhost",
        "port": 8065,
        "basepath": "/api/v4",
        "verify": True,
        "timeout": 30,
        "request_timeout": None,
        "login_id": None,
        "password": None,
        "token": None,
        "mfa_token": None,
        "auth": None,
        "keepalive": False,
        "keepalive_delay": 5,
        "websocket_kw_args": None,
        "debug": False,
        "http2": False,
        "proxy": None,
    }
    """
    Required options
        - url

    Either
        - login_id
        - password

    Or
        - token (https://docs.mattermost.com/developer/personal-access-tokens.html)

    Optional
        - scheme ('https')
        - port (8065)
        - verify (True)
        - timeout (30)
        - request_timeout (None)
        - mfa_token (None)
        - auth (None)
        - debug (False)

    Should not be changed
        - basepath ('/api/v4') - unlikely this would do any good
    """

    def __init__(self, options):
        """
        :param options: A dict with the values from `default_options`
        :type options: dict
        """
        self._options = self._default_options.copy()
        if options is not None:
            self._options.update(options)

        self._client = aiohttp.ClientSession(raise_for_status=True, trust_env=True)

    async def connect(self):
        """Connects the driver to the server, starting the websocket event loop."""

        self._client.headers["Authorization"] = "Bearer {token:s}".format(
            token=self._options["token"]
        )
        return await self.users.get_user("me")

    async def listen(self, event_handler: Callable[[str], Coroutine[Any, Any, None]]):
        await self.init_websocket(event_handler)

    def build_base_url(self):
        return "{scheme:s}://{url:s}:{port:s}{basepath:s}".format(
            scheme=self._options["scheme"],
            url=self._options["url"],
            port=str(self._options["port"]),
            basepath=self._options["basepath"],
        )

    @property
    def teams(self):
        """
        Api endpoint for teams

        :return: Instance of :class:`~endpoints.teams.Teams`
        """
        return Teams(self._client, self.build_base_url())

    @property
    def channels(self):
        """
        Api endpoint for channels

        :return: Instance of :class:`~endpoints.channels.Channels`
        """
        return Channels(self._client, self.build_base_url())

    @property
    def posts(self):
        """
        Api endpoint for posts

        :return: Instance of :class:`~endpoints.posts.Posts`
        """
        return Posts(self._client, self.build_base_url())

    @property
    def users(self):
        """
        Api endpoint for users

        :return: Instance of :class:`~endpoints.users.Users`
        """
        return Users(self._client, self.build_base_url())

    async def __aenter__(self):
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *exc_info):
        return await self._client.__aexit__(*exc_info)

    async def init_websocket(
        self, event_handler: Callable[[str], Coroutine[Any, Any, None]]
    ):
        """
        Will initialize the websocket connection to the mattermost server.
        assumes you are async aware and returns a coroutine that can be awaited.
        It will not return until shutdown() is called.

        This should be run after login(), because the websocket needs to make
        an authentification.

        See https://api.mattermost.com/v4/#tag/WebSocket for which
        websocket events mattermost sends.

        Example of a really simple event_handler function

        .. code:: python

                async def my_event_handler(message):
                        print(message)


        :param event_handler: The function to handle the websocket events. Takes one argument.
        :type event_handler: Function(message)
        :return: coroutine
        """
        while not self._client.closed:
            try:
                await self._websocket_loop(event_handler)
            except ValueError:
                raise
            except aiohttp.WebSocketError as ex:
                _LOGGER.info(
                    "Mattermost: An exception occured in the Websocket: '%s'", repr(ex)
                )
            except Exception as ex:
                _LOGGER.error(
                    "Mattermost: An unexpected exception occured in the Websocket: '%s'",
                    repr(ex),
                )

    async def _websocket_loop(
        self, event_handler: Callable[[str], Coroutine[Any, Any, None]]
    ):
        if self._options["scheme"] == "https":
            scheme = "wss"
        elif self._options["scheme"] == "http":
            scheme = "ws"
        else:
            raise ValueError(
                "Mattermost invalid scheme '%s'. Only 'http' and 'https' are supported!"
            )

        url = "{scheme:s}://{url:s}:{port:s}{basepath:s}/websocket".format(
            scheme=scheme,
            url=self._options["url"],
            port=str(self._options["port"]),
            basepath=self._options["basepath"],
        )

        async with self._client.ws_connect(
            url=url,
            autoping=True,
            heartbeat=self._options["timeout"],
        ) as websocket:
            websocket.send_json(
                {
                    "seq": 1,
                    "action": "authentication_challenge",
                    "data": {"token": self._options["token"]},
                }
            )
            while not websocket.closed and not self._client.closed:
                message = await websocket.receive_json()
                _LOGGER.debug("Mattermost received message: '%s'", repr(message))
                # We want to pass the events to the event_handler already
                # because the hello event could arrive before the authentication ok response
                await event_handler(message)
                if "seq" in message and message["seq"] == 0:
                    if "event" in message and message["event"] == "hello":
                        _LOGGER.info("Mattermost Websocket authentification OK")
                    else:
                        _LOGGER.error("Mattermost Websocket authentification failed")
                        break

        return await asyncio.sleep(0)  # allow for graceful websocket removal
