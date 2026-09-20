# Validation and limitations

A Nix build proves packaging, not authenticated model routing or compression.

## Platforms

| System | Nix evaluation | Runtime |
| --- | --- | --- |
| `aarch64-darwin` | Pass | Headroom 0.37.0 proxy, writer, and local auth-adapter smoke pass |
| `aarch64-linux` | Pass | Unverified |
| `x86_64-linux` | Pass | Unverified |

The Codex app wrapper is macOS only. Consumer configs were not changed or activated.

## What was checked

On Apple Silicon macOS, with Headroom **0.37.0** (2026-09-16):

- 65 unit tests, 2 client-adapter tests, Ruff, nixfmt, anti-slop, and
  `nix flake check` (native plus all-systems eval)
- Runtime smoke: real proxies, 2 JSONC writer tests, Copilot adapter refresh
  against a local token endpoint (fake credentials; no GitHub auth or model requests)
- Shared lifecycle: sequential and simultaneous reuse, stop, dead/abandoned
  sockets, foreign listeners, Copilot reuse across model/env, editor path guards
  (editor processes are stand-ins)
- Real clients: Codex **0.154.0**, Pi **0.85.1**, OpenCode **2.0.3**, sandboxed
  local endpoints. `agent_routing_smoke.py`: 8 cases.
  `shared_agent_smoke.py`: 5/6, then 6/6 on repeat.

## Real clients

Codex and Pi both passed two concurrent clients under ordinary and wildcard proxy
settings: one managed fake proxy, two requests, both prompts. OpenCode's ordinary
case passed with nine requests, including serial init and auxiliary traffic.

**OpenCode 2.0.3 can fail concurrent private-server startup** with a JSON bootstrap
error. That also happens in plain OpenCode, without Kit, its plugin, Headroom, or
forward-proxy variables. Start sessions one at a time. A full repeat passed all
six cases; the flake is still real.

Pi/OpenCode provider routing (OpenAI/Anthropic, ordinary and wildcard proxy)
passed; no requests hit the conflicting endpoint, and config files stayed
unchanged. Local errors prove routing, not model support.

## Remaining limits

- Linux runtime, live Codex app routing, isolated editor chat, and remote editor hosts.
- Authenticated providers, Copilot enterprise domains/model combinations, and
  Pi/OpenCode custom provider runtimes. Pi routes `openai`, `openai-codex`
  (best effort), `anthropic`, and `github-copilot` (Headroom Copilot login;
  Claude/Gemini ids may not speak Responses). OpenCode routes `openai`, `anthropic`,
  `opencode` (Zen/free, best effort), and `github-copilot`. Other providers keep
  their normal routes.
- Compression quality under concurrent load.
- Consumer integration. Published revisions run Linux and macOS checks in the
  [release workflow](https://github.com/ruarfff/headroom-kit-nix/actions/workflows/tag.yml).

A new Copilot OAuth credential needs an explicit stop even for the same account.
If you kill the owner and Headroom survives, inspect the listener yourself; Kit
will not kill an unverified process. Interrupted model requests are not replayed.

Exact versions do not lock every Python dependency. Editor path checks cannot
catch concurrent symlink changes. [Stop older wrapper-owned proxies](usage.md#migration-and-rollback)
before replacing them.
