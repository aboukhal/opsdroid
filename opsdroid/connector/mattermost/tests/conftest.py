"""Fixtures and functions for slack testsuite."""

from pathlib import Path
from ..connector import ConnectorMattermost

import pytest
import typing
import re


def get_path(file_name: str) -> str:
    """Return current path for the requested file_name."""

    return Path(__file__).parent / "responses" / file_name


@pytest.fixture
async def connector(opsdroid, mock_api_obj):
    """Initiate a basic connector setup for testing on."""
    segments = re.split(r":/?/?", mock_api_obj.base_url)

    opsdroid.config["connectors"] = {
        "mattermost": {
            "token": "abc123",
            "url": segments[1],
            "team-name": "opsdroid",
            "scheme": segments[0],
            "port": segments[2],
        }
    }

    await opsdroid.load()
    connector = typing.cast(ConnectorMattermost, opsdroid.get_connector("mattermost"))

    return connector
