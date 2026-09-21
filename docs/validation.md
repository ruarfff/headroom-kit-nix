# Validation and limitations

A build proves packaging, not model routing or compression. These results cover
the checked-out code; they do not apply to every release tag.

## Platforms

| System | Nix evaluation | Runtime |
| --- | --- | --- |
| `aarch64-darwin` | Pass | Headroom 0.37.0 runtime and routing checks pass |
| `aarch64-linux` | Pass | Unverified |
| `x86_64-linux` | Pass | Unverified |

The Codex app wrapper is macOS only. Consumer configurations were not changed or
activated during these checks.

## What was checked

On Apple Silicon macOS with Headroom **0.37.0**:

- Python and client-adapter tests, Ruff, nixfmt, anti-slop, native
  `nix flake check`, all-systems evaluation, and the package build.
- Real proxy startup, reuse, stop, stale sockets, foreign listeners, editor path
  guards, and local Copilot token refresh. Editor processes are stand-ins.
- Local routing and concurrent clients, using fake credentials and a network
  sandbox. Live Copilot checks are listed separately below.

See [development](development.md) for commands and prerequisites.

## Real clients

| Check | Coverage | Result |
| --- | --- | --- |
| Pi 0.85.1 routing | 18 Copilot cases; 4 OpenAI/Anthropic cases | 22/22 pass |
| OpenCode 2.0.11 routing | 12 Copilot cases; 4 OpenAI/Anthropic cases | 16/16 pass |
| Shared proxy | Two concurrent clients for Codex, Pi, and OpenCode; ordinary and wildcard proxy settings | 6/6 pass |

Copilot cases cover Claude, Gemini, and GPT with saved OAuth or an API key. Pi also
covers no saved login. Each Copilot model request reaches the intended local
endpoint with a placeholder token, not the cache proxy, conflicting endpoint, or
forward proxy. Config and fake credentials stay unchanged. Local rejections prove
routing, not authenticated model support.

**OpenCode 2.0.3 has an intermittent concurrent-startup failure**, also reproduced
without Kit. Start sessions one at a time if you see a JSON bootstrap error.
The current shared-client check passes with OpenCode 2.0.11.

## Copilot CLI model routing

With Copilot CLI **1.0.87-0**, the built package passed
`copilot_models_smoke.py` ([issue #4](https://github.com/ruarfff/headroom-kit-nix/issues/4)):

| Selection | Reply | Headroom request counter increase |
| --- | --- | --- |
| `gemini-3.8-flash` | `ok` | 1 |
| `gpt-5.4` | `ok` | 1 |
| `claude-sonnet-5` | `ok` | 1 |
| `auto` | `ok` | 1 |

All four launches used one proxy despite conflicting BYOK settings. Copilot owns
model and protocol selection; Kit uses `COPILOT_API_URL`, not OpenAI BYOK.
The reported `gemma-3.8-flash` ID was unavailable. The catalog's
`gemini-3.8-flash` works through Completions, not Responses.

## Pi Copilot routing

Pi **0.85.1** applies saved credentials after endpoint overrides. Kit now pins the
local URL and placeholder token in the native provider's auth result, keeping its
catalog, protocols, and saved-login refresh
([issue #5](https://github.com/ruarfff/headroom-kit-nix/issues/5)).

Live `claude-sonnet-5`, `gemini-3.8-flash`, and `gpt-5.4` requests each returned
`ok`, added one Copilot request, and appeared in per-model counters. The cache
proxy stayed unused; later launches reused both proxies. Test proxies were stopped.

## OpenCode Copilot routing

OpenCode **2.0.11** removed `ctx.catalog`, breaking plugin setup. Its Copilot SDK
also ignores the final `model.request` endpoint override. Kit now uses the model
API, retains the older catalog API, and redirects SDK fetches without replacing
native protocol selection
([issue #7](https://github.com/ruarfff/headroom-kit-nix/issues/7)). Removing the SDK
override from a temporary copy makes the real GPT routing check fail again.

The built package passed live checks with OpenCode **2.0.11**:

| Model | Reply | `requests.by_model` counter increase |
| --- | --- | --- |
| `claude-sonnet-5` | `ok` | 1 |
| `gemini-3.8-flash` | `ok` | 1 |
| `gpt-5.4` | `ok` | 1 |

The cache proxy stayed at zero. Later launches reused both proxies. Tools were
denied, storage was stateless, and both test proxies were stopped.

**Certificate caveat:** inherited `SSL_CERT_FILE` caused `RemoteDisconnected`
during token exchange, reported as an authorization failure. Unsetting it for the
test processes allowed authorization and model requests. TLS verification stayed
enabled; no persistent settings changed. This remains
[issue #8](https://github.com/ruarfff/headroom-kit-nix/issues/8).

## Persistent local metrics

With Nix Python **3.13** and temporary storage, two real Headroom processes each
recorded 23 synthetic requests. All 46 reached the shared ledger and
`headroom savings --json`. Graceful shutdown flushed pending counters; restarted
proxies exposed the saved totals through `/stats`. Telemetry opt-out and stateless
operation also passed, without provider credentials or model calls
([issue #6](https://github.com/ruarfff/headroom-kit-nix/issues/6)).

This does not prove recovery after abrupt termination or compression quality.
See [metrics and retention](usage.md#metrics-and-retention).

## Remaining limits

- [#8](https://github.com/ruarfff/headroom-kit-nix/issues/8): custom-CA negotiation
  and misleading authentication errors.
- [#9](https://github.com/ruarfff/headroom-kit-nix/issues/9): Copilot CLI capability
  checks. Older builds can ignore the endpoint override.
- [#10](https://github.com/ruarfff/headroom-kit-nix/issues/10): remaining live checks
  and interactive model switching.

Still unverified: Linux runtime, GUI chat, remote editor hosts, consumer
integration, Copilot enterprise domains, other authenticated model/provider
combinations, custom Pi/OpenCode provider runtimes, and compression under load.
Passing these checks does not establish every model or interactive switch.

See [proxy lifetime](usage.md#proxy-lifetime) for credential changes and process
recovery, and [migration](usage.md#migration-and-rollback) before replacing older
wrappers. Exact runtime versions do not lock every Python dependency; editor path
checks cannot prevent concurrent symlink changes.
