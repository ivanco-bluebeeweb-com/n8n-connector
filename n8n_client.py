"""n8n Public REST API client -- API-key auth against a user-supplied
base_url, and thin wrappers around the workflow/execution/credential
endpoints this connector exposes.

WHY NO ZONE/HOST DISCOVERY, UNLIKE make_client.py.

Make.com has a small fixed set of public zone hosts to probe. n8n has no
such set: a self-hosted instance can live at any host:port/path the user
deployed it to, and n8n Cloud gives each account its own subdomain. Per
n8n's own docs (docs.n8n.io/connect/n8n-api/authentication), every
request goes to `<base_url>/api/v1/...` where base_url is entirely
instance-specific -- so the user supplies it directly (PREPARATION.md
section 4, answer 2), and this client just normalises it (strips a
trailing slash) rather than guessing it.

WHY `X-N8N-API-KEY: <key>`, NOT Bearer/Basic/`Token ...`.

n8n's docs are explicit about this exact header name -- confirmed
2026-08-18 against docs.n8n.io/connect/n8n-api/authentication.

WHY 401 vs 403 ARE HANDLED DIFFERENTLY, SAME REASONING AS make_client.py.

A 401 means this base_url/key pair is not recognised at all (wrong URL,
wrong key, or instance unreachable under that path). A 403 means the key
IS recognised by this instance, but lacks the scope for the specific
operation being called (n8n Cloud/Enterprise instances can issue
scope-restricted keys, per docs.n8n.io/connect/n8n-api/authentication
"API Scopes" section) -- a materially different, more specific and more
fixable cause that must not be reported as "wrong key".
"""
from __future__ import annotations

API_VERSION = "v1"


class ProviderError(Exception):
    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


def _normalize_base_url(base_url: str) -> str:
    return base_url.strip().rstrip("/")


def _headers(api_key: str) -> dict:
    return {"X-N8N-API-KEY": api_key, "Accept": "application/json"}


def _api(base_url: str, path: str) -> str:
    return f"{_normalize_base_url(base_url)}/api/{API_VERSION}{path}"


def _error_detail(resp) -> str:
    try:
        body = resp.body if isinstance(resp.body, dict) else {}
    except Exception:
        body = {}
    return body.get("message") or ""


def _check_status(resp, action: str):
    if resp.status_code == 401:
        raise ProviderError(
            f"n8n rejected the request to {action}: the API key or base URL "
            "isn't recognised by this instance. Check that the base URL is "
            "correct (no typo, right instance) and that the key hasn't been "
            "deleted in n8n's Settings -> n8n API.",
            "N8N_AUTH_ERROR",
        )
    if resp.status_code == 403:
        detail = _error_detail(resp)
        raise ProviderError(
            f"n8n recognised your key for {action}, but it's missing the "
            "required scope." + (f" ({detail})" if detail else "") +
            " Fix: in your n8n instance, go to Settings -> n8n API, and "
            "either create a new key with the needed scope checked, or use "
            "an unrestricted key (scopes are an n8n Cloud/Enterprise "
            "feature -- Community edition keys aren't scope-restricted).",
            "N8N_SCOPE_ERROR",
        )
    if resp.status_code == 404:
        raise ProviderError(f"Not found while trying to {action}.", "N8N_NOT_FOUND")
    if resp.status_code >= 400:
        detail = _error_detail(resp)
        raise ProviderError(
            f"n8n returned an error while trying to {action}"
            f"{f': {detail}' if detail else f' (HTTP {resp.status_code})'}.",
            "N8N_API_ERROR",
        )
    body = resp.body
    return body if isinstance(body, dict) else {}


async def check_connection(ctx, base_url: str, api_key: str) -> dict:
    """GET /workflows?limit=1 -- cheap, side-effect-free call used both to
    validate a freshly entered key/URL pair before saving it, and to
    surface a real n8n-shaped error (401 vs 403) instead of a generic
    network failure."""
    resp = await ctx.http.get(
        _api(base_url, "/workflows"), headers=_headers(api_key), params={"limit": 1},
    )
    return _check_status(resp, "verify connection")


# ──────────────────────────────────────────────────────────────────────────
# Workflows
# ──────────────────────────────────────────────────────────────────────────


async def list_workflows(
    ctx, base_url: str, api_key: str, *,
    active: bool | None = None, tags: str | None = None,
    limit: int = 50, cursor: str | None = None,
) -> tuple[list[dict], str | None]:
    params: dict = {"limit": limit}
    if active is not None:
        params["active"] = active
    if tags:
        params["tags"] = tags
    if cursor:
        params["cursor"] = cursor
    resp = await ctx.http.get(
        _api(base_url, "/workflows"), headers=_headers(api_key), params=params,
    )
    body = _check_status(resp, "list workflows")
    return body.get("data") or [], body.get("nextCursor")


async def get_workflow(ctx, base_url: str, api_key: str, workflow_id: str) -> dict:
    resp = await ctx.http.get(
        _api(base_url, f"/workflows/{workflow_id}"), headers=_headers(api_key),
    )
    return _check_status(resp, "get workflow")


async def create_workflow(ctx, base_url: str, api_key: str, payload: dict) -> dict:
    resp = await ctx.http.post(
        _api(base_url, "/workflows"),
        headers={**_headers(api_key), "Content-Type": "application/json"},
        json=payload,
    )
    return _check_status(resp, "create workflow")


async def update_workflow(ctx, base_url: str, api_key: str, workflow_id: str, payload: dict) -> dict:
    """PUT /workflows/{id} -- n8n replaces the whole entity, unlike a
    typical PATCH. Callers MUST read-merge-write (see PREPARATION.md
    section 3, decision 7) -- this function does not do the merge itself,
    it only sends whatever payload it's given."""
    resp = await ctx.http.put(
        _api(base_url, f"/workflows/{workflow_id}"),
        headers={**_headers(api_key), "Content-Type": "application/json"},
        json=payload,
    )
    return _check_status(resp, "update workflow")


async def delete_workflow(ctx, base_url: str, api_key: str, workflow_id: str) -> dict:
    resp = await ctx.http.delete(
        _api(base_url, f"/workflows/{workflow_id}"), headers=_headers(api_key),
    )
    return _check_status(resp, "delete workflow")


async def publish_workflow(ctx, base_url: str, api_key: str, workflow_id: str) -> dict:
    """POST /workflows/{id}/publish -- the current (non-deprecated) way to
    make a workflow active, per n8n issue #34745. Do NOT use the older
    `active: true` PATCH-style activate/deactivate path -- deprecated per
    n8n issue #34771 (PREPARATION.md section 2)."""
    resp = await ctx.http.post(
        _api(base_url, f"/workflows/{workflow_id}/publish"), headers=_headers(api_key),
    )
    return _check_status(resp, "publish workflow")


async def unpublish_workflow(ctx, base_url: str, api_key: str, workflow_id: str) -> dict:
    resp = await ctx.http.post(
        _api(base_url, f"/workflows/{workflow_id}/unpublish"), headers=_headers(api_key),
    )
    return _check_status(resp, "unpublish workflow")


async def run_workflow(ctx, base_url: str, api_key: str, workflow_id: str, data: dict | None = None) -> dict:
    """POST /workflows/{id}/execute -- a recent addition to n8n's public
    API (added in PRs #23435/#20234, late 2025). Older self-hosted
    instances may not have this route yet; callers should treat a 404
    here as "this instance's n8n version doesn't support manual run via
    API yet", not a generic failure (PREPARATION.md section 5.2)."""
    resp = await ctx.http.post(
        _api(base_url, f"/workflows/{workflow_id}/execute"),
        headers={**_headers(api_key), "Content-Type": "application/json"},
        json=data or {},
    )
    if resp.status_code == 404:
        raise ProviderError(
            "This n8n instance doesn't support running a workflow directly "
            "via the API (the /execute endpoint isn't available -- likely "
            "an older n8n version). Trigger it via its Webhook node URL "
            "instead, or upgrade the instance.",
            "N8N_RUN_UNSUPPORTED",
        )
    return _check_status(resp, "run workflow")


# ──────────────────────────────────────────────────────────────────────────
# Executions
# ──────────────────────────────────────────────────────────────────────────


async def list_executions(
    ctx, base_url: str, api_key: str, *,
    status: str | None = None, workflow_id: str | None = None,
    limit: int = 50, cursor: str | None = None,
) -> tuple[list[dict], str | None]:
    params: dict = {"limit": limit}
    if status:
        params["status"] = status
    if workflow_id:
        params["workflowId"] = workflow_id
    if cursor:
        params["cursor"] = cursor
    resp = await ctx.http.get(
        _api(base_url, "/executions"), headers=_headers(api_key), params=params,
    )
    body = _check_status(resp, "list executions")
    return body.get("data") or [], body.get("nextCursor")


async def get_execution(ctx, base_url: str, api_key: str, execution_id: int) -> dict:
    resp = await ctx.http.get(
        _api(base_url, f"/executions/{execution_id}"), headers=_headers(api_key),
    )
    return _check_status(resp, "get execution")


async def delete_execution(ctx, base_url: str, api_key: str, execution_id: int) -> dict:
    resp = await ctx.http.delete(
        _api(base_url, f"/executions/{execution_id}"), headers=_headers(api_key),
    )
    return _check_status(resp, "delete execution")


async def retry_execution(ctx, base_url: str, api_key: str, execution_id: int) -> dict:
    """POST /executions/{id}/retry -- confirmed per docs.n8n.io/connect/
    n8n-api/execution outline (2026-08-18)."""
    resp = await ctx.http.post(
        _api(base_url, f"/executions/{execution_id}/retry"), headers=_headers(api_key),
    )
    return _check_status(resp, "retry execution")


async def stop_execution(ctx, base_url: str, api_key: str, execution_id: int) -> dict:
    resp = await ctx.http.post(
        _api(base_url, f"/executions/{execution_id}/stop"), headers=_headers(api_key),
    )
    return _check_status(resp, "stop execution")


async def stop_executions(ctx, base_url: str, api_key: str, execution_ids: list[int]) -> dict:
    resp = await ctx.http.post(
        _api(base_url, "/executions/stop"),
        headers={**_headers(api_key), "Content-Type": "application/json"},
        json={"ids": execution_ids},
    )
    return _check_status(resp, "stop multiple executions")


# ──────────────────────────────────────────────────────────────────────────
# Credentials -- FULL ACCESS per Vlad's decision (PREPARATION.md section 4,
# answer 3). NOTE: n8n's Public API only supports get-schema/create/delete
# for credentials -- there is NO update/PATCH endpoint (confirmed via n8n
# community post 2024-12-30 + openapi.yml). To "change" a credential, the
# user must delete and recreate it -- this is a limitation of n8n itself,
# not of this connector, and must be explained in the tool description
# rather than left as a silent gap.
# ──────────────────────────────────────────────────────────────────────────


async def list_credentials(ctx, base_url: str, api_key: str) -> list[dict]:
    resp = await ctx.http.get(
        _api(base_url, "/credentials"), headers=_headers(api_key),
    )
    body = _check_status(resp, "list credentials")
    return body.get("data") or []


async def get_credential_schema(ctx, base_url: str, api_key: str, credential_type_name: str) -> dict:
    resp = await ctx.http.get(
        _api(base_url, f"/credentials/schema/{credential_type_name}"), headers=_headers(api_key),
    )
    return _check_status(resp, "get credential schema")


async def create_credential(ctx, base_url: str, api_key: str, payload: dict) -> dict:
    resp = await ctx.http.post(
        _api(base_url, "/credentials"),
        headers={**_headers(api_key), "Content-Type": "application/json"},
        json=payload,
    )
    return _check_status(resp, "create credential")


async def delete_credential(ctx, base_url: str, api_key: str, credential_id: str) -> dict:
    resp = await ctx.http.delete(
        _api(base_url, f"/credentials/{credential_id}"), headers=_headers(api_key),
    )
    return _check_status(resp, "delete credential")


# ──────────────────────────────────────────────────────────────────────────
# Tags
# ──────────────────────────────────────────────────────────────────────────


async def list_tags(ctx, base_url: str, api_key: str, *, limit: int = 50, cursor: str | None = None) -> tuple[list[dict], str | None]:
    params: dict = {"limit": limit}
    if cursor:
        params["cursor"] = cursor
    resp = await ctx.http.get(
        _api(base_url, "/tags"), headers=_headers(api_key), params=params,
    )
    body = _check_status(resp, "list tags")
    return body.get("data") or [], body.get("nextCursor")


async def create_tag(ctx, base_url: str, api_key: str, name: str) -> dict:
    resp = await ctx.http.post(
        _api(base_url, "/tags"),
        headers={**_headers(api_key), "Content-Type": "application/json"},
        json={"name": name},
    )
    return _check_status(resp, "create tag")


async def delete_tag(ctx, base_url: str, api_key: str, tag_id: str) -> dict:
    resp = await ctx.http.delete(
        _api(base_url, f"/tags/{tag_id}"), headers=_headers(api_key),
    )
    return _check_status(resp, "delete tag")
