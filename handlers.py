"""Chat functions for n8n Connector: connection, workflows, executions,
credentials, tags. Built on n8n_client.py / schemas.py."""
from __future__ import annotations

from imperal_sdk import ActionResult

import n8n_client as nc
from app import ext, chat
from schemas import (
    NoParams, ConnectN8nParams, ProviderConnection,
    ListWorkflowsParams, N8nWorkflow, N8nWorkflowList,
    GetWorkflowParams, CreateWorkflowParams, UpdateWorkflowParams,
    DeleteWorkflowParams, PublishWorkflowParams, UnpublishWorkflowParams,
    RunWorkflowParams, WorkflowActionResult, DeleteResult,
    ListExecutionsParams, N8nExecution, N8nExecutionList,
    GetExecutionParams, DeleteExecutionParams, RetryExecutionParams,
    StopExecutionParams, StopExecutionsParams, ExecutionActionResult,
    BulkExecutionResult,
    ListCredentialsParams, N8nCredential, N8nCredentialList,
    GetCredentialSchemaParams, CredentialSchema, CreateCredentialParams,
    DeleteCredentialParams,
    ListTagsParams, N8nTag, N8nTagList, CreateTagParams, DeleteTagParams,
)


async def _get_credentials(ctx) -> tuple[str, str]:
    base_url = await ctx.secrets.get("n8n_base_url")
    api_key = await ctx.secrets.get("n8n_api_key")
    return base_url or "", api_key or ""


def _not_connected() -> ActionResult:
    return ActionResult.error(
        "n8n isn't connected yet -- run connect_n8n first.",
        code="N8N_NOT_CONNECTED",
    )


def _workflow_entity(w: dict) -> N8nWorkflow:
    wid = str(w.get("id") or "")
    tags = w.get("tags") or []
    tag_names = ", ".join(t.get("name", "") for t in tags if isinstance(t, dict))
    return N8nWorkflow(
        id=wid,
        title=w.get("name") or wid,
        workflow_id=wid,
        active=bool(w.get("active")),
        created_at=str(w.get("createdAt") or ""),
        updated_at=str(w.get("updatedAt") or ""),
        tags=tag_names,
    )


def _execution_entity(e: dict) -> N8nExecution:
    eid = str(e.get("id") or "")
    return N8nExecution(
        id=eid,
        title=f"Execution {eid}",
        execution_id=eid,
        workflow_id=str(e.get("workflowId") or ""),
        status=str(e.get("status") or ("success" if e.get("finished") else "")),
        started_at=str(e.get("startedAt") or ""),
        stopped_at=str(e.get("stoppedAt") or ""),
        mode=str(e.get("mode") or ""),
    )


def _credential_entity(c: dict) -> N8nCredential:
    cid = str(c.get("id") or "")
    return N8nCredential(
        id=cid,
        title=c.get("name") or cid,
        credential_id=cid,
        credential_type=str(c.get("type") or ""),
        created_at=str(c.get("createdAt") or ""),
        updated_at=str(c.get("updatedAt") or ""),
    )


def _tag_entity(t: dict) -> N8nTag:
    tid = str(t.get("id") or "")
    return N8nTag(id=tid, title=t.get("name") or tid, tag_id=tid)


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
            "Please provide your n8n instance's base URL (e.g. https://n8n.example.com).",
            code="N8N_MISSING_BASE_URL",
        )
    if not api_key:
        return ActionResult.error(
            "Please provide your n8n API key -- create one in your instance: "
            "Settings -> n8n API -> Create an API key.",
            code="N8N_MISSING_API_KEY",
        )
    try:
        await nc.check_connection(ctx, base_url, api_key)
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


# ──────────────────────────────────────────────────────────────────────────
# Workflows
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "list_n8n_workflows",
    "List workflows on your connected n8n instance -- name, active state, "
    "and tags. Supports filtering by active state and/or tags.",
    action_type="read",
    chain_callable=True,
    data_model=N8nWorkflowList,
)
async def list_n8n_workflows(ctx, params: ListWorkflowsParams) -> ActionResult:
    """List workflows via GET /workflows, optionally filtered by active state and/or tags."""
    base_url, api_key = await _get_credentials(ctx)
    if not (base_url and api_key):
        return _not_connected()
    try:
        rows, next_cursor = await nc.list_workflows(
            ctx, base_url, api_key,
            active=params.active, tags=params.tags,
            limit=params.limit, cursor=params.cursor or None,
        )
    except nc.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    items = [_workflow_entity(w) for w in rows]
    summary = f"{len(items)} workflow(s)."
    if next_cursor:
        summary += f" More available (cursor={next_cursor})."
    return ActionResult.success(N8nWorkflowList(items=items), summary=summary)


@chat.function(
    "get_n8n_workflow",
    "Read one n8n workflow in full -- its nodes, connections, and active state.",
    action_type="read",
    chain_callable=True,
    data_model=N8nWorkflow,
)
async def get_n8n_workflow(ctx, params: GetWorkflowParams) -> ActionResult:
    """Read one workflow's full definition via GET /workflows/{id}."""
    base_url, api_key = await _get_credentials(ctx)
    if not (base_url and api_key):
        return _not_connected()
    try:
        w = await nc.get_workflow(ctx, base_url, api_key, params.workflow_id)
    except nc.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    return ActionResult.success(_workflow_entity(w), summary=f"Workflow '{w.get('name')}'.")


@chat.function(
    "create_n8n_workflow",
    "Create a brand-new workflow on your n8n instance from an explicit "
    "node/connection definition (n8n's own workflow JSON format).",
    action_type="write",
    data_model=N8nWorkflow,
    event="n8n-connector.create_workflow",
    effects=["n8n.workflow.created"],
)
async def create_n8n_workflow(ctx, params: CreateWorkflowParams) -> ActionResult:
    """Create a workflow via POST /workflows from an explicit node/connection definition."""
    base_url, api_key = await _get_credentials(ctx)
    if not (base_url and api_key):
        return _not_connected()
    payload = {"name": params.name, "nodes": params.nodes, "connections": params.connections}
    try:
        w = await nc.create_workflow(ctx, base_url, api_key, payload)
    except nc.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    return ActionResult.success(_workflow_entity(w), summary=f"Workflow '{params.name}' created.")


@chat.function(
    "update_n8n_workflow",
    "Update an existing n8n workflow's name, nodes, and/or connections. "
    "n8n's PUT /workflows/{id} replaces the whole entity, so this reads "
    "the current workflow first and merges in only the fields you gave.",
    action_type="write",
    data_model=N8nWorkflow,
    event="n8n-connector.update_workflow",
    effects=["n8n.workflow.updated"],
)
async def update_n8n_workflow(ctx, params: UpdateWorkflowParams) -> ActionResult:
    """Read-merge-write update: n8n's PUT /workflows/{id} replaces the whole entity,
    so the current workflow is fetched first and only the given fields are merged in."""
    base_url, api_key = await _get_credentials(ctx)
    if not (base_url and api_key):
        return _not_connected()
    try:
        current = await nc.get_workflow(ctx, base_url, api_key, params.workflow_id)
        payload = {
            "name": params.name or current.get("name"),
            "nodes": params.nodes if params.nodes is not None else current.get("nodes"),
            "connections": params.connections if params.connections is not None else current.get("connections"),
        }
        w = await nc.update_workflow(ctx, base_url, api_key, params.workflow_id, payload)
    except nc.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    return ActionResult.success(_workflow_entity(w), summary=f"Workflow '{w.get('name')}' updated.")


@chat.function(
    "delete_n8n_workflow",
    "Permanently delete a workflow from your n8n instance. Cannot be undone.",
    action_type="write",
    data_model=DeleteResult,
    event="n8n-connector.delete_workflow",
    effects=["n8n.workflow.deleted"],
)
async def delete_n8n_workflow(ctx, params: DeleteWorkflowParams) -> ActionResult:
    """Permanently delete a workflow via DELETE /workflows/{id}. Requires confirm=true."""
    if not params.confirm:
        return ActionResult.error(
            "Deleting a workflow is permanent. Pass confirm=true to proceed.",
            code="N8N_CONFIRM_REQUIRED",
        )
    base_url, api_key = await _get_credentials(ctx)
    if not (base_url and api_key):
        return _not_connected()
    try:
        await nc.delete_workflow(ctx, base_url, api_key, params.workflow_id)
    except nc.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    return ActionResult.success(
        DeleteResult(deleted=True), summary=f"Workflow {params.workflow_id} deleted.",
    )


@chat.function(
    "publish_n8n_workflow",
    "Publish (activate) an n8n workflow so its triggers start running. "
    "This is n8n's current API -- the older activate/deactivate endpoints "
    "are deprecated.",
    action_type="write",
    data_model=WorkflowActionResult,
    event="n8n-connector.publish_workflow",
    effects=["n8n.workflow.published"],
)
async def publish_n8n_workflow(ctx, params: PublishWorkflowParams) -> ActionResult:
    """Activate a workflow via POST /workflows/{id}/activate (n8n's current, non-deprecated endpoint)."""
    base_url, api_key = await _get_credentials(ctx)
    if not (base_url and api_key):
        return _not_connected()
    try:
        w = await nc.publish_workflow(ctx, base_url, api_key, params.workflow_id)
    except nc.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    return ActionResult.success(
        WorkflowActionResult(workflow_id=params.workflow_id, active=bool(w.get("active"))),
        summary=f"Workflow {params.workflow_id} published.",
    )


@chat.function(
    "unpublish_n8n_workflow",
    "Unpublish (deactivate) an n8n workflow so its triggers stop running.",
    action_type="write",
    data_model=WorkflowActionResult,
    event="n8n-connector.unpublish_workflow",
    effects=["n8n.workflow.unpublished"],
)
async def unpublish_n8n_workflow(ctx, params: UnpublishWorkflowParams) -> ActionResult:
    """Deactivate a workflow via POST /workflows/{id}/deactivate."""
    base_url, api_key = await _get_credentials(ctx)
    if not (base_url and api_key):
        return _not_connected()
    try:
        w = await nc.unpublish_workflow(ctx, base_url, api_key, params.workflow_id)
    except nc.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    return ActionResult.success(
        WorkflowActionResult(workflow_id=params.workflow_id, active=bool(w.get("active"))),
        summary=f"Workflow {params.workflow_id} unpublished.",
    )


@chat.function(
    "run_n8n_workflow",
    "Run an n8n workflow right now by id. This endpoint is recent in n8n's "
    "own API (added late 2025) -- older self-hosted instances may not have "
    "it; if it fails, trigger the workflow via its own Webhook node URL instead.",
    action_type="write",
    data_model=WorkflowActionResult,
    event="n8n-connector.run_workflow",
    effects=["n8n.workflow.executed"],
)
async def run_n8n_workflow(ctx, params: RunWorkflowParams) -> ActionResult:
    """Trigger an on-demand run via n8n's recent (late-2025) run endpoint; falls back to
    the workflow's own Webhook node URL on older instances that lack it."""
    base_url, api_key = await _get_credentials(ctx)
    if not (base_url and api_key):
        return _not_connected()
    try:
        result = await nc.run_workflow(ctx, base_url, api_key, params.workflow_id)
    except nc.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    return ActionResult.success(
        WorkflowActionResult(workflow_id=params.workflow_id, active=True),
        summary=f"Workflow {params.workflow_id} run triggered.",
        data_extra={"execution": result},
    )


# ──────────────────────────────────────────────────────────────────────────
# Executions
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "list_n8n_executions",
    "List past/current executions on your connected n8n instance -- status, "
    "workflow, and timing. Filter by status and/or workflow id.",
    action_type="read",
    chain_callable=True,
    data_model=N8nExecutionList,
)
async def list_n8n_executions(ctx, params: ListExecutionsParams) -> ActionResult:
    """List executions via GET /executions, optionally filtered by status and/or workflow id."""
    base_url, api_key = await _get_credentials(ctx)
    if not (base_url and api_key):
        return _not_connected()
    try:
        rows, next_cursor = await nc.list_executions(
            ctx, base_url, api_key,
            status=params.status or None, workflow_id=params.workflow_id or None,
            limit=params.limit, cursor=params.cursor or None,
        )
    except nc.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    items = [_execution_entity(e) for e in rows]
    summary = f"{len(items)} execution(s)."
    if next_cursor:
        summary += f" More available (cursor={next_cursor})."
    return ActionResult.success(N8nExecutionList(items=items), summary=summary)


@chat.function(
    "get_n8n_execution",
    "Read one n8n execution in full, optionally including its run data.",
    action_type="read",
    chain_callable=True,
    data_model=N8nExecution,
)
async def get_n8n_execution(ctx, params: GetExecutionParams) -> ActionResult:
    """Read one execution via GET /executions/{id}, optionally including its full run data."""
    base_url, api_key = await _get_credentials(ctx)
    if not (base_url and api_key):
        return _not_connected()
    try:
        e = await nc.get_execution(ctx, base_url, api_key, int(params.execution_id))
    except nc.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    entity = _execution_entity(e)
    extra = {"data": e.get("data")} if params.include_data else {}
    return ActionResult.success(entity, summary=f"Execution {entity.execution_id}: {entity.status}.", data_extra=extra)


@chat.function(
    "delete_n8n_execution",
    "Permanently delete one n8n execution record. This does not affect the "
    "workflow itself -- only its execution history.",
    action_type="write",
    data_model=DeleteResult,
    event="n8n-connector.delete_execution",
    effects=["n8n.execution.deleted"],
)
async def delete_n8n_execution(ctx, params: DeleteExecutionParams) -> ActionResult:
    """Permanently delete one execution record via DELETE /executions/{id}. Requires confirm=true.
    Does not affect the workflow itself, only its execution history."""
    if not params.confirm:
        return ActionResult.error(
            "Deletion is permanent -- pass confirm=true to proceed.",
            code="N8N_CONFIRM_REQUIRED",
        )
    base_url, api_key = await _get_credentials(ctx)
    if not (base_url and api_key):
        return _not_connected()
    try:
        await nc.delete_execution(ctx, base_url, api_key, int(params.execution_id))
    except nc.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    return ActionResult.success(
        DeleteResult(deleted=True),
        summary=f"Execution {params.execution_id} deleted.",
    )


@chat.function(
    "retry_n8n_execution",
    "Retry a failed n8n execution.",
    action_type="write",
    data_model=ExecutionActionResult,
    event="n8n-connector.retry_execution",
    effects=["n8n.execution.retried"],
)
async def retry_n8n_execution(ctx, params: RetryExecutionParams) -> ActionResult:
    """Retry a failed execution via POST /executions/{id}/retry."""
    base_url, api_key = await _get_credentials(ctx)
    if not (base_url and api_key):
        return _not_connected()
    try:
        result = await nc.retry_execution(ctx, base_url, api_key, int(params.execution_id))
    except nc.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    return ActionResult.success(
        ExecutionActionResult(execution_id=params.execution_id, status=str(result.get("status") or "retried")),
        summary=f"Execution {params.execution_id} retried.",
    )


@chat.function(
    "stop_n8n_execution",
    "Stop one currently-running n8n execution.",
    action_type="write",
    data_model=ExecutionActionResult,
    event="n8n-connector.stop_execution",
    effects=["n8n.execution.stopped"],
)
async def stop_n8n_execution(ctx, params: StopExecutionParams) -> ActionResult:
    """Stop one running execution via POST /executions/{id}/stop."""
    base_url, api_key = await _get_credentials(ctx)
    if not (base_url and api_key):
        return _not_connected()
    try:
        result = await nc.stop_execution(ctx, base_url, api_key, int(params.execution_id))
    except nc.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    return ActionResult.success(
        ExecutionActionResult(execution_id=params.execution_id, status=str(result.get("status") or "stopped")),
        summary=f"Execution {params.execution_id} stopped.",
    )


@chat.function(
    "stop_n8n_executions",
    "Stop several currently-running n8n executions at once.",
    action_type="write",
    data_model=BulkExecutionResult,
    event="n8n-connector.stop_executions",
    effects=["n8n.execution.stopped"],
)
async def stop_n8n_executions(ctx, params: StopExecutionsParams) -> ActionResult:
    """Stop several running executions in one call via POST /executions/stop."""
    base_url, api_key = await _get_credentials(ctx)
    if not (base_url and api_key):
        return _not_connected()
    ids = [int(i) for i in params.execution_ids]
    try:
        await nc.stop_executions(ctx, base_url, api_key, ids)
    except nc.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    return ActionResult.success(
        BulkExecutionResult(count=len(ids)),
        summary=f"Stopped {len(ids)} execution(s).",
    )


# ──────────────────────────────────────────────────────────────────────────
# Credentials -- full access per Vlad's decision. No update endpoint exists
# in n8n's own Public API (get-schema / create / delete only) -- delete +
# create_credential again is the only way to "change" one, and this must be
# explained wherever credentials are surfaced, not silently omitted.
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "list_n8n_credentials",
    "List credentials stored on your connected n8n instance -- name and "
    "type only, never their secret field values (n8n's own API never "
    "returns those either).",
    action_type="read",
    chain_callable=True,
    data_model=N8nCredentialList,
)
async def list_n8n_credentials(ctx, params: NoParams) -> ActionResult:
    """List credentials via GET /credentials -- name and type only, never secret values."""
    base_url, api_key = await _get_credentials(ctx)
    if not (base_url and api_key):
        return _not_connected()
    try:
        rows = await nc.list_credentials(ctx, base_url, api_key)
    except nc.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    items = [_credential_entity(c) for c in rows]
    return ActionResult.success(N8nCredentialList(items=items), summary=f"{len(items)} credential(s).")


@chat.function(
    "get_n8n_credential_schema",
    "Read the field schema for one n8n credential type (e.g. 'openAiApi') "
    "-- which fields it needs -- before creating a credential of that type.",
    action_type="read",
    chain_callable=True,
    data_model=CredentialSchema,
)
async def get_n8n_credential_schema(ctx, params: GetCredentialSchemaParams) -> ActionResult:
    """Read the required-fields schema for one credential type via GET /credentials/schema/{type}."""
    base_url, api_key = await _get_credentials(ctx)
    if not (base_url and api_key):
        return _not_connected()
    try:
        schema = await nc.get_credential_schema(ctx, base_url, api_key, params.credential_type_name)
    except nc.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    import json
    return ActionResult.success(
        CredentialSchema(id=params.credential_type_name, title=params.credential_type_name, fields_json=json.dumps(schema)),
        summary=f"Schema for {params.credential_type_name}.",
    )


@chat.function(
    "create_n8n_credential",
    "Create a new credential on your connected n8n instance. WARNING: this "
    "stores sensitive data (API keys, passwords, tokens) on your n8n "
    "instance -- only do this for credentials you intend workflows to use. "
    "n8n has no update endpoint: to change a credential later you must "
    "delete it and create it again.",
    action_type="write",
    data_model=N8nCredential,
    event="n8n-connector.create_credential",
    effects=["n8n.credential.created"],
)
async def create_n8n_credential(ctx, params: CreateCredentialParams) -> ActionResult:
    """Create a credential via POST /credentials. Stores sensitive data on the user's n8n instance."""
    base_url, api_key = await _get_credentials(ctx)
    if not (base_url and api_key):
        return _not_connected()
    try:
        c = await nc.create_credential(
            ctx, base_url, api_key,
            {"name": params.name, "type": params.credential_type_name, "data": params.data},
        )
    except nc.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    return ActionResult.success(_credential_entity(c), summary=f"Credential '{params.name}' created.")


@chat.function(
    "delete_n8n_credential",
    "Permanently delete a credential from your connected n8n instance. "
    "Workflows using it will fail until re-configured. This is also the "
    "only way to 'change' a credential -- n8n has no update endpoint, so "
    "delete this one and create_n8n_credential a replacement.",
    action_type="write",
    data_model=DeleteResult,
    event="n8n-connector.delete_credential",
    effects=["n8n.credential.deleted"],
)
async def delete_n8n_credential(ctx, params: DeleteCredentialParams) -> ActionResult:
    """Permanently delete a credential via DELETE /credentials/{id}. Requires confirm=true.
    Also the only way to "change" one, since n8n has no update endpoint for credentials."""
    if not params.confirm:
        return ActionResult.error(
            "Deletion is permanent -- pass confirm=true to proceed.",
            code="N8N_CONFIRM_REQUIRED",
        )
    base_url, api_key = await _get_credentials(ctx)
    if not (base_url and api_key):
        return _not_connected()
    try:
        await nc.delete_credential(ctx, base_url, api_key, params.credential_id)
    except nc.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    return ActionResult.success(
        DeleteResult(deleted=True),
        summary=f"Credential {params.credential_id} deleted.",
    )


# ──────────────────────────────────────────────────────────────────────────
# Tags
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "list_n8n_tags",
    "List tags defined on your connected n8n instance.",
    action_type="read",
    chain_callable=True,
    data_model=N8nTagList,
)
async def list_n8n_tags(ctx, params: ListTagsParams) -> ActionResult:
    """List tags via GET /tags."""
    base_url, api_key = await _get_credentials(ctx)
    if not (base_url and api_key):
        return _not_connected()
    try:
        rows, next_cursor = await nc.list_tags(ctx, base_url, api_key, limit=params.limit, cursor=params.cursor or None)
    except nc.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    items = [_tag_entity(t) for t in rows]
    summary = f"{len(items)} tag(s)."
    if next_cursor:
        summary += f" More available (cursor={next_cursor})."
    return ActionResult.success(N8nTagList(items=items), summary=summary)


@chat.function(
    "create_n8n_tag",
    "Create a new tag on your connected n8n instance.",
    action_type="write",
    data_model=N8nTag,
    event="n8n-connector.create_tag",
    effects=["n8n.tag.created"],
)
async def create_n8n_tag(ctx, params: CreateTagParams) -> ActionResult:
    """Create a tag via POST /tags."""
    base_url, api_key = await _get_credentials(ctx)
    if not (base_url and api_key):
        return _not_connected()
    try:
        t = await nc.create_tag(ctx, base_url, api_key, params.name)
    except nc.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    return ActionResult.success(_tag_entity(t), summary=f"Tag '{params.name}' created.")


@chat.function(
    "delete_n8n_tag",
    "Permanently delete a tag from your connected n8n instance. Workflows "
    "keep working -- they just lose this tag.",
    action_type="write",
    data_model=DeleteResult,
    event="n8n-connector.delete_tag",
    effects=["n8n.tag.deleted"],
)
async def delete_n8n_tag(ctx, params: DeleteTagParams) -> ActionResult:
    """Permanently delete a tag via DELETE /tags/{id}. Requires confirm=true. Workflows keep
    working -- they just lose this tag."""
    if not params.confirm:
        return ActionResult.error(
            "Deletion is permanent -- pass confirm=true to proceed.",
            code="N8N_CONFIRM_REQUIRED",
        )
    base_url, api_key = await _get_credentials(ctx)
    if not (base_url and api_key):
        return _not_connected()
    try:
        await nc.delete_tag(ctx, base_url, api_key, params.tag_id)
    except nc.ProviderError as exc:
        return ActionResult.error(str(exc), code=exc.code)
    return ActionResult.success(
        DeleteResult(deleted=True),
        summary=f"Tag {params.tag_id} deleted.",
    )
