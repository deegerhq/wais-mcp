"""Tool: wais_discover — Find what a WAIS-compatible site offers."""

from .._tool_client import get_client


async def wais_discover(site_url: str) -> str:
    """Discover what a WAIS-compatible site offers. Call this first for any site.

    Fetches /.well-known/agents.json and returns a summary showing:
    - site.url and site.api_base_url (how the site identifies itself)
    - Available actions with their IDs, endpoints, methods, and parameters
    - Registration requirements, constraints, and payment info

    The agents.json is the source of truth. Use the action IDs and parameter
    schemas it defines when calling wais_execute.

    Args:
        site_url: The site's URL (e.g. "https://serphub.deeger.io").
    """
    client = get_client()

    try:
        manifest = await client.discover(site_url)
    except Exception as e:
        if "404" in str(e):
            return f"Site {site_url} does not have agents.json — it may not support WAIS."
        raise

    lines = [
        f"# {manifest.name}",
        f"{manifest.description}",
        "",
        f"site.url: {manifest.site_url or site_url}",
    ]
    if manifest.api_base_url != manifest.site_url:
        lines.append(f"site.api_base_url: {manifest.api_base_url} (resolved automatically by tools)")
    lines.append(f"WAIS version: {manifest.wais_version}")
    lines.append(f"Auth: {', '.join(manifest.auth_methods)}")

    req_claims, opt_claims = manifest.get_registration_claims()
    if req_claims:
        lines.append(f"Registration requires: {', '.join(req_claims)}")
    if opt_claims:
        lines.append(f"Registration optional: {', '.join(opt_claims)}")

    if manifest.constraints:
        lines.append(f"Constraints: {', '.join(f'{k} ({v})' for k, v in manifest.constraints.items())}")

    if manifest.payment:
        providers = ", ".join(manifest.payment.get("providers", []))
        currencies = ", ".join(manifest.payment.get("currencies", []))
        lines.append(f"Payment: {providers} ({currencies})")

    actions = manifest.list_actions()
    if actions:
        lines.append("")
        lines.append("## Actions")
        lines.append("")
        for action in actions:
            action_id = action.get("id", "?")
            desc = action.get("description", "")
            method = action.get("method", "?")
            endpoint = action.get("endpoint", "?")
            risk = action.get("risk_level", "standard")
            confirm = action.get("requires_confirmation", False)
            is_async = "async" in action

            flags = []
            if risk == "high":
                flags.append("high risk")
            if confirm:
                flags.append("requires confirmation")
            if action.get("requires_payment"):
                flags.append("requires payment")
            if is_async:
                flags.append("async")
            flag_str = f"  [{', '.join(flags)}]" if flags else ""

            lines.append(f"  - **{action_id}**: {desc}{flag_str}")
            lines.append(f"    {method} {endpoint}")

            input_schema = action.get("input_schema", {})
            props = input_schema.get("properties", {})
            required = input_schema.get("required", [])
            if props:
                lines.append(f"    Parameters:")
                for pname, pinfo in props.items():
                    ptype = pinfo.get("type", "?")
                    req = " (required)" if pname in required else ""
                    pdesc = pinfo.get("description", "")
                    enum = pinfo.get("enum")
                    extra = ""
                    if enum:
                        extra = f", options: {enum}"
                    elif pdesc:
                        extra = f", {pdesc}"
                    lines.append(f"      - {pname}: {ptype}{req}{extra}")
    else:
        scopes = manifest.raw.get("scopes", {})
        if scopes:
            lines.append("")
            lines.append("## Scopes:")
            for scope_name, scope_info in scopes.items():
                risk = scope_info.get("risk", "?")
                desc = scope_info.get("description", "")
                lines.append(f"  - {scope_name} [{risk}]: {desc}")

    return "\n".join(lines)
