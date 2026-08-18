"""Pydantic params models + SDL entity contracts for n8n Connector.

All params models are module-scope (V17 federal invariant, same rule as
Make.com Connector's schemas.py).
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from imperal_sdk import sdl


class NoParams(BaseModel):
    """Explicit empty params model -- V17 disallows untyped handlers."""
    pass


# ──────────────────────────────────────────────────────────────────────────
# Connection
# ──────────────────────────────────────────────────────────────────────────


class ConnectN8nParams(BaseModel):
    base_url: str = Field(
        "",
        description=(
            "Base URL of your n8n instance, e.g. https://n8n.example.com "
            "(self-hosted) or https://your-org.app.n8n.cloud (n8n Cloud)."
        ),
    )
    api_key: str = Field(
        "",
        description="n8n API key -- create it in your instance: Settings -> n8n API -> Create an API key.",
    )


class ProviderConnection(sdl.Entity):
    id: str = ""
    title: str = ""
    connected: bool = False
    detail: str = ""


# ──────────────────────────────────────────────────────────────────────────
# Workflows
# ──────────────────────────────────────────────────────────────────────────


class ListWorkflowsParams(BaseModel):
    active: bool | None = Field(None, description="Filter by active/published state. Omit for all.")
    tags: str | None = Field(None, description="Comma-separated tag names to filter by.")
    limit: int = Field(50, ge=1, le=200, description="Max workflows to return per page.")
    cursor: str = Field("", description="Pagination cursor from a previous call's nextCursor.")


class N8nWorkflow(sdl.Entity):
    id: str = ""
    title: str = ""
    workflow_id: str = ""
    active: bool = False
    created_at: str = ""
    updated_at: str = ""
    tags: str = ""


class N8nWorkflowList(sdl.EntityList[N8nWorkflow]):
    pass


class GetWorkflowParams(BaseModel):
    workflow_id: str = Field(..., description="n8n workflow id (see list_workflows).")


class CreateWorkflowParams(BaseModel):
    name: str = Field(..., description="Workflow name.")
    nodes: list[dict] = Field(default_factory=list, description="n8n node definitions -- see n8n's workflow JSON format.")
    connections: dict = Field(default_factory=dict, description="n8n node connection map -- see n8n's workflow JSON format.")


class UpdateWorkflowParams(BaseModel):
    workflow_id: str = Field(..., description="n8n workflow id to update (see list_workflows).")
    name: str = Field("", description="New name. Leave empty to keep the current one.")
    nodes: list[dict] | None = Field(None, description="Full replacement node list. Omit to keep current nodes.")
    connections: dict | None = Field(None, description="Full replacement connection map. Omit to keep current connections.")


class DeleteWorkflowParams(BaseModel):
    workflow_id: str = Field(..., description="n8n workflow id to permanently delete (see list_workflows).")
    confirm: bool = Field(False, description="Must be true. Deletion is permanent and cannot be undone via this API.")


class PublishWorkflowParams(BaseModel):
    workflow_id: str = Field(..., description="n8n workflow id to publish/activate (see list_workflows).")


class UnpublishWorkflowParams(BaseModel):
    workflow_id: str = Field(..., description="n8n workflow id to unpublish/deactivate (see list_workflows).")


class RunWorkflowParams(BaseModel):
    workflow_id: str = Field(..., description="n8n workflow id to run right now (see list_workflows).")
    confirm: bool = Field(
        False, description="Must be true. Running a workflow executes its real actions "
                           "in your n8n instance right now -- there is no dry-run or undo.")


class WorkflowActionResult(sdl.Entity):
    id: str = ""
    title: str = ""
    workflow_id: str = ""
    active: bool = False
    execution_id: str = ""
    status: str = ""


class DeleteResult(sdl.Entity):
    id: str = ""
    title: str = ""
    deleted: bool = False


# ──────────────────────────────────────────────────────────────────────────
# Executions
# ──────────────────────────────────────────────────────────────────────────


class ListExecutionsParams(BaseModel):
    status: str = Field("", description="Filter: success, error, waiting. Empty for all.")
    workflow_id: str = Field("", description="Filter to one workflow's executions. Empty for all.")
    limit: int = Field(50, ge=1, le=200, description="Max executions to return per page.")
    cursor: str = Field("", description="Pagination cursor from a previous call's nextCursor.")


class N8nExecution(sdl.Entity):
    id: str = ""
    title: str = ""
    execution_id: str = ""
    workflow_id: str = ""
    status: str = ""
    started_at: str = ""
    stopped_at: str = ""
    mode: str = ""


class N8nExecutionList(sdl.EntityList[N8nExecution]):
    pass


class GetExecutionParams(BaseModel):
    execution_id: str = Field(..., description="n8n execution id (see list_executions).")
    include_data: bool = Field(False, description="Include the execution's full run data (larger response).")


class DeleteExecutionParams(BaseModel):
    execution_id: str = Field(..., description="n8n execution id to permanently delete (see list_executions).")
    confirm: bool = Field(False, description="Must be true. Deletion is permanent.")


class RetryExecutionParams(BaseModel):
    execution_id: str = Field(..., description="n8n execution id to retry (see list_executions).")


class StopExecutionParams(BaseModel):
    execution_id: str = Field(..., description="n8n execution id to stop (see list_executions).")


class StopExecutionsParams(BaseModel):
    execution_ids: list[str] = Field(..., description="n8n execution ids to stop, in one call.")


class ExecutionActionResult(sdl.Entity):
    id: str = ""
    title: str = ""
    execution_id: str = ""
    status: str = ""


class BulkExecutionResult(sdl.Entity):
    id: str = ""
    title: str = ""
    count: int = 0


# ──────────────────────────────────────────────────────────────────────────
# Credentials -- full access per Vlad's decision (PREPARATION.md section 4,
# answer 3). No update endpoint exists in n8n's Public API (get-schema /
# create / delete only) -- reflected in the tool set below, not a gap.
# ──────────────────────────────────────────────────────────────────────────


class ListCredentialsParams(NoParams):
    pass


class N8nCredential(sdl.Entity):
    id: str = ""
    title: str = ""
    credential_id: str = ""
    credential_type: str = ""
    created_at: str = ""
    updated_at: str = ""


class N8nCredentialList(sdl.EntityList[N8nCredential]):
    pass


class GetCredentialSchemaParams(BaseModel):
    credential_type_name: str = Field(
        ..., description="n8n credential type name, e.g. 'openAiApi', 'clickUpApi'. "
                         "Ask the user for the exact type if unsure -- it must match n8n's own naming.",
    )


class CredentialSchema(sdl.Entity):
    id: str = ""
    title: str = ""
    fields_json: str = ""


class CreateCredentialParams(BaseModel):
    name: str = Field(..., description="Display name for the new credential.")
    credential_type_name: str = Field(..., description="n8n credential type name (see get_credential_schema).")
    data: dict = Field(..., description="Credential field values matching the type's schema (see get_credential_schema).")


class DeleteCredentialParams(BaseModel):
    credential_id: str = Field(..., description="n8n credential id to permanently delete (see list_credentials).")
    confirm: bool = Field(
        False, description="Must be true. Deletion is permanent -- and since n8n has no update "
                           "endpoint for credentials, this is also the only way to 'change' one "
                           "(delete, then create_credential again).")


# ──────────────────────────────────────────────────────────────────────────
# Tags
# ──────────────────────────────────────────────────────────────────────────


class ListTagsParams(BaseModel):
    limit: int = Field(50, ge=1, le=200, description="Max tags to return per page.")
    cursor: str = Field("", description="Pagination cursor from a previous call's nextCursor.")


class N8nTag(sdl.Entity):
    id: str = ""
    title: str = ""
    tag_id: str = ""
    created_at: str = ""


class N8nTagList(sdl.EntityList[N8nTag]):
    pass


class CreateTagParams(BaseModel):
    name: str = Field(..., description="Tag name to create.")


class DeleteTagParams(BaseModel):
    tag_id: str = Field(..., description="n8n tag id to permanently delete (see list_tags).")
    confirm: bool = Field(False, description="Must be true. Deletion is permanent.")
