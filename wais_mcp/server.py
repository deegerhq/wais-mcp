"""Universal WAIS MCP Server.

5 generic tools that work with ANY WAIS-compatible site:
  - wais_discover: Find what a site offers (agents.json)
  - wais_register: Register at a site using SD-JWT identity
  - wais_execute: Perform actions at a site (search, subscribe, etc.)
  - wais_confirm: Confirm high-risk actions or complete payments
  - wais_status: Check auth/subscription status at a site

Configuration:
    PLATFORM_URL: URL of the WAIS Provider (default: https://pod.deeger.io)
    WAIS_API_KEY: API key from the provider dashboard
                  Falls back to macOS Keychain (service: wais-api)
"""

from mcp.server.fastmcp import FastMCP

from .tools.confirm import wais_confirm
from .tools.discover import wais_discover
from .tools.execute import wais_execute
from .tools.register import wais_register
from .tools.status import wais_status

mcp = FastMCP(
    "wais-agent",
    instructions="""\
You have access to WAIS (Web Agent Interaction Standard) tools that let you \
interact with any WAIS-compatible website on behalf of the user.

## How agents.json works

Every WAIS site publishes a manifest at /.well-known/agents.json. \
wais_discover fetches and shows it to you. The key structure:

- **site.url**: The site's identity (e.g. "https://serphub.deeger.io"). \
This is what you pass as site_url to all tools.
- **site.api_base_url** (optional): Where HTTP requests actually go if the \
API lives on a different domain. The tools handle this routing for you.
- **actions[]**: Each action has an id, endpoint, method, and input_schema. \
You use the action id and input_schema parameters with wais_execute.
- **data_requirements.registration**: What claims the site needs to register.

## Workflow

1. **wais_discover(site_url)** — Call first. Shows the agents.json summary \
with all available actions and their parameters.
2. **wais_register(site_url)** — Register using WAIS identity before \
using authenticated actions.
3. **wais_execute(site_url, action_id, params)** — Run an action. Pass \
the site.url as site_url, the action id from agents.json, and params \
matching the action's input_schema. The tool resolves the endpoint, \
api_base_url, tokens, and DPoP automatically.
4. **wais_confirm(site_url, challenge_id)** — Only after a 402 challenge \
from wais_execute. Ask the user for approval first.
5. **wais_status(site_url)** — Check account status, plan, credits.
""",
)

# Register all tools
mcp.tool()(wais_discover)
mcp.tool()(wais_register)
mcp.tool()(wais_execute)
mcp.tool()(wais_confirm)
mcp.tool()(wais_status)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
