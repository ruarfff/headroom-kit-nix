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

## Native compression profiles

`tests/smoke_compression.py` runs real Headroom **0.37.0** with temporary homes,
fake credentials, and local HTTP providers. [Run it here](development.md#compression-comparison).

Before the change, two managed proxies reported **375 requests**, **196,808 saved
tokens**, and **31,780,255 input tokens**. These mixed-workload counters are a
baseline, not a controlled comparison. Only aggregate counters were read; live
proxies and ledgers were unchanged.

### Default-profile comparison

Thirty cases compare the old switches with the managed coding profile: JSON,
searches, logs, short output, and reads across three protocols, with and without
streaming. One Apple Silicon run produced:

| Measurement | Old switches | Native profile with OpenAI exception |
| --- | ---: | ---: |
| Fixture input tokens | 61,516 | 61,516 |
| Forwarded input tokens | 52,446 | 44,790 |
| Input reduction | 14.74% | 27.19% |
| Tool-schema tokens saved | 0 | 0 |
| Median compression-path time | 9.47 ms | 11.44 ms |
| Median request time | 10.69 ms | 13.20 ms |
| Proxy process startup | 1.76 s | 1.74 s |

The extra JSON savings (**5,032 → 1,204** forwarded tokens per Anthropic request)
come from **lossless tabular conversion**, not lossy compression. OpenAI results
stay unchanged. Counts use `cl100k_base` over serialized messages, not billing
usage. Small schemas do not exercise tool-search savings.

Timing is an uncontrolled local sample. Compression-path time includes HTTP,
parsing, queueing, and serialization; startup excludes uv and model downloads.

Reads, short output, tool calls, streaming, and stable prefixes pass. All four
profiles parse through the real CLI for every proxy kind. Selecting only `log`
leaves JSON unchanged; wrapper tests reject changed selections, including shared
Copilot, without weakening routing, auth, or privacy filters.

### Lossy compression and recovery

Two additional Anthropic cases use native **LogCompressor**, not a seeded store.
Each starts a fresh proxy and workspace with `log` selected, token mode, lossless
off, a 128-token minimum, and proactive CCR expansion off. Model downloads are
disabled for these cases.

| Client mode | Input tokens | Forwarded tokens | Lines omitted and recovered |
| --- | ---: | ---: | ---: |
| Non-streaming | 2,268 | 262 | 172 of 181 |
| Streaming | 2,267 | 255 | 172 of 181 |

Both passed with zero retrieval failures. The checks require the native
`router:tool_result:log` transform, its generated `Retrieve more: hash=…` marker,
the exact stored original, and every omitted line in the continuation's result. Compression or retrieval being skipped
fails the test. Forcing lossless mode fails as expected.

Counts cover the first provider request. Retrieval adds 114 tool-schema tokens
and a second request; this tests recovery, not net savings.

The streaming case returns complete SSE through Headroom's **buffered CCR path**;
both provider requests are non-streaming. This does not test native provider SSE
tool-call interception. Four seeded-store checks separately cover retrieval
transport for Anthropic and Responses; Responses declares the tool explicitly.

Kompress inference, production savings, cache-hit rates, and task quality remain
unmeasured. One run hit a native `recursive_mutex` abort; a repeat passed. Its
cause is unresolved. Live routing results below predate this compression change.

### OpenAI retrieval exception

The script reproduces three gaps in Headroom 0.37.0:

- Responses forwards the marker without injecting `headroom_retrieve`. Retrieval
  works only when the request already declares that tool.
- Direct non-streaming Chat injects the tool but returns its call to the client
  without continuation. This check does not cover the native backend adapter.
- Streaming Chat omits retrieval-tool injection; it cannot intercept the call.

Kit keeps a **native lossless OpenAI pipeline**, including OpenAI-wire Copilot.
Keep this exception until those routes pass automatic retrieval without
client-provided tooling. Anthropic and the routing/auth policies are unchanged.
See the [pinned handlers](https://github.com/headroomlabs-ai/headroom/blob/v0.37.0/headroom/proxy/handlers/openai.py).

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
