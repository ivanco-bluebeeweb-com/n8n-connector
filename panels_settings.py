"""The single 'App settings' screen (center slot) -- connection management
(connect/disconnect) for n8n. Split out of panels.py per the same
convention as Aidentika's panels_settings.py.

Per ~/UI_INTERFACE_STANDARD.md (updated 2026-08-20): the left sidebar no
longer wraps the connection status in a Card -- it's a plain stack line,
and the *only* way to disconnect is through this "App settings" screen,
reached via the one secondary "App settings" button that sits LAST at
the bottom of the sidebar.
"""
from __future__ import annotations

from imperal_sdk import ui

from app import ext
import handlers as h


def _connection_section(base_url: str, connected: bool) -> ui.UINode:
    if not connected:
        return ui.Stack(direction="v", gap=2, children=[
            ui.Text("Connection", variant="heading"),
            ui.Text("Not connected.", variant="caption"),
            ui.Text(
                "Paste your instance's URL and API key below. Both are "
                "verified together before saving.",
                variant="caption",
            ),
            ui.Form(
                action="connect_n8n",
                submit_label="Verify and connect",
                children=[
                    ui.Input(param_name="base_url",
                              placeholder="https://n8n.example.com"),
                    ui.Password(param_name="api_key", placeholder="n8n API key"),
                ],
            ),
        ])
    return ui.Stack(direction="v", gap=2, children=[
        ui.Text("Connection", variant="heading"),
        ui.Text(f"Connected -- {base_url}", variant="caption"),
        ui.Button("Disconnect", variant="danger", size="sm",
                  on_click=ui.Call("disconnect_n8n")),
    ])


@ext.panel("n8n_settings", slot="center", title="App settings", icon="⚙️",
           center_overlay=True)
async def n8n_settings_panel(ctx, **kwargs) -> object:
    base_url, api_key = await h._get_credentials(ctx)
    connected = bool(base_url and api_key)
    return ui.Stack(direction="v", gap=3, children=[
        ui.Text("n8n -- App settings", variant="title"),
        _connection_section(base_url, connected),
    ])
