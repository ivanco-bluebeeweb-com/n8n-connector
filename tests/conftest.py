"""Shared fixtures for n8n Connector PST (Plausible Scenario Testing).

Mirrors the accepted pattern used by DataForSEO Connector / Media Studio:
imperal_sdk.testing.MockContext + MockSecretStore give us the REAL
handlers.py / n8n_client.py code path (real HTTP call construction, real
header names, real error mapping) against a controlled fake HTTP backend --
not a hand-rolled imitation of the logic itself.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def ctx():
    from imperal_sdk.testing import MockContext, MockSecretStore

    mock = MockContext()
    mock.secrets = MockSecretStore({})
    return mock


@pytest.fixture
def ctx_connected(ctx):
    """Same as `ctx` but with n8n credentials already saved -- the state
    every persona in SCENARIO_TESTS.md starts from except the brand-new
    user in the connection scenarios."""
    from imperal_sdk.testing import MockSecretStore
    ctx.secrets = MockSecretStore({
        "n8n_base_url": "https://n8n.acme-agency.example.com",
        "n8n_api_key": "n8n_api_test_key_5f3a9c",
    })
    return ctx
