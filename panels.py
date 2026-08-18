"""Panel UI -- Срез 1 (connection) only.

SKETCH (PREPARATION.md section 6), implemented:
  ui.Stack (v, gap=4)
    ui.Header
    ui.Card (connect form OR connected status) -- ONE genuine widget, not a list
      [not connected] ui.Input(base_url) FIRST, then ui.Password(api_key),
                       ui.Button("How do I get an API key?")
                       ui.Form(action=connect_n8n, submit_label="Verify and connect")
      [connected]      ui.Text(detail) + ui.Button("Disconnect")
  -- separate center_overlay dialog, opened by the help button --
  @ext.panel("n8n_connect_help", slot="center", center_overlay=True)
    ui.Dialog(title=..., content=ui.Stack(v, [ui.Text(step1..4), ui.Divider(), ui.Link(docs)]))

PRE-PANEL CHECKLIST pass:
  - ui.Input / ui.Password: no label=, no type=      OK
  - ui.Card: content=, not children=                 OK
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

SIDEBAR CONTENT SECTIONS -- NOT wrapped in ui.Card, from the FIRST DRAFT.

Only the connect/connected block is a genuine Card (a single form/status
widget, not a list). Any future section listing several items of the
same kind (workflows, executions, tags) must render as a plain ui.Stack
with a ui.Divider() before it -- no card padding/border/background per
section. This is Vlad's standing rule (flagged after a Make.com Connector
regression, see PREPARATION.md section 7) applied here from the start
instead of fixed after the fact.
"""
from __future__ import annotations

from imperal_sdk import ui

from app import ext
import handlers as h


def _connected_card(detail: str) -> ui.UINode:
    return ui.Card(
        title="n8n",
        subtitle="Connected",
        content=ui.Stack(direction="v", gap=2, children=[
            ui.Text(detail, variant="caption"),
            ui.Button("Disconnect", variant="danger", size="sm",
                      on_click=ui.Call("disconnect_n8n")),
        ]),
    )


def _connect_card() -> ui.UINode:
    return ui.Card(
        title="Connect n8n",
        subtitle="Bring your own n8n instance -- self-hosted or n8n Cloud",
        content=ui.Stack(direction="v", gap=3, children=[
            ui.Text(
                "Paste your instance's URL and API key below. Both are "
                "verified together before saving. This key gives full "
                "access to your instance's workflows, executions AND "
                "credentials -- only connect an account you're comfortable "
                "granting that to.",
                variant="caption",
            ),
            ui.Stack(direction="h", gap=2, align="center", children=[
                ui.Button("How do I get an API key?", variant="ghost", size="sm",
                          icon="HelpCircle",
                          on_click=ui.Call("__panel__n8n_connect_help")),
            ]),
            ui.Form(
                action="connect_n8n",
                submit_label="Verify and connect",
                children=[
                    ui.Input(param_name="base_url",
                              placeholder="https://n8n.example.com"),
                    ui.Password(param_name="api_key", placeholder="n8n API key"),
                ],
            ),
        ]),
    )


@ext.panel("n8n_connect", slot="left", title="n8n", icon="🔗",
           default_width=320, min_width=260, max_width=420)
async def n8n_connect_panel(ctx, **kwargs) -> object:
    base_url, api_key = await h._get_credentials(ctx)
    connected = bool(base_url and api_key)

    header = ui.Header(text="n8n", level=2,
                        subtitle="Manage your n8n workflows from Imperal")

    if not connected:
        return ui.Stack(direction="v", gap=4, children=[
            header,
            _connect_card(),
            ui.Alert(
                title="Not connected yet",
                message="Connect your n8n instance to see and manage your workflows.",
                type="info",
            ),
        ])

    return ui.Stack(direction="v", gap=4, children=[
        header,
        _connected_card(f"Instance: {base_url}"),
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
