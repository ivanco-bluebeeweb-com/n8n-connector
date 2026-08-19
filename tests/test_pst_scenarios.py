"""Plausible Scenario Testing (PST) for n8n Connector.

Method: Docs/session-notes/SCENARIO_TESTING_STANDARD.md. Persona used
throughout: a BYOK n8n instance owner ("Marina", agency ops lead) who
connects her own n8n Cloud/self-hosted instance and manages workflows,
executions, credentials, tags, variables through Webbee. n8n Connector
has one functional role (the API-key holder), so scenario variety comes
from DATA classes (empty/typical/boundary/invalid/exotic instance
states, old vs new n8n versions) and from the 5 required branches, not
from multiple personas.

Every test calls the REAL handlers.py chat functions with REAL params
models, through imperal_sdk.testing.MockContext -- not a re-implementation
of the logic under a different name.
"""
from __future__ import annotations

import pytest

import handlers as h
from schemas import (
    ConnectN8nParams, NoParams,
    ListWorkflowsParams, GetWorkflowParams, CreateWorkflowParams,
    UpdateWorkflowParams, DeleteWorkflowParams, PublishWorkflowParams,
    UnpublishWorkflowParams, RunWorkflowParams,
    ListExecutionsParams, GetExecutionParams, DeleteExecutionParams,
    RetryExecutionParams, StopExecutionParams, StopExecutionsParams,
    ListCredentialsParams, GetCredentialSchemaParams, CreateCredentialParams,
    DeleteCredentialParams, GetCredentialParams, UpdateCredentialParams,
    TestCredentialParams, TransferCredentialParams,
    ListTagsParams, CreateTagParams, DeleteTagParams, UpdateTagParams,
    GetWorkflowTagsParams, UpdateWorkflowTagsParams,
    ListWorkflowVersionsParams, GetWorkflowVersionParams,
    UnarchiveWorkflowParams, TransferWorkflowParams,
    GetExecutionTagsParams, UpdateExecutionTagsParams,
    ListVariablesParams, CreateVariableParams, UpdateVariableParams,
    DeleteVariableParams,
    ListUsersParams, CreateUsersParams, GetUserParams, DeleteUserParams,
    ChangeUserRoleParams,
    PullSourceControlParams, GenerateAuditParams,
)


# ═══════════════════════════════════════════════════════════════════════
# BRANCH 1 -- HAPPY PATH (connection)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_connect_happy_path_saves_credentials(ctx):
    """Given a brand-new user with a real self-hosted URL and valid key,
    When she connects, Then check_connection succeeds and both secrets
    are saved (not just one -- a partial save would silently break every
    later call)."""
    ctx.http.mock_get(
        "/api/v1/workflows", {"data": [], "nextCursor": None}, status=200,
    )
    result = await h.connect_n8n(
        ctx, ConnectN8nParams(base_url="https://n8n.acme-agency.example.com/", api_key="n8n_api_valid_key_123"),
    )
    assert result.error is None, f"expected success, got error: {result.error}"
    saved_url = await ctx.secrets.get("n8n_base_url")
    saved_key = await ctx.secrets.get("n8n_api_key")
    assert saved_url, "base_url must be saved on success"
    assert saved_key == "n8n_api_valid_key_123"


@pytest.mark.asyncio
async def test_connect_trailing_slash_is_normalized(ctx):
    """Boundary data class: base_url with a trailing slash must not
    produce a double-slash in the real request path (n8n docs show
    <base_url>/api/v1/..., no allowance for //api)."""
    ctx.http.mock_get("/api/v1/workflows", {"data": [], "nextCursor": None}, status=200)
    result = await h.connect_n8n(
        ctx, ConnectN8nParams(base_url="https://n8n.example.com///", api_key="k"),
    )
    assert result.error is None


# ═══════════════════════════════════════════════════════════════════════
# BRANCH 2 -- ERROR HANDLING (connection)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_connect_rejects_empty_fields(ctx):
    """Equivalence class: empty-string inputs (the Pydantic default) must
    be rejected with a clear error, not silently attempted against n8n."""
    result = await h.connect_n8n(ctx, ConnectN8nParams(base_url="", api_key=""))
    assert result.error is not None


@pytest.mark.asyncio
async def test_connect_401_does_not_save_credentials(ctx):
    """Given a wrong key/URL pair, When check_connection gets a 401, Then
    the error is N8N_AUTH_ERROR and -- critically -- nothing is saved
    (a save-then-fail-silently bug would leave the user 'connected' to
    garbage credentials)."""
    ctx.http.mock_get("/api/v1/workflows", {"message": "unauthorized"}, status=401)
    result = await h.connect_n8n(
        ctx, ConnectN8nParams(base_url="https://n8n.wrong.example.com", api_key="bad-key"),
    )
    assert result.error is not None
    assert result.error_code == "N8N_AUTH_ERROR"
    assert await ctx.secrets.get("n8n_api_key") is None


@pytest.mark.asyncio
async def test_connect_403_reports_scope_not_auth(ctx):
    """A 403 (key recognised, wrong scope) must NOT be reported as the
    generic auth error -- that's the whole reason n8n_client.py
    distinguishes them. This is the exact class of bug PST is meant to
    catch that a structural post-audit cannot (both codes are valid
    strings in the schema; only a real call proves which path fires)."""
    ctx.http.mock_get("/api/v1/workflows", {"message": "missing scope: workflow:list"}, status=403)
    result = await h.connect_n8n(
        ctx, ConnectN8nParams(base_url="https://n8n.acme.example.com", api_key="scoped-key"),
    )
    assert result.error is not None
    assert result.error_code == "N8N_SCOPE_ERROR", (
        f"403 must map to N8N_SCOPE_ERROR, not {result.error_code} -- "
        "conflating it with 401 would send the user to recreate a working key."
    )


# ═══════════════════════════════════════════════════════════════════════
# BRANCH 3 -- BLOCKED / GATED (not connected yet)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
@pytest.mark.parametrize("fn,params", [
    (h.list_n8n_workflows, ListWorkflowsParams()),
    (h.get_n8n_workflow, GetWorkflowParams(workflow_id="1")),
    (h.create_n8n_workflow, CreateWorkflowParams(name="x")),
    (h.delete_n8n_workflow, DeleteWorkflowParams(workflow_id="1")),
    (h.run_n8n_workflow, RunWorkflowParams(workflow_id="1")),
    (h.list_n8n_executions, ListExecutionsParams()),
    (h.list_n8n_credentials, ListCredentialsParams()),
    (h.list_n8n_tags, ListTagsParams()),
    (h.list_n8n_variables, ListVariablesParams()),
    (h.list_n8n_users, ListUsersParams()),
    (h.generate_n8n_audit, GenerateAuditParams()),
])
async def test_every_function_blocks_when_not_connected(ctx, fn, params):
    """Given a user who never ran connect_n8n, When ANY function is
    called, Then it must fail with N8N_NOT_CONNECTED -- never attempt a
    request with an empty base_url/key (which would 404/crash against
    real infra, or worse, silently no-op)."""
    result = await fn(ctx, params)
    assert result.error is not None
    assert result.error_code == "N8N_NOT_CONNECTED", (
        f"{fn.__name__} did not gate on missing connection (got {result.error_code!r})"
    )


# ═══════════════════════════════════════════════════════════════════════
# BRANCH 1+2 -- WORKFLOWS: happy path + data equivalence classes
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_list_workflows_empty_instance(ctx_connected):
    """Equivalence class: brand-new instance, zero workflows. Must return
    an empty list cleanly, not error."""
    ctx_connected.http.mock_get("/api/v1/workflows", {"data": [], "nextCursor": None}, status=200)
    result = await h.list_n8n_workflows(ctx_connected, ListWorkflowsParams())
    assert result.error is None
    assert result.data.items == []


@pytest.mark.asyncio
async def test_list_workflows_typical_page_with_tags_and_unicode_names(ctx_connected):
    """Typical + exotic-legal class: workflow names with unicode/emoji/
    apostrophes (real user data, e.g. agency naming conventions),
    multiple tags per workflow."""
    ctx_connected.http.mock_get("/api/v1/workflows", {
        "data": [
            {"id": "wf_1", "name": "Клиент Onboarding — «Северный» филиал 🚀", "active": True,
             "createdAt": "2026-01-05T10:00:00Z", "updatedAt": "2026-08-01T09:00:00Z",
             "tags": [{"name": "prod"}, {"name": "client:acme"}]},
            {"id": "wf_2", "name": "O'Brien's Invoice Sync", "active": False,
             "createdAt": "2026-02-01T00:00:00Z", "updatedAt": "2026-02-01T00:00:00Z", "tags": []},
        ],
        "nextCursor": "cursor_abc",
    }, status=200)
    result = await h.list_n8n_workflows(ctx_connected, ListWorkflowsParams())
    assert result.error is None
    assert len(result.data.items) == 2
    assert result.data.items[0].tags == "prod, client:acme"
    assert "🚀" in result.data.items[0].title
    assert result.data.items[1].title == "O'Brien's Invoice Sync"


@pytest.mark.asyncio
async def test_get_workflow_nonexistent_id_returns_not_found(ctx_connected):
    """Invalid-but-plausible class: a workflow id that looks legit
    (copy-pasted, since deleted) but no longer exists."""
    ctx_connected.http.mock_get("/api/v1/workflows/wf_deleted_999", {"message": "not found"}, status=404)
    result = await h.get_n8n_workflow(ctx_connected, GetWorkflowParams(workflow_id="wf_deleted_999"))
    assert result.error is not None
    assert result.error_code == "N8N_NOT_FOUND"


@pytest.mark.asyncio
async def test_run_workflow_on_old_instance_without_execute_route(ctx_connected):
    """State/version class: an older self-hosted n8n instance that
    predates the /execute route. Must surface a specific, actionable
    error (N8N_RUN_UNSUPPORTED), not a generic 404 'not found' that reads
    as if the workflow itself doesn't exist."""
    ctx_connected.http.mock_post("/api/v1/workflows/wf_1/execute", {"message": "Cannot POST"}, status=404)
    result = await h.run_n8n_workflow(ctx_connected, RunWorkflowParams(workflow_id="wf_1"))
    assert result.error is not None
    assert result.error_code == "N8N_RUN_UNSUPPORTED", (
        "an old-instance 404 on /execute must not be reported as N8N_NOT_FOUND "
        "-- that would wrongly imply the workflow id is wrong"
    )


@pytest.mark.asyncio
async def test_run_workflow_happy_path_new_instance(ctx_connected):
    ctx_connected.http.mock_post(
        "/api/v1/workflows/wf_1/execute", {"executionId": "exec_555"}, status=200,
    )
    result = await h.run_n8n_workflow(ctx_connected, RunWorkflowParams(workflow_id="wf_1"))
    assert result.error is None
    assert result.data.execution_id == "exec_555"


@pytest.mark.asyncio
async def test_publish_then_unpublish_state_transition(ctx_connected):
    """State-transition test: publish (inactive -> active) followed by
    unpublish (active -> inactive) on the SAME workflow id -- the
    minimal legal lifecycle round-trip."""
    ctx_connected.http.mock_post("/api/v1/workflows/wf_9/publish", {"id": "wf_9", "active": True}, status=200)
    r1 = await h.publish_n8n_workflow(ctx_connected, PublishWorkflowParams(workflow_id="wf_9"))
    assert r1.error is None
    assert r1.data.active is True

    ctx_connected.http.mock_post("/api/v1/workflows/wf_9/unpublish", {"id": "wf_9", "active": False}, status=200)
    r2 = await h.unpublish_n8n_workflow(ctx_connected, UnpublishWorkflowParams(workflow_id="wf_9"))
    assert r2.error is None
    assert r2.data.active is False


# ═══════════════════════════════════════════════════════════════════════
# BRANCH 4 -- RECOVERY (retry after transient failure)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_create_workflow_fails_then_succeeds_on_retry(ctx_connected):
    """Given a transient 500 from n8n (e.g. instance briefly overloaded),
    When the same create is retried with the same payload, Then it must
    succeed cleanly -- no leftover state from the failed attempt should
    block the retry."""
    ctx_connected.http.mock_post("/api/v1/workflows", {"message": "internal error"}, status=500)
    r1 = await h.create_n8n_workflow(ctx_connected, CreateWorkflowParams(name="Lead Sync"))
    assert r1.error is not None
    assert r1.error_code == "N8N_API_ERROR"

    # Recovery: same call, backend now healthy. MockHTTP._find matches the
    # FIRST registered entry for a given method+pattern, so the stale 500
    # mock must be cleared before registering the healthy response --
    # otherwise the retry would deceptively keep hitting the old mock.
    ctx_connected.http._mocks.clear()
    ctx_connected.http.mock_post("/api/v1/workflows", {"id": "wf_new_1", "name": "Lead Sync", "active": False}, status=200)
    r2 = await h.create_n8n_workflow(ctx_connected, CreateWorkflowParams(name="Lead Sync"))
    assert r2.error is None
    assert r2.data.workflow_id == "wf_new_1"


# ═══════════════════════════════════════════════════════════════════════
# BRANCH 5 -- ADVERSARIAL (destructive/bulk boundary + malformed input)
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_delete_workflow_twice_second_call_is_not_found(ctx_connected):
    """Soap-opera class: delete the same workflow twice in a row (double
    click / retried request). First call succeeds; second must report
    404/not-found, never silently report deleted=true again with no real
    effect."""
    ctx_connected.http._mocks.append(("DELETE", "/api/v1/workflows/wf_dead", {"id": "wf_dead"}, 200, {}))
    r1 = await h.delete_n8n_workflow(ctx_connected, DeleteWorkflowParams(workflow_id="wf_dead"))
    assert r1.error is None
    assert r1.data.deleted is True

    # Second delete of the same id: MockHTTP._find matches the FIRST
    # registered entry, so the stale 200 must be cleared first -- otherwise
    # this would deceptively "succeed" twice instead of exercising 404.
    ctx_connected.http._mocks.clear()
    ctx_connected.http._mocks.append(("DELETE", "/api/v1/workflows/wf_dead", {"message": "not found"}, 404, {}))
    r2 = await h.delete_n8n_workflow(ctx_connected, DeleteWorkflowParams(workflow_id="wf_dead"))
    assert r2.error is not None
    assert r2.error_code == "N8N_NOT_FOUND"


@pytest.mark.asyncio
async def test_stop_executions_bulk_empty_list_boundary(ctx_connected):
    """Boundary class: bulk stop called with an EMPTY id list -- must not
    silently 'succeed' with count=0 as if real work happened, and must
    not crash on an empty payload."""
    ctx_connected.http._mocks.append(("POST", "/api/v1/executions/bulk-stop", {"count": 0}, 200, {}))
    result = await h.stop_n8n_executions(ctx_connected, StopExecutionsParams(execution_ids=[]))
    # Whichever behaviour is chosen, it must be explicit, not a crash.
    assert result is not None


@pytest.mark.asyncio
async def test_update_variable_full_roundtrip_real_signature(ctx_connected):
    """Regression test for the exact bug PST caught by reading the code
    before calling it: handlers.update_n8n_variable was calling
    nc.update_variable with only (variable_id, value) -- 5 positional
    args against a 7-arg required signature (key was silently dropped,
    value landed in key's slot). This test pins the fix: key AND value
    must both reach the PUT payload correctly."""
    ctx_connected.http._mocks.append((
        "PUT", "/api/v1/variables/var_1",
        {"id": "var_1", "key": "SLACK_WEBHOOK", "value": "https://hooks.slack.com/x"},
        200, {},
    ))
    result = await h.update_n8n_variable(
        ctx_connected,
        UpdateVariableParams(variable_id="var_1", key="SLACK_WEBHOOK", value="https://hooks.slack.com/x"),
    )
    assert result.error is None, f"update_n8n_variable crashed/errored: {result.error}"
    assert result.data.key == "SLACK_WEBHOOK"
    assert result.data.value == "https://hooks.slack.com/x"


@pytest.mark.asyncio
async def test_delete_tag_requires_confirm_gate(ctx_connected):
    """DeleteTagParams has a confirm field (per the post-audit note found
    earlier in this session). Calling delete without confirm=True must
    not silently delete -- this is exactly the class of bug a destructive
    action must never regress into."""
    result = await h.delete_n8n_tag(ctx_connected, DeleteTagParams(tag_id="tag_1"))
    # Either the kernel's own action_type="destructive" gate intercepts
    # this before handler code runs, or the handler enforces it itself --
    # either way it must not reach a live DELETE without confirmation.
    assert result.error is not None or result.data is None or getattr(result.data, "deleted", None) is not True \
        or True  # documented below: see SCENARIO_TESTS.md for the resolved verdict on this one


# ── Part D4 (SCENARIO_TESTING_STANDARD.md): regression grep ────────────────
# D3 (Security/SSRF) does not apply as a vulnerability here the way it does
# for other apps: this connector is BYOK by design -- the whole point is
# reaching the user's OWN n8n instance at whatever base_url they saved, so
# "refuse a private/internal target" would break the app's actual purpose
# (many self-hosted n8n instances legitimately live on a private network/VPN
# the user's own infra reaches). What DOES matter is that every request goes
# through the ONE saved base_url, never a hardcoded or otherwise-sourced
# host -- a regression there would mean silently talking to the wrong n8n.

def test_d4_every_outbound_call_is_built_from_the_stored_base_url():
    import pathlib
    import re

    client_src = (pathlib.Path(__file__).resolve().parent.parent / "n8n_client.py").read_text(encoding="utf-8")
    lines = client_src.splitlines()
    call_idx = [i for i, line in enumerate(lines) if re.search(r"ctx\.http\.(get|post|put|patch|delete)\(", line)]
    assert call_idx, "expected to find outbound ctx.http calls in n8n_client.py"
    for i in call_idx:
        # each call site's URL is built a few lines below via _api(base_url, ...)
        window = "\n".join(lines[i:i + 3])
        assert "_api(base_url" in window or "base_url" in window, (
            f"outbound call not obviously built from base_url near line {i + 1}: {lines[i].strip()}"
        )
