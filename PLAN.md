# WAIS Ecosystem — 4 Package Split Plans

> Master document for spinning up Claude Code agents on each package.
> Each section is self-contained — can be given to a separate agent.
> Updated 2026-03-19 with audit of actual codebase state.

---

## Shared Context (READ FIRST)

### Current State

The entire WAIS ecosystem currently lives in ONE monorepo at `github.com/deegerhq/wais`.
Version: **0.2.0**. 181 tests passing. All core modules are complete and battle-tested
against a real integrator (SerpHub — serphub.deeger.io).

**The main work is EXTRACTION + POLISH, not rewriting from scratch.**

### Key Spec Decisions (from SerpHub integration)

1. **Audience Resolution**: `aud` in PoD token = `site.url` (discovery domain), NEVER `api_base_url`. Verifier accepts both domains. DPoP `htu` = exact request URL (routed to api_base_url).

2. **Hybrid Scope Model**: 3 levels — Standard WAIS scopes (~30 defined, fixed risk levels), Custom `x-` scopes (site-defined, must declare risk), Freeform actions (no scope, description-only).

3. **Risk Override Rule**: Sites can RAISE risk levels, NEVER lower them. `checkout.execute` is always at least "high" regardless of what the site declares.

4. **Async Resolution**: Unified `resolution` object for polling. Works for async APIs AND payment confirmation. Status codes: 202=pending, 200=completed, 422=failed, 410=expired.

5. **Payment Model**: WAIS never touches money. Sites include Stripe/PayPal payment links in 402 challenges. Agent polls for payment completion via `resolution` pattern.

6. **Platform Role**: A WAIS Provider (like pod.deeger.io) emits tokens and stores the user's digital passport (SD-JWT vault). It is NOT a payment processor. In the future, Anthropic/OpenAI/Google would be providers.

7. **Transport**: `Authorization: DPoP <token>` + `DPoP: <proof>` headers. Fallback: `X-WAIS-PoD: <token>` for backward compat.

### Known Bugs/Improvements

- `ConfirmationResponse.is_valid` → rename to `is_well_formed` (no crypto verification yet)
- Platform: SECRET_KEY should crash on startup if not set (no fallback)
- Platform: CSRF tokens needed on HTML forms
- MCP: `wais_confirm` polling works but needs better user feedback during wait

### Versions & Publishing

- Python: >=3.10
- All packages: MIT license
- Semantic versioning
- Published under `deeger-dev` GitHub org
- wais-pod and wais-validator on PyPI

---

# PACKAGE 1: wais-pod

## What it is
The core library that any site installs to verify WAIS tokens and become agent-friendly.
This is what SerpHub `pip install`s.

## Current state: 95% complete
All modules exist and work. This is mostly extraction from the monorepo + adding manifest.py.

## PyPI name: `wais-pod`
## GitHub repo: `deeger-dev/wais-pod`

## Directory Structure

```
wais-pod/
├── pod/
│   ├── __init__.py           # Public API exports + __version__ (EXISTS, 23 exports)
│   ├── token.py              # PoDToken, DelegationPayload, Constraints (EXISTS, COMPLETE)
│   ├── issuer.py             # PoDIssuer — create signed PoD tokens (EXISTS, COMPLETE)
│   ├── verifier.py           # PoDVerifier — 12-step verification chain (EXISTS, COMPLETE)
│   ├── dpop.py               # DPoP key gen, proof creation, verification (EXISTS, COMPLETE)
│   ├── sd_jwt.py             # SD-JWT credential creation/presentation/verification (EXISTS, COMPLETE)
│   ├── scopes.py             # ~30 standard scopes + hybrid model logic (EXISTS, COMPLETE)
│   ├── confirmation.py       # ConfirmationChallenge, PaymentInfo, Resolution (EXISTS, COMPLETE)
│   ├── site.py               # WAISAuth — drop-in FastAPI integration (EXISTS, COMPLETE)
│   └── manifest.py           # NEW — agents.json parser + URL resolver
├── tests/                    # 181 tests across 10 files (EXISTS)
│   ├── conftest.py
│   ├── test_token.py
│   ├── test_issuer.py
│   ├── test_verifier.py
│   ├── test_dpop.py          # Includes 8 htu comparison tests
│   ├── test_sd_jwt.py
│   ├── test_scopes.py
│   ├── test_confirmation.py
│   ├── test_site.py
│   ├── test_payment.py
│   └── test_manifest.py      # NEW
├── pyproject.toml
├── README.md
├── CHANGELOG.md
└── .github/
    └── workflows/
        └── ci.yml             # pytest + ruff + mypy on PR
```

## What already works (DO NOT REWRITE)

### pod/token.py — COMPLETE
- `PoDToken` with `typ="at+jwt"` (RFC 9068), backward compat with `"WAIS-PoD"`
- `client_id`, `scope` (space-separated), `cnf` (DPoP binding) — all implemented
- `DelegationPayload` with `has_scope()`, `has_all_scopes()`, `hash_user_id()`
- `Constraints` with `exceeds_amount()`, `needs_confirmation()`

### pod/issuer.py — COMPLETE
- `PoDIssuer.create_token()` accepts `agent_public_key_jwk` → computes JWK thumbprint → sets `cnf.jkt`
- Accepts `client_id`, emits `scope` as space-separated string
- `generate_keypair()` for ES256

### pod/verifier.py — COMPLETE
- 12-step verification: parse, typ check (at+jwt OR WAIS-PoD), alg, issuer, signature, token build, iat, exp, jti (no replay on access tokens), audience (multi-audience set), user_verified, scopes, DPoP
- `expected_audiences: set[str]` for site_url + api_base_url
- DPoP integration: if token has `cnf.jkt`, requires proof
- Lazy DPoPVerifier init, reused across calls

### pod/dpop.py — COMPLETE
- `DPoPKeyPair`: generate, create_proof, thumbprint, public_jwk
- `DPoPVerifier`: 11-step verification (parse, typ, alg, jwk, signature, htm, htu, iat, jti replay, thumbprint, ath)
- `_compare_htu()`: RFC 9449 compliant — case-insensitive scheme/host, trailing slash, default ports, query strip
- `_seen_jtis` with TTL eviction every 100 verifications
- Debug logging via `logger.getLogger("wais")`

### pod/sd_jwt.py — COMPLETE
- `SDJWTIssuer.create_credential()` — SHA-256 disclosure hashing
- `SDJWTHolder.create_presentation()` — selective disclosure
- `SDJWTVerifier.verify()` — signature + hash validation

### pod/scopes.py — COMPLETE
- ~30 standard scopes across 7 categories (Universal, E-Commerce, SaaS, Travel, Financial, Government, Healthcare)
- `is_standard_scope()`, `is_custom_scope()` (x- prefix), `risk_level()`, `validate_risk_override()`
- Convenience bundles: `ecommerce_full()`, `saas_full()`, `travel_full()`

### pod/confirmation.py — COMPLETE
- `ConfirmationChallenge` with `create()`, `is_expired`, `requires_payment`
- `PaymentInfo` with method, provider, amount, currency, url, expires_at
- `Resolution` with mode, endpoint, interval_seconds, max_attempts, timeout_seconds, statuses
- `ConfirmationResponse` (note: `is_valid` should be renamed to `is_well_formed`)

### pod/site.py — COMPLETE
- `WAISAuth(site_url, api_base_url, platform_urls)`
- `setup()` — JWKS fetch with 3 retries, backoff [1s, 2s]
- `verify()` — token extraction, `_get_public_url()` with X-Forwarded headers, full verification
- `require()` — FastAPI dependency factory, dual auth (API key + WAIS), ANY-of scope semantics
- `agents_json()` — generate agents.json response (new + legacy format)
- `extract_token()` — DPoP / Bearer / X-WAIS-PoD header parsing
- `WAIS_DEBUG=1` env var enables debug logging

## What needs to be done

### 1. NEW: pod/manifest.py

Parser for agents.json — used by both wais-mcp and wais-validator:

```python
class WAISManifest:
    """Parse and work with agents.json manifests."""

    @classmethod
    async def from_url(cls, url: str) -> "WAISManifest":
        """Fetch and parse agents.json from a site."""

    @classmethod
    def from_dict(cls, data: dict) -> "WAISManifest":
        """Parse from a dict (already loaded JSON)."""

    @property
    def site_url(self) -> str: ...

    @property
    def api_base_url(self) -> str:
        """Returns api_base_url if set, otherwise site_url."""

    def resolve_endpoint(self, action_id: str) -> str:
        """Full URL for an action: api_base_url + action.endpoint"""

    def get_action(self, action_id: str) -> Optional[dict]: ...
    def list_actions(self) -> list[dict]: ...

    def get_effective_risk(self, action_id: str) -> str:
        """Resolve risk level using hybrid model + override rules."""

    def get_required_scopes(self, action_id: str) -> list[str]: ...
    def get_all_scopes(self) -> list[str]: ...

    def is_async(self, action_id: str) -> bool: ...
    def get_resolution(self, action_id: str) -> Optional[Resolution]: ...

    def get_registration_claims(self) -> tuple[list[str], list[str]]:
        """Returns (required_claims, optional_claims)."""
```

### 2. Minor fixes
- Rename `ConfirmationResponse.is_valid` → `is_well_formed`
- Add `__version__` check in a test
- Extract shared test fixtures to `conftest.py`

### 3. Packaging for PyPI
- Clean pyproject.toml (remove platform/store/mcp optional deps)
- Write README.md with quick start
- CHANGELOG.md
- GitHub Actions CI (pytest + ruff + mypy)
- `pip install wais-pod` and `pip install wais-pod[fastapi]`

### pyproject.toml (cleaned for standalone)

```toml
[project]
name = "wais-pod"
version = "0.2.0"
description = "WAIS — Web Agent Interaction Standard. Core library for agent authentication and site integration."
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10"
authors = [{name = "Deeger", email = "hello@deeger.io"}]
keywords = ["ai", "agents", "authentication", "wais", "delegation"]
dependencies = [
    "cryptography>=41.0.0",
]

[project.optional-dependencies]
fastapi = ["fastapi>=0.100.0", "httpx>=0.25.0"]
dev = ["pytest>=7.0", "pytest-asyncio", "pytest-cov", "ruff", "mypy"]

[project.urls]
Homepage = "https://deeger.io"
Repository = "https://github.com/deeger-dev/wais-pod"
```

---

# PACKAGE 2: wais-validator

## What it is
CLI tool + library to validate agents.json compliance.
Used by integrators to verify their implementation.

## Current state: 0% — NEW PACKAGE
Nothing exists yet. Build from scratch, depends on wais-pod for scope definitions.

## PyPI name: `wais-validator`
## GitHub repo: `deeger-dev/wais-validator`

## Directory Structure

```
wais-validator/
├── wais_validator/
│   ├── __init__.py
│   ├── cli.py                 # CLI entry point
│   ├── validators/
│   │   ├── __init__.py
│   │   ├── schema.py          # Validate against JSON Schema
│   │   ├── endpoints.py       # Check declared endpoints respond
│   │   ├── scopes.py          # Verify scopes are valid WAIS or x-custom
│   │   ├── auth.py            # Check JWKS endpoints reachable
│   │   ├── risk.py            # Verify risk levels not lowered below spec
│   │   └── consistency.py     # Cross-field consistency checks
│   ├── reporter.py            # Format results (terminal, JSON)
│   └── scoring.py             # 0-100 compliance score
├── schemas/
│   └── agents-v0.1.schema.json
├── tests/
│   ├── test_schema.py
│   ├── test_endpoints.py
│   ├── test_scopes.py
│   ├── test_scoring.py
│   └── fixtures/
│       ├── valid_serphub.json
│       ├── invalid_missing_actions.json
│       └── invalid_lowered_risk.json
├── pyproject.toml
├── README.md
└── LICENSE
```

## CLI Usage

```bash
# Validate a live site
wais validate https://serphub.deeger.io

# Validate local file
wais validate --file ./agents.json

# JSON output for CI
wais validate https://serphub.deeger.io --format json

# Schema only (no HTTP)
wais validate https://serphub.deeger.io --schema-only
```

## Validation Checks

### 1. Schema (schema.py)
- Required: wais_version, site, authentication, actions
- Action fields: id, description, endpoint, method
- Custom scope pattern: `x-{name}.{action}`
- Resolution object if present: mode, endpoint, statuses

### 2. Scopes (scopes.py)
- Import from `wais-pod` Scopes class
- Standard scopes: verify exists in taxonomy
- Custom scopes: verify x- prefix
- No scope: warn (freeform — valid but not recommended)

### 3. Risk (risk.py)
- Standard scopes: verify risk not LOWER than WAIS minimum
- Custom scopes: accept any declared risk
- `requires_confirmation: true` should have risk >= high

### 4. Endpoints (endpoints.py)
- Resolve: api_base_url + action.endpoint
- HEAD/OPTIONS request (never POST — could trigger actions)
- Report: responds / 404 / 500 / timeout

### 5. Auth (auth.py)
- Fetch `{issuer}/.well-known/jwks.json`
- Verify valid JWKS with at least one ES256 key

### 6. Consistency (consistency.py)
- site.url must be HTTPS
- api_base_url must be HTTPS if present
- No duplicate action IDs
- `requires_payment: true` → risk should be high+

### Scoring (scoring.py)

| Category | Points | Method |
|----------|--------|--------|
| Schema valid | 30 | pass/fail |
| Scopes valid | 15 | proportional |
| Risk levels correct | 15 | proportional |
| Endpoints respond | 20 | proportional |
| Auth reachable | 10 | pass/fail |
| Consistency | 10 | proportional |

Grades: A (90+), B (75-89), C (50-74), D (25-49), F (0-24)

### pyproject.toml

```toml
[project]
name = "wais-validator"
version = "0.1.0"
description = "Validate WAIS agents.json compliance. CLI + library."
dependencies = [
    "wais-pod>=0.2.0",
    "httpx>=0.25.0",
    "jsonschema>=4.20.0",
    "rich>=13.0.0",
]

[project.scripts]
wais = "wais_validator.cli:main"
```

---

# PACKAGE 3: wais-platform

## What it is
The reference WAIS Provider — pod.deeger.io. Emits tokens, manages user data vault.
This is Deeger's infrastructure, not something others install.

## Current state: 80% complete
FastAPI app works, SQLite persistence, Google OAuth, JWKS. Needs security hardening
and proper config management.

## GitHub repo: `deeger-dev/wais-platform`

## What already works (DO NOT REWRITE)

### pod_platform/app.py — routes
- `GET /healthz` — health + version
- `GET /.well-known/jwks.json` — JWKS endpoint
- `GET /auth/login` — Google OAuth redirect
- `GET /auth/callback` — OAuth callback
- `POST /api/tokens` — create PoD token (accepts dpop_jwk for binding)
- `GET /api/tokens` — list user tokens
- `DELETE /api/tokens/{jti}` — revoke token
- `POST /api/vault/data` — store personal data
- `GET /api/vault/data` — list claim names
- `POST /api/vault/present` — create SD-JWT presentation
- `POST /api/keys` — create API key
- `GET /api/keys` — list API keys
- HTML dashboard routes

### pod_platform/models.py — SQLite persistence (COMPLETE)
- Tables: users, tokens, api_keys, vault_data, vault_credentials
- WAL mode, foreign keys enabled
- DB at `./data/platform.db` (DATA_DIR env var)
- Full CRUD for all tables

## What needs to be done

### 1. CRITICAL: config.py — settings with validation

```python
# platform/config.py — NEW
import os

class Settings:
    def __init__(self):
        self.SECRET_KEY = os.environ["SECRET_KEY"]  # Crash if missing
        self.GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
        self.GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
        self.DATA_DIR = os.environ.get("DATA_DIR", "./data")

settings = Settings()  # Crashes on import if SECRET_KEY missing
```

### 2. CRITICAL: CSRF middleware

```python
# Skip CSRF for /api/* routes (they use PoD tokens)
# HTML form submissions must include csrf_token from session
# All templates: <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
```

### 3. Refactor into modules
Current: everything in one app.py. Split into:
- `routes/auth.py` — login, callback
- `routes/tokens.py` — token CRUD
- `routes/vault.py` — vault CRUD + SD-JWT
- `routes/keys.py` — API key management

### 4. Deploy infrastructure
- `deploy/` directory with systemd unit, nginx config, .env template
- Document the rsync deploy pattern (exclude data/, __pycache__)

### Production
- Server: Hetzner CX22 (89.167.116.156), Ubuntu 24.04
- Domain: pod.deeger.io (nginx + certbot)
- Service: systemd (wais-platform), user: wais
- DB: /opt/wais/pod_platform/data/platform.db (excluded from rsync)

---

# PACKAGE 4: wais-mcp

## What it is
Universal MCP server with 5 generic tools that work with ANY WAIS-compatible site.
Installed in Claude Desktop or any MCP client.

## Current state: 90% complete
All 5 tools work. Tested end-to-end with SerpHub. Needs refactoring into modules.

## GitHub repo: `deeger-dev/wais-mcp`

## What already works (DO NOT REWRITE)

### mcp_server/server.py — single file, 760 lines
**5 tools**: wais_discover, wais_register, wais_execute, wais_confirm, wais_status

**Working features:**
- DPoP keypair per session (`DPoPKeyPair.generate()`)
- `_auth_headers()` — builds Authorization + DPoP headers per request
- Token cache by (audience, sorted_scopes) with 60s buffer before expiry
- Site data cache with auto-discovery fallback
- URL normalization for cache lookups
- Async polling (`_poll_for_result`)
- 402 confirmation challenge handling with resolution storage
- Invalid action_id returns list of valid ones
- API key from env or macOS Keychain
- Server instructions explaining agents.json structure
- Error messages with contextual hints

**Tested flows (working with SerpHub):**
- discover → shows all 8 actions with params
- register → SD-JWT selective disclosure (email only)
- execute "list_jobs" → GET with DPoP ✓
- execute "get_job" → GET with path interpolation ✓
- execute "search" → POST async with polling ✓
- execute "list_plans" → GET ✓
- execute "get_usage" → GET ✓
- status → aggregates from get_usage action ✓

## What needs to be done

### 1. Refactor into modules

Extract from single file into:
```
wais_mcp/
├── server.py          # FastMCP setup + instructions
├── session.py         # DPoP keypair, token cache, site cache
├── tools/
│   ├── discover.py
│   ├── register.py
│   ├── execute.py
│   ├── confirm.py
│   └── status.py
├── auth.py            # _get_token, _auth_headers
├── polling.py         # _poll_for_result
└── http.py            # HTTP client with DPoP injection
```

### 2. Use WAISManifest from wais-pod
Replace inline `_get_site_data()`, `_find_action()`, `_get_all_scopes()`, etc.
with `WAISManifest` class (once manifest.py is created in wais-pod).

### 3. Better error handling for 500s
Currently `resp.raise_for_status()` gives generic httpx error.
Catch and return the response body if available.

### 4. Claude Desktop config

```json
{
  "mcpServers": {
    "wais": {
      "command": "wais-mcp",
      "env": {
        "WAIS_PLATFORM_URL": "https://pod.deeger.io",
        "WAIS_API_KEY": "<from platform dashboard>"
      }
    }
  }
}
```

### pyproject.toml

```toml
[project]
name = "wais-mcp"
version = "0.2.0"
description = "Universal WAIS MCP server — 5 tools for any WAIS-compatible site"
dependencies = [
    "wais-pod>=0.2.0",
    "mcp>=1.0.0",
    "httpx>=0.25.0",
]

[project.scripts]
wais-mcp = "wais_mcp.server:main"
```

---

## Dependency Graph

```
wais-pod (core library, zero heavy deps)
  ↑
  ├── wais-validator (imports Scopes, WAISManifest)
  ├── wais-platform (imports PoDIssuer, PoDVerifier, SDJWTIssuer, DPoPVerifier)
  └── wais-mcp (imports DPoPKeyPair, WAISManifest)
```

`wais-pod` is the foundation. The other three depend on it but NOT on each other.

## Build Order

1. **wais-pod** — Extract, add manifest.py, publish to PyPI. Everything else depends on this.
2. **wais-validator** + **wais-platform** — Can start in parallel once wais-pod is on PyPI.
3. **wais-mcp** — Can start once wais-pod manifest.py exists.
4. **Integration testing** — End-to-end across all 4 packages.

## For Claude Code Agents

Each agent gets:
1. This document (shared context + their package section)
2. The source code from the monorepo as reference
3. The addendum documents (1: hybrid scopes, 2: payment, 3: async/schema)

They do NOT need the full history of debugging — just the spec decisions and current code.
