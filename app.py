"""Extension declaration, secrets, lifecycle hooks.

WHY BYOK (bring-your-own-key), same reasoning as Make.com Connector /
DataForSEO Connector. n8n is a platform the USER runs themselves (self-
hosted) or has their own paid account with (n8n Cloud) -- not something
Imperal can broker centrally. The user pastes their own n8n API key once,
Vault-encrypted via `ctx.secrets`, and every call runs against their own
n8n instance.

WHY TWO SECRETS (base_url + api_key), AND WHY base_url IS NOT AUTO-
DISCOVERED THE WAY Make.com's ZONE IS.

Make.com Connector auto-discovers its zone (eu1/eu2/us1/us2) because Make
only has a handful of known public hosts to probe. n8n has no such fixed
set: a self-hosted instance lives at whatever host:port/path the user
deployed it to, and n8n Cloud gives each account its own subdomain --
there is no finite list to probe. Per n8n's own docs
(docs.n8n.io/connect/n8n-api/authentication), every request goes to
`<base_url>/api/v1/...` where base_url is entirely instance-specific.
So the connect form asks for the base_url directly, as the first field
-- confirmed with Vlad 2026-08-18 (PREPARATION.md section 4, answer 2).

WHY `X-N8N-API-KEY`, NOT Bearer/Basic/`Token ...`.

n8n's own docs are explicit: the header is `X-N8N-API-KEY: <your-api-key>`
-- a different scheme from Make's `Authorization: Token ...` or
DataForSEO's Basic auth, so it is built here rather than assumed.

WHY `write_mode="both"`, SAME REASONING AS MAKE.COM CONNECTOR.

Declaring `write_mode="user"` would mean only the platform's generic
Secrets screen could write these -- leaving a first-time user with no
in-app screen explaining what an n8n API key even is or whether what they
pasted actually works. `write_mode="both"` keeps the platform Secrets
screen working AND lets this extension's own `connect_n8n` validate the
key against the user's own n8n instance *before* writing it.
"""

from imperal_sdk import Extension, ChatExtension

ext = Extension(
    "n8n-connector",
    version="0.1.0",
    display_name="n8n",
    description=(
        "Connect your own n8n instance (self-hosted or n8n Cloud) to see "
        "and manage your workflows from Imperal -- list workflows with "
        "their status, publish/unpublish them, run one on demand where "
        "your instance supports it, inspect executions, and manage "
        "credentials. Your n8n API key is verified against your own "
        "instance before it's saved."
    ),
    icon="icon.svg",
    actions_explicit=True,
    capabilities=["n8n:read", "n8n:write"],
)

chat = ChatExtension(
    ext,
    tool_name="n8n-connector",
    description="View and manage your n8n workflows, executions and credentials",
)

ext.secret(
    name="n8n_base_url",
    description=(
        "Base URL of your n8n instance, e.g. https://n8n.example.com "
        "(self-hosted) or https://your-org.app.n8n.cloud (n8n Cloud). "
        "No trailing slash needed."
    ),
    write_mode="both",
)
ext.secret(
    name="n8n_api_key",
    description=(
        "n8n API key -- create it in your n8n instance: Settings -> "
        "n8n API -> Create an API key. Verified against your instance "
        "before saving."
    ),
    write_mode="both",
)


@ext.health_check
async def health_check(ctx) -> bool:
    """Basic liveness check -- confirms the store surface is reachable."""
    await ctx.store.query("n8n_app_settings", limit=1)
    return True
