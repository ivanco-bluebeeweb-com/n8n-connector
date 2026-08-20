"""Panel UI -- connection (Срез 1) + workflows list (Срез 2).

SKETCH, updated 2026-08-20 to the current no-card sidebar shape:
  ui.Stack (v, gap=4)
    ui.Header
    [not connected] _connect_section() -- plain content, ui.Form(connect_n8n)
    [connected]     _connected_section() -- plain text, then workflows list
    ui.Divider()
    _settings_button() -- ALWAYS the last element, secondary style
  -- separate center_overlay dialogs --
  @ext.panel("n8n_connect_help", slot="center", center_overlay=True)
    ui.Dialog(title=..., content=ui.Stack(v, [ui.Text(step1..4), ui.Divider(), ui.Link(docs)]))
  @ext.panel("n8n_settings", slot="center", center_overlay=True) -- panels_settings.py
    disconnect lives here, not inline in the sidebar

PRE-PANEL CHECKLIST pass:
  - ui.Input / ui.Password: label= set on every field (2026-08-20 update
    to UI_INTERFACE_STANDARD.md -- label is now mandatory, not optional),
    placeholder= is a contextual example, not a substitute for the label OK
  - No ui.Card anywhere in the left sidebar slot      OK
  - ui.Dialog on a center_overlay panel, opened via ui.Call("__panel__...")
    (same proven pattern as make_connect_help / yt_connect_dialog)  OK
  - ui.Form does not submit pre-set value= fields -- both base_url and
    api_key are user-typed, not pre-filled, so no hidden-context
    workaround needed                                  OK

WHY base_url IS THE FIRST FIELD, NOT AN AFTERTHOUGHT.

Unlike Make.com Connector (where the zone is auto-detected and the form
only ever asks for a token), n8n has no fixed set of hosts to probe --
confirmed with Vlad 2026-08-18 (PREPARATION.md section 4, answer 2). The
form must ask for the instance URL up front, as literally the first
field, not bury it as a secondary/advanced option.

SIDEBAR CONTENT -- NO CARDS ANYWHERE, updated 2026-08-20 per
~/UI_INTERFACE_STANDARD.md's "left sidebar, no decorated cards" rule.

Every section (connected status, workflows) is a plain ui.Stack, content
stacked vertically and left-aligned, sections separated by ui.Divider()
-- no Card border/background/shadow anywhere in this slot. Disconnect now
lives in the "App settings" screen (panels_settings.py), not inline in
the sidebar -- the sidebar only shows the connected summary line. The one
secondary "App settings" button is always the LAST element at the bottom
of the sidebar.
"""
from __future__ import annotations

from imperal_sdk import ui

import n8n_client as nc
from app import ext
import handlers as h


def _settings_button() -> ui.UINode:
    """The one required secondary entry point into the settings screen --
    always the last element at the bottom of the sidebar."""
    return ui.Button(
        "App settings", variant="secondary", size="sm", full_width=True,
        icon="settings", on_click=ui.Call("__panel__n8n_settings"),
    )


def _connected_section(detail: str) -> ui.UINode:
    """Plain content, no Card wrapper -- disconnect lives in App settings now."""
    return ui.Stack(direction="v", gap=1, align="start", children=[
        ui.Text("n8n", variant="body"),
        ui.Text(detail, variant="caption"),
    ])


def _workflow_row(w) -> ui.UINode:
    """One workflow row -- plain content, no Card wrapper, no padding/border.
    A Divider() between rows (added by the caller) is the ONLY separator,
    per Vlad's standing sidebar rule (PREPARATION.md section 7)."""
    status = "Active" if w.active else "Inactive"
    subtitle = f"{status}" + (f" · {w.tags}" if w.tags else "")
    return ui.Stack(direction="v", gap=1, children=[
        ui.Text(w.title, variant="body"),
        ui.Text(subtitle, variant="caption"),
    ])


def _workflows_section(workflows: list) -> ui.UINode:
    if not workflows:
        return ui.Text("No workflows yet.", variant="caption")
    children: list[ui.UINode] = []
    for i, w in enumerate(workflows):
        if i > 0:
            children.append(ui.Divider())
        children.append(_workflow_row(w))
    return ui.Stack(direction="v", gap=2, children=children)


def _connect_section() -> ui.UINode:
    """Plain content, no Card wrapper -- shown only while not connected.
    Stretched full-width per UI_INTERFACE_STANDARD.md (2026-08-20). No
    intro heading/description text here -- that instruction lives ONLY in
    n8n_connect_help's modal (button below opens it); repeating it here,
    or an extra "Not connected yet" Alert next to an already-empty form,
    would duplicate what the empty form itself already communicates."""
    return ui.Stack(direction="v", gap=3, align="stretch", children=[
        ui.Button("How do I get an API key?", variant="ghost", size="sm",
                  icon="HelpCircle",
                  on_click=ui.Call("__panel__n8n_connect_help")),
        ui.Form(
            action="connect_n8n",
            submit_label="Verify and connect",
            children=[
                ui.Stack(direction="v", gap=1, children=[
                    ui.Text("Instance URL", variant="caption"),
                    ui.Input(param_name="base_url",
                              placeholder="https://n8n.example.com"),
                ]),
                ui.Stack(direction="v", gap=1, children=[
                    ui.Text("API key", variant="caption"),
                    ui.Password(param_name="api_key", placeholder="n8n API key"),
                ]),
            ],
        ),
    ])


@ext.panel("n8n_connect", slot="left", title="n8n", icon="🔗",
           default_width=320, min_width=260, max_width=420)
async def n8n_connect_panel(ctx, **kwargs) -> object:
    base_url, api_key = await h._get_credentials(ctx)
    connected = bool(base_url and api_key)

    header = ui.Header(text="n8n", level=2,
                        subtitle="Manage your n8n workflows from Imperal")

    if not connected:
        return ui.Stack(direction="v", gap=4, align="stretch", children=[
            header,
            _connect_section(),
            ui.Divider(),
            _settings_button(),
        ])

    workflows: list = []
    if connected:
        try:
            rows, _ = await nc.list_workflows(ctx, base_url, api_key, limit=50)
            workflows = [h._workflow_entity(w) for w in rows]
        except nc.ProviderError:
            workflows = []

    return ui.Stack(direction="v", gap=4, align="stretch", children=[
        header,
        _connected_section(f"Instance: {base_url}"),
        ui.Divider(),
        ui.Text("Workflows", variant="subtitle"),
        _workflows_section(workflows),
        ui.Divider(),
        _settings_button(),
    ])


@ext.panel("n8n_connect_help", slot="center", title="How to get an n8n API key",
           center_overlay=True)
async def n8n_connect_help(ctx, **kwargs) -> object:
    content = ui.Stack(direction="v", gap=3, children=[
        ui.Text("1. Open your n8n instance and go to Settings."),
        ui.Text("2. Open the n8n API section."),
        ui.Text("3. Click Create an API key, optionally set an expiry, and save."),
        ui.Text("4. Copy the key -- n8n only shows it once."),
        ui.Divider(),
        ui.Alert(
            title="This key grants full access",
            message=(
                "An n8n API key can read and change workflows, executions "
                "AND credentials (the logins your workflow nodes use for "
                "other services). Only paste a key for an instance/account "
                "you're comfortable giving that level of access to."
            ),
            type="warning",
        ),
        ui.Divider(),
        ui.Link(
            label="Open n8n's official documentation",
            href="https://docs.n8n.io/connect/n8n-api/authentication",
        ),
    ])
    return ui.Dialog(
        title="How to get an n8n API key",
        content=content,
        confirm_label="",
        cancel_label="Close",
    )


@ext.panel("n8n_center", slot="center", title="n8n", icon="🔗")
async def n8n_center_panel(ctx, **kwargs) -> object:
    """Base (non-overlay) center panel -- per UI_INTERFACE_STANDARD.md
    (2026-08-20): this app has no list/detail content of its own to show
    in the center by default (everything lives in the sidebar; center is
    only ever used for settings/help via center_overlay). Without this
    panel the center slot would simply render nothing when connected and
    nothing else is open. Text is the shared canonical wording -- must
    stay identical across every app in this situation, not app-specific."""
    return ui.Empty(
        message="Nothing to show here -- this app is managed entirely from the sidebar.",
        icon="👈",
    )
