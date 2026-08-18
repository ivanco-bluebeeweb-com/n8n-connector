"""Chat functions for n8n Connector -- Срез 1 (connection) only.

Workflow/execution/credential lists land in Срез 2+ per PREPARATION.md's
Фаза 2 plan -- this file intentionally stops at connect/disconnect/status
so this slice stays live-verifiable on its own before the next is built,
same discipline as Make.com Connector's handlers.py.
"""
from __future__ import annotations

from imperal_sdk import ActionResult

import n8n_client as nc
from app import ext, chat
from schemas import NoParams, ConnectN8nParams, ProviderConnection


async def _get_credentials(ctx) -> tuple[str, str]:
    """Returns (base_url, api_key). Either empty means "not connected"."""
    base_url = await ctx.secrets.get("n8n_base_url")
    api_key = await ctx.secrets.get("n8n_api_key")
    return base_url or "", api_key or ""


# ──────────────────────────────────────────────────────────────────────────
# Connection / account management
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "connect_n8n",
    "Connect your n8n instance by saving its base URL and your own API "
    "key, after checking they actually work together. Create the key in "
    "your instance: Settings -> n8n API -> Create an API key. Works for "
    "both self-hosted n8n and n8n Cloud -- just paste your instance's own "
    "URL, there's no auto-detection since n8n has no fixed set of hosts "
    "the way Make.com does.",
    action_type="write",
    chain_callable=True,
    data_model=ProviderConnection,
    event="n8n-connector.connect_n8n",
    effects=["n8n.provider.connected"],
)
async def connect_n8n(ctx, params: ConnectN8nParams) -> ActionResult:
    """Validate base_url+api_key against the user's own n8n instance, then
    persist both as secrets so every later call reuses them."""
    base_url = params.base_url.strip().rstrip("/")
    api_key = params.api_key.strip()
    if not base_url:
        return ActionResult.error(
            "Please provide your n8n instance's base URL (e.g. "
            "https://n8n.example.com or https://your-org.app.n8n.cloud).",
            code="N8N_MISSING_BASE_URL",
        )
    if not api_key:
        return ActionResult.error(
            "Please provide your n8n API key -- create one in your "
            "instance: Settings -> n8n API -> Create an API key.",
            code="N8N_MISSING_API_KEY",
        )
    try:
        await nc.verify_credentials(ctx, base_url, api_key)
    except nc.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)

    await ctx.secrets.set("n8n_base_url", base_url)
    await ctx.secrets.set("n8n_api_key", api_key)
    return ActionResult.success(
        ProviderConnection(connected=True, detail=f"Connected ({base_url})"),
        summary=f"n8n connected -- {base_url}.",
        refresh_panels=["n8n_connect"],
    )


@chat.function(
    "disconnect_n8n",
    "Disconnect n8n: deletes the saved base URL and API key. Existing "
    "workflows/executions on your own n8n instance are untouched.",
    action_type="write",
    chain_callable=True,
    data_model=ProviderConnection,
    event="n8n-connector.disconnect_n8n",
    effects=["n8n.provider.disconnected"],
)
async def disconnect_n8n(ctx, params: NoParams) -> ActionResult:
    """Delete the saved base_url/api_key secrets. Nothing on the user's own
    n8n instance is touched -- only this connector forgets them."""
    await ctx.secrets.delete("n8n_base_url")
    await ctx.secrets.delete("n8n_api_key")
    return ActionResult.success(
        ProviderConnection(connected=False, detail="Not connected"),
        summary="n8n disconnected.",
        refresh_panels=["n8n_connect"],
    )


@chat.function(
    "get_n8n_connection",
    "Check whether n8n is currently connected (does not reveal the saved "
    "base URL or API key).",
    action_type="read",
    data_model=ProviderConnection,
)
async def get_n8n_connection(ctx, params: NoParams) -> ActionResult:
    """Read-only status check -- never returns the saved base_url/api_key
    values themselves, only whether a pair is currently stored."""
    base_url, api_key = await _get_credentials(ctx)
    connected = bool(base_url and api_key)
    return ActionResult.success(
        ProviderConnection(
            connected=connected,
            detail=f"Connected ({base_url})" if connected else "Not connected -- run connect_n8n",
        ),
        summary="n8n is connected." if connected else "n8n is not connected.",
    )
