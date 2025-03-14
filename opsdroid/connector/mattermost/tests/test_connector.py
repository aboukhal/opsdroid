"""Tests for the ConnectorMattermost class."""
import pytest
import aiohttp.client_exceptions

from .conftest import get_path

pytestmark = pytest.mark.anyio

USER_ME_SUCCESS = ("/api/v4/users/me", "GET", get_path("users.me.success.json"), 200)
USER_ME_ERROR = ("/api/v4/users/me", "GET", None, 401)


@pytest.fixture
async def send_event(connector, mock_api):
    """Mock a send opsdroid event and return payload used and response from the request"""

    async def _send_event(api_call, event):
        api_endpoint, *_ = api_call
        response = await connector.send(event)
        payload = mock_api.get_payload(api_endpoint)

        return payload, response

    return _send_event


@pytest.mark.add_response(*USER_ME_SUCCESS)
async def test_api_key_success(connector, mock_api):
    """Test that creating without an API key raises an error."""
    await connector.connect()

    assert connector._bot_id == "test1234"


@pytest.mark.add_response(*USER_ME_ERROR)
async def test_api_key_failure(connector, mock_api):
    """Test that using an API key that Mattermost declares as Unauthorized, raises an error."""
    try:
        await connector.connect()
    except aiohttp.client_exceptions.ClientResponseError as ex:
        assert ex.status == 401

    assert connector._bot_id is None
