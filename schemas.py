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
    allow_private_http: bool = Field(
        False,
        description=(
            "Set true to allow a plain http:// base_url for a self-hosted "
            "instance on localhost or a private network. HTTPS is required otherwise."
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


class PublishWorkflowParams(BaseModel):
    workflow_id: str = Field(..., description="n8n workflow id to publish/activate (see list_workflows).")


class UnpublishWorkflowParams(BaseModel):
    workflow_id: str = Field(..., description="n8n workflow id to unpublish/deactivate (see list_workflows).")


class RunWorkflowParams(BaseModel):
    workflow_id: str = Field(..., description="n8n workflow id to run right now (see list_workflows).")


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
    run_data: dict = Field(default_factory=dict)


class N8nExecutionList(sdl.EntityList[N8nExecution]):
    pass


class GetExecutionParams(BaseModel):
    execution_id: str = Field(..., description="n8n execution id (see list_executions).")
    include_data: bool = Field(False, description="Include the execution's full run data (larger response).")


class DeleteExecutionParams(BaseModel):
    execution_id: str = Field(..., description="n8n execution id to permanently delete (see list_executions).")


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


class UpdateTagParams(BaseModel):
    tag_id: str = Field(..., description="n8n tag id to rename (see list_tags).")
    name: str = Field(..., description="New name for the tag.")


# ──────────────────────────────────────────────────────────────────────────
# Workflow tags / versions / unarchive / transfer
# ──────────────────────────────────────────────────────────────────────────


class GetWorkflowTagsParams(BaseModel):
    workflow_id: str = Field(..., description="n8n workflow id (see list_workflows).")


class UpdateWorkflowTagsParams(BaseModel):
    workflow_id: str = Field(..., description="n8n workflow id (see list_workflows).")
    tag_ids: list[str] = Field(..., description="Full replacement list of tag ids to assign to this workflow.")


class ListWorkflowVersionsParams(BaseModel):
    workflow_id: str = Field(..., description="n8n workflow id (see list_workflows).")


class GetWorkflowVersionParams(BaseModel):
    workflow_id: str = Field(..., description="n8n workflow id (see list_workflows).")
    version_id: str = Field(..., description="Specific version id (see list_workflow_versions).")


class N8nWorkflowVersion(sdl.Entity):
    id: str = ""
    title: str = ""
    version_id: str = ""
    workflow_id: str = ""
    name: str = ""
    autosaved: bool = False
    created_at: str = ""


class N8nWorkflowVersionList(sdl.EntityList[N8nWorkflowVersion]):
    pass


class UnarchiveWorkflowParams(BaseModel):
    workflow_id: str = Field(..., description="n8n workflow id to unarchive (see list_workflows).")


class TransferWorkflowParams(BaseModel):
    workflow_id: str = Field(..., description="n8n workflow id to transfer (see list_workflows).")
    destination_project_id: str = Field(..., description="Target project id to move the workflow into.")


# ──────────────────────────────────────────────────────────────────────────
# Execution tags
# ──────────────────────────────────────────────────────────────────────────


class GetExecutionTagsParams(BaseModel):
    execution_id: str = Field(..., description="n8n execution id (see list_executions).")


class UpdateExecutionTagsParams(BaseModel):
    execution_id: str = Field(..., description="n8n execution id (see list_executions).")
    tag_ids: list[str] = Field(..., description="Full replacement list of tag ids to assign to this execution.")


# ──────────────────────────────────────────────────────────────────────────
# Credentials -- extra operations beyond Срез 2 (get by id, update, test, transfer)
# ──────────────────────────────────────────────────────────────────────────


class GetCredentialParams(BaseModel):
    credential_id: str = Field(..., description="n8n credential id (see list_credentials).")


class UpdateCredentialParams(BaseModel):
    credential_id: str = Field(..., description="n8n credential id to update (see list_credentials).")
    name: str = Field("", description="New display name. Leave empty to keep the current one.")
    credential_type_name: str = Field(
        "", description="New credential type name -- required only if changing type, must be paired with data."
    )
    data: dict | None = Field(None, description="New credential field values (see get_credential_schema). Required if changing type.")
    is_partial_data: bool = Field(
        False, description="If true, merges the given data into the existing (unredacted) data instead of replacing it entirely."
    )


class TestCredentialParams(BaseModel):
    credential_id: str = Field(..., description="n8n credential id to test (see list_credentials).")


class CredentialTestResult(sdl.Entity):
    id: str = ""
    title: str = ""
    status: str = ""
    message: str = ""


class TransferCredentialParams(BaseModel):
    credential_id: str = Field(..., description="n8n credential id to transfer (see list_credentials).")
    destination_project_id: str = Field(..., description="Target project id to move the credential into.")


# ──────────────────────────────────────────────────────────────────────────
# Variables -- full resource (list/create/update/delete)
# ──────────────────────────────────────────────────────────────────────────


class ListVariablesParams(BaseModel):
    limit: int = Field(100, ge=1, le=200, description="Max variables to return per page.")
    cursor: str = Field("", description="Pagination cursor from a previous call's nextCursor.")


class N8nVariable(sdl.Entity):
    id: str = ""
    title: str = ""
    key: str = ""
    value: str = ""
    project_name: str = ""


class N8nVariableList(sdl.EntityList[N8nVariable]):
    pass


class CreateVariableParams(BaseModel):
    key: str = Field(..., description="Variable name -- used in n8n expressions as $vars.<key>.")
    value: str = Field(..., description="Variable value.")
    project_id: str = Field("", description="Project to create the variable in. Defaults to the user's personal project.")


class UpdateVariableParams(BaseModel):
    variable_id: str = Field(..., description="n8n variable id to update (see list_variables).")
    key: str = Field(..., description="New variable name.")
    value: str = Field(..., description="New variable value.")
    project_id: str = Field("", description="Project the variable belongs to. Leave empty to keep unchanged.")


class DeleteVariableParams(BaseModel):
    variable_id: str = Field(..., description="n8n variable id to permanently delete (see list_variables).")


# ──────────────────────────────────────────────────────────────────────────
# Users -- full resource. Only relevant for multi-user/Enterprise n8n instances.
# ──────────────────────────────────────────────────────────────────────────


class ListUsersParams(BaseModel):
    limit: int = Field(100, ge=1, le=200, description="Max users to return per page.")
    cursor: str = Field("", description="Pagination cursor from a previous call's nextCursor.")
    include_role: bool = Field(False, description="Whether to include each user's global role in the results.")


class N8nUser(sdl.Entity):
    id: str = ""
    title: str = ""
    email: str = ""
    first_name: str = ""
    last_name: str = ""
    role: str = ""
    is_pending: bool = False


class N8nUserList(sdl.EntityList[N8nUser]):
    pass


class CreateUsersParams(BaseModel):
    invites: list[dict] = Field(
        ..., description="List of {email, role} dicts to invite, e.g. [{'email': 'a@b.com', 'role': 'global:member'}]."
    )


class GetUserParams(BaseModel):
    id_or_email: str = Field(..., description="User id or email address.")
    include_role: bool = Field(False, description="Whether to include the user's global role.")


class DeleteUserParams(BaseModel):
    id_or_email: str = Field(..., description="User id or email address to permanently delete.")


class ChangeUserRoleParams(BaseModel):
    id_or_email: str = Field(..., description="User id or email address.")
    new_role_name: str = Field(..., description="New global role, e.g. 'global:admin', 'global:member'.")


# ──────────────────────────────────────────────────────────────────────────
# Source Control -- pull changes from the connected remote repository.
# ──────────────────────────────────────────────────────────────────────────


class PullSourceControlParams(BaseModel):
    force: bool = Field(False, description="Discard uncommitted local changes/merge conflicts and force the pull.")
    auto_publish: str = Field(
        "none", description="Publishing behavior after import: 'none' (keep local published state), "
                             "'all' (publish everything imported), or 'published' (only what was published locally before)."
    )


class SourceControlPullResult(sdl.Entity):
    id: str = ""
    title: str = ""
    files_changed: int = 0
    workflows_count: int = 0
    credentials_count: int = 0
    variables_count: int = 0
    tags_count: int = 0
    summary_json: str = ""


# ──────────────────────────────────────────────────────────────────────────
# Audit -- generate a security audit report for the instance.
# ──────────────────────────────────────────────────────────────────────────


class GenerateAuditParams(BaseModel):
    days_abandoned_workflow: int = Field(
        90, description="Workflows with no executions in this many days are flagged as abandoned."
    )
    categories: list[str] = Field(
        default_factory=list,
        description="Which risk categories to include: credentials, database, filesystem, nodes, instance. Empty for all.",
    )


class AuditReport(sdl.Entity):
    id: str = ""
    title: str = ""
    report_json: str = ""
