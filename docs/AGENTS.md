<!-- File: docs/AGENTS.md -->

# Documentation & Multi-Audience Knowledge Base Guide (`docs/`)

## 1. Playbook F Multi-Audience Persona Boundaries

All documentation must strictly respect target audience boundaries:

- **End-User Persona (`README.md`):**
  - Audience: Self-hosters and home lab users running official prebuilt Docker containers.
  - Content: Quick-start Docker instructions (`docker run`, `docker-compose.yml`), port mapping, and basic setup.
  - Boundary: Zero developer tooling, zero package building commands, and no deep architectural implementation details.
- **Operator / Admin Persona (`docs/configuration.md`):**
  - Audience: System administrators and advanced homelab operators.
  - Content: Complete environment variable reference (`DL_CLIENT`, uppercase client-prefixed settings), VPN/Gluetun
    proxy routing, RFC-1918 `NO_PROXY` bypass rules, multi-client aggregation, and troubleshooting.
- **Developer & Contributor Persona (`docs/development.md`, `docs/agents/*.md`):**
  - Audience: Core software engineers and open-source contributors.
  - Content: Local setup (`uv`, `npm`), test harnesses (`pytest`, Jest, Playwright), Basedpyright typing, pre-commit
    linting hooks, and release publishing workflows.
- **AI Agent & Governance Persona (`AGENTS.md`, `.agents/docs/*`):**
  - Audience: Autonomous subagents and orchestrators.
  - Content: Invariants, sandbox taxonomy, sequential task locks, and testing contracts.

## 2. Canonical Product Truth Alignment

- All documentation and examples must strictly align with `.agents/docs/product-truth.md`.
- Never invent endpoints, settings, or architectural behaviors not documented in canonical product truth.

## 3. Formatting & Terminology Mandates

- **First-Line File Headers:** Line 1 of every markdown file must comment its path: `<!-- File: <relpath> -->`.
- **Code Block Formatting:** Always use triple tildes (`~~~`) for code blocks; triple backticks are forbidden.
- **User-Centric Terminology:** Always use `Download Client` and explicit client names (e.g. `qBittorrent`,
  `Transmission`), never developer jargon like `Strategy`.
- **Client-Perspective Paths:** Explain filesystem paths from the Download Client's perspective (e.g. `/downloads`).
- **Copyable Commands:** Ensure all command snippets are copyable and specify the intended execution environment.
