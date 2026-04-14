"""CLI for wais-mcp: setup wizard and MCP server runner."""

import json
import os
import sys
from pathlib import Path


CLAUDE_GLOBAL_DIR = Path.home() / ".claude"
CLAUDE_GLOBAL_MCP = CLAUDE_GLOBAL_DIR / "claude_desktop_config.json"
PROJECT_MCP = Path(".mcp.json")

DEFAULT_PLATFORM_URL = "https://pod.deeger.io"

MCP_ENTRY = {
    "command": "wais-mcp",
    "env": {
        "PLATFORM_URL": DEFAULT_PLATFORM_URL,
        "WAIS_API_KEY": "",
    },
}

PROVIDERS = {
    "claude-code": {
        "name": "Claude Code",
        "project": Path(".mcp.json"),
        "global": CLAUDE_GLOBAL_DIR / "claude_desktop_config.json",
        "key": "mcpServers",
    },
    "claude-desktop": {
        "name": "Claude Desktop",
        "global": Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
        "key": "mcpServers",
    },
    "chatgpt": {
        "name": "ChatGPT Desktop",
        "global": Path.home() / "Library" / "Application Support" / "ChatGPT" / "mcp-server-config.json",
        "key": "mcpServers",
    },
    "cursor": {
        "name": "Cursor",
        "project": Path(".cursor") / "mcp.json",
        "global": Path.home() / ".cursor" / "mcp.json",
        "key": "mcpServers",
    },
    "windsurf": {
        "name": "Windsurf",
        "global": Path.home() / ".codeium" / "windsurf" / "mcp_config.json",
        "key": "mcpServers",
    },
    "vscode": {
        "name": "VS Code (Copilot)",
        "project": Path(".vscode") / "mcp.json",
        "key": "servers",
    },
    "gemini": {
        "name": "Gemini CLI",
        "project": Path(".gemini") / "settings.json",
        "global": Path.home() / ".gemini" / "settings.json",
        "key": "mcpServers",
    },
}


def _read_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {}


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def _pick_provider() -> str:
    print("\nWhich provider do you want to configure?\n")
    providers = list(PROVIDERS.items())
    for i, (key, info) in enumerate(providers, 1):
        print(f"  {i}. {info['name']}")
    print()

    while True:
        choice = input(f"Choose (1-{len(providers)}) [1]: ").strip() or "1"
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(providers):
                return providers[idx][0]
        except ValueError:
            pass
        print("Invalid choice, try again.")


def _pick_scope(provider_key: str) -> str:
    provider = PROVIDERS[provider_key]
    has_project = "project" in provider
    has_global = "global" in provider

    if has_project and has_global:
        print(f"\n  1. Project (./{provider['project']})")
        print(f"  2. Global  ({provider['global']})")
        while True:
            choice = input("\nScope (1-2) [1]: ").strip() or "1"
            if choice == "1":
                return "project"
            if choice == "2":
                return "global"
            print("Invalid choice.")
    elif has_project:
        return "project"
    else:
        return "global"


def cmd_init():
    """Interactive setup wizard for WAIS MCP."""
    print("🔧 wais-mcp setup\n")

    # 1. Pick provider
    provider_key = _pick_provider()
    provider = PROVIDERS[provider_key]

    # 2. Pick scope
    scope = _pick_scope(provider_key)
    config_path = provider[scope]

    # 3. Ask for API key
    print()
    api_key = input("WAIS API key (from pod.deeger.io dashboard): ").strip()
    if not api_key:
        print("⚠ No API key provided. You can set WAIS_API_KEY env var later.")

    # 4. Ask for platform URL
    platform_url = input(f"Platform URL [{DEFAULT_PLATFORM_URL}]: ").strip() or DEFAULT_PLATFORM_URL

    # 5. Build config
    servers_key = provider["key"]
    entry = {
        "command": "wais-mcp",
        "env": {
            "PLATFORM_URL": platform_url,
            "WAIS_API_KEY": api_key,
        },
    }

    # VS Code needs type field
    if provider_key == "vscode":
        entry["type"] = "stdio"

    # 6. Read existing config, merge, write
    config = _read_json(config_path)
    if servers_key not in config:
        config[servers_key] = {}
    config[servers_key]["wais"] = entry
    _write_json(config_path, config)

    print(f"\n✅ WAIS configured in {config_path}")
    print(f"   Provider: {provider['name']}")
    print(f"   Platform: {platform_url}")
    if provider_key in ("claude-desktop", "chatgpt"):
        print(f"\n   Restart {provider['name']} to activate.")
    else:
        print(f"\n   Ready to use!")


def main():
    """Entry point: run MCP server or CLI subcommands."""
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "init":
            cmd_init()
            return
        if cmd in ("-h", "--help", "help"):
            print("Usage:")
            print("  wais-mcp         Run the MCP server (used by MCP clients)")
            print("  wais-mcp init    Setup wizard — configure WAIS for your AI provider")
            print("  wais-mcp help    Show this help")
            return
        print(f"Unknown command: {cmd}")
        print("Run 'wais-mcp help' for usage.")
        sys.exit(1)

    # Default: run MCP server
    from .server import mcp
    mcp.run()
