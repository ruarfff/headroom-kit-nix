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

## Copilot CLI model routing

Issue [#4](https://github.com/ruarfff/headroom-kit-nix/issues/4) was checked on
Apple Silicon macOS with Headroom **0.37.0** and Copilot CLI **1.0.87-0**.

The reported `gemma-3.8-flash` ID is unavailable to the tested account, including
in native Copilot. Both BYOK wires reject it. The catalog lists
`gemini-3.8-flash`: Responses rejects that model; Completions answers successfully.

Kit now uses Copilot's native `COPILOT_API_URL` override instead of OpenAI BYOK.
The built package passed `copilot_models_smoke.py` with:

| Selection | Reply | Headroom request counter increase |
| --- | --- | --- |
| `gemini-3.8-flash` | `ok` | 1 |
| `gpt-5.4` | `ok` | 1 |
| `claude-sonnet-5` | `ok` | 1 |
| `auto` | `ok` | 1 |

All four launches reused one proxy, despite inherited BYOK overrides. These are
live routing checks, not a claim that every catalog model or interactive `/model`
switch has been tested. Unit tests check argument/environment preservation,
BYOK removal, and both Copilot upstreams. Copilot owns model and wire selection;
there is no Kit model allowlist.

Checks after the change: 78 Python tests, 4 client-adapter tests, native
`nix flake check`, all-systems evaluation, anti-slop, and the real-runtime smoke
passed. The fake-token auth check covers Responses, Completions, Messages, and
model discovery without contacting GitHub.

## Pi and OpenCode Copilot routing

The Pi **0.85.1** check returned `ok` for `claude-sonnet-5`, but did **not**
increase the Copilot proxy counters. A loopback relay at the configured endpoint
also received zero POSTs. This is a routing failure, tracked in
[issue #5](https://github.com/ruarfff/headroom-kit-nix/issues/5), not a successful
Headroom check.

OpenCode's first live Copilot check was skipped because no models were connected.
After login, OpenCode **2.0.11** listed Copilot models and Headroom's live OAuth
check passed. Wrapped requests for `claude-sonnet-5`, `gemini-3.8-flash`, and
`gpt-5.4` each returned `ok`, but neither proxy's request counters increased.
Later launches reused the Copilot proxy; the failure was not startup or login.

A second OpenCode check used local endpoints that reject every request. Claude
still returned `ok`, and neither endpoint received a request. This confirms a
routing bypass, tracked in [issue #7](https://github.com/ruarfff/headroom-kit-nix/issues/7).
The temporary proxies were stopped. Neither client adapter was changed for #4.

## Remaining limits

Follow-up work is tracked in issues, not implied by passing checks:

- [#5](https://github.com/ruarfff/headroom-kit-nix/issues/5) and
  [#7](https://github.com/ruarfff/headroom-kit-nix/issues/7): Pi/OpenCode Copilot bypasses.
- [#6](https://github.com/ruarfff/headroom-kit-nix/issues/6): metrics across proxy restarts.
- [#8](https://github.com/ruarfff/headroom-kit-nix/issues/8): custom-CA TLS negotiation
  and misleading authentication errors.
- [#9](https://github.com/ruarfff/headroom-kit-nix/issues/9): native Copilot CLI
  capability checks and unsupported-build rejection.
- [#10](https://github.com/ruarfff/headroom-kit-nix/issues/10): remaining live
  checks, interactive model switching, and stronger routing regressions.

The unverified coverage includes:

- Linux runtime, live Codex app routing, isolated editor chat, and remote editor hosts.
- Other authenticated provider/model combinations, Copilot enterprise domains, and
  Pi/OpenCode custom provider runtimes. Pi routes `openai`, `openai-codex`
  (best effort), `anthropic`, and `github-copilot` (Headroom Copilot login;
  native client, token swap). OpenCode routes `openai`, `anthropic`,
  `opencode` (Zen/free, best effort), and `github-copilot`. Other providers keep
  their normal routes. Pi/OpenCode Copilot routing has the confirmed bypasses above.
- Compression quality under concurrent load.
- Consumer integration. Published revisions run Linux and macOS checks in the
  [release workflow](https://github.com/ruarfff/headroom-kit-nix/actions/workflows/tag.yml).

A new Copilot OAuth credential needs an explicit stop even for the same account.
If you kill the owner and Headroom survives, inspect the listener yourself; Kit
will not kill an unverified process. Interrupted model requests are not replayed.

Exact versions do not lock every Python dependency. Editor path checks cannot
catch concurrent symlink changes. [Stop older wrapper-owned proxies](usage.md#migration-and-rollback)
before replacing them.
