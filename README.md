# wais-mcp

Universal MCP server for [WAIS (Web Agent Interaction Standard)](https://deeger.io) — 5 generic tools that work with **any** WAIS-compatible site.

Works with Claude, ChatGPT, Gemini, Cursor, Windsurf, VS Code Copilot, and any MCP-compatible client.

## Tools

| Tool | Description |
|------|-------------|
| `wais_discover` | Fetch a site's `agents.json` and show available actions |
| `wais_register` | Register at a site using SD-JWT selective disclosure |
| `wais_execute` | Execute any action (search, subscribe, purchase, etc.) |
| `wais_confirm` | Confirm high-risk actions or complete payments (402 flow) |
| `wais_status` | Check account status, plan, and credits |

## Quick Start

```bash
pip install wais-mcp
wais-mcp init
```

The setup wizard will ask you to pick your provider (Claude, ChatGPT, Cursor, etc.), choose project or global scope, and enter your API key. It writes the correct config file automatically.

## Manual Setup by Provider

If you prefer to configure manually, all providers use the same `wais-mcp` command — only the config file location and format differ.

### Claude Desktop

File: `claude_desktop_config.json`

```json
{
  "mcpServers": {
    "wais": {
      "command": "wais-mcp",
      "env": {
        "PLATFORM_URL": "https://pod.deeger.io",
        "WAIS_API_KEY": "<your-api-key>"
      }
    }
  }
}
```

### Claude Code

File: `.mcp.json` (project root) or `~/.claude/settings.json` (global)

```json
{
  "mcpServers": {
    "wais": {
      "command": "wais-mcp",
      "env": {
        "PLATFORM_URL": "https://pod.deeger.io",
        "WAIS_API_KEY": "<your-api-key>"
      }
    }
  }
}
```

### ChatGPT Desktop

Requires Developer Mode: **Settings > Advanced Settings > Developer Mode**.

File locations:
- **macOS:** `~/Library/Application Support/ChatGPT/mcp-server-config.json`
- **Windows:** `%APPDATA%\OpenAI\ChatGPT\mcp-server-config.json`
- **Linux:** `~/.config/ChatGPT/mcp-server-config.json`

```json
{
  "mcpServers": {
    "wais": {
      "command": "wais-mcp",
      "env": {
        "PLATFORM_URL": "https://pod.deeger.io",
        "WAIS_API_KEY": "<your-api-key>"
      }
    }
  }
}
```

Restart ChatGPT after saving.

### Gemini CLI

File: `~/.gemini/settings.json` (global) or `.gemini/settings.json` (project)

```json
{
  "mcpServers": {
    "wais": {
      "command": "wais-mcp",
      "env": {
        "PLATFORM_URL": "https://pod.deeger.io",
        "WAIS_API_KEY": "<your-api-key>"
      }
    }
  }
}
```

### Cursor

File: `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global)

```json
{
  "mcpServers": {
    "wais": {
      "command": "wais-mcp",
      "env": {
        "PLATFORM_URL": "https://pod.deeger.io",
        "WAIS_API_KEY": "<your-api-key>"
      }
    }
  }
}
```

### Windsurf

File: `~/.codeium/windsurf/mcp_config.json`

Or open from Windsurf: click **MCPs** icon in Cascade panel > **Configure**.

```json
{
  "mcpServers": {
    "wais": {
      "command": "wais-mcp",
      "env": {
        "PLATFORM_URL": "https://pod.deeger.io",
        "WAIS_API_KEY": "<your-api-key>"
      }
    }
  }
}
```

### VS Code (GitHub Copilot)

File: `.vscode/mcp.json` (project) or via Command Palette: `MCP: Open User Configuration` (global)

```json
{
  "servers": {
    "wais": {
      "type": "stdio",
      "command": "wais-mcp",
      "env": {
        "PLATFORM_URL": "https://pod.deeger.io",
        "WAIS_API_KEY": "<your-api-key>"
      }
    }
  }
}
```

> Note: VS Code uses `servers` instead of `mcpServers`, and requires the `type` field.

## Usage without MCP (Python SDK)

For custom agents, scripts, or any Python code — no MCP client needed:

```python
import asyncio
from wais_mcp import WAISClient

async def main():
    client = WAISClient(api_key="your-api-key")

    # 1. Discover what the site offers
    site = await client.discover("https://serphub.deeger.io")
    print(site.name, site.list_action_ids())

    # 2. Register (shares only required claims via SD-JWT)
    await client.register(site)

    # 3. Execute actions
    result = await client.execute(site, "search", {"query": "python"})
    print(result)

    # 4. Confirm high-risk actions (if 402 returned)
    # result = await client.confirm(site, challenge_id)

    # 5. Check account status
    status = await client.status(site)
    print(status)

asyncio.run(main())
```

Works with OpenAI SDK, LangChain, CrewAI, or any Python agent framework.

## How It Works

1. **Discover** — Fetches `/.well-known/agents.json` from a site
2. **Register** — Shares only required claims via SD-JWT selective disclosure
3. **Execute** — Handles tokens, DPoP, endpoint resolution, and async polling automatically
4. **Confirm** — Polls for completion after 402 confirmation challenges
5. **Status** — Check credits and plan info

All authentication (PoD tokens, DPoP proofs) is handled transparently.

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `PLATFORM_URL` | `https://pod.deeger.io` | WAIS Provider URL |
| `WAIS_API_KEY` | _(keychain fallback on macOS)_ | API key from provider dashboard |

## Development

```bash
pip install -e ".[dev]"
```

## License

MIT
