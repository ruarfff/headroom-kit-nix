# Usage and troubleshooting

Shared proxies, Pi, and OpenCode are available from **v0.1.1**. When upgrading from
v0.1.0, [stop the old wrapper-owned proxies](#migration-and-rollback) first.
Normal agent launches are unchanged.

## Codex CLI

Sign in with `codex login`, then launch from your project:

```sh
codex-headroom
codex-headroom resume --last
```

Kit keeps your sign-in, history, working directory, arguments, and terminal input.
Help and version requests skip Headroom. Only the built-in OpenAI provider is
supported; use normal Codex for custom or local providers. API-key routing is
[unverified](validation.md).

## Copilot CLI

1. Sign in with normal `copilot`, then exit it.
2. Authorize Headroom separately:

   ```sh
   headroom copilot-auth login
   ```

3. Use your normal model selection, or choose an available model:

   ```sh
   copilot-headroom
   copilot-headroom --model auto
   copilot-headroom --model <model-id>
   ```

Use the same account in Copilot and Headroom so model access matches. Routed
requests use Headroom's OAuth credential, with access tokens refreshed per
Copilot integration.

Copilot keeps its native catalog and chooses Responses, Completions, or Messages.
Kit leaves `COPILOT_MODEL`, `--model=...`, and `/model` selection to the client;
there is no Kit model list. Inherited `COPILOT_PROVIDER_*` settings are removed
from the child to prevent BYOK from replacing native routing. Use normal Copilot
for BYOK providers.

The CLI must support `COPILOT_API_URL`; **1.0.87-0** was tested. Older builds can
ignore it and bypass Headroom. Capability enforcement is
[issue #9](https://github.com/ruarfff/headroom-kit-nix/issues/9). See
[validation](validation.md#copilot-cli-model-routing) for tested models and limits,
including enterprise domains and interactive switching.

## Pi

Install [Pi](https://pi.dev) and configure your provider through its normal setup:

```sh
pi-headroom --provider openai --model <model-id>
pi-headroom --provider anthropic --model <model-id>
pi-headroom --provider github-copilot --model <model-id>
```

OpenAI and Anthropic use API keys. Copilot uses
[Headroom's login](#copilot-cli); a separate Pi Copilot login is not required.
An existing Pi login still controls model filtering and follows Pi's normal
refresh path. `openai-codex` with ChatGPT login is best effort and routes through
Headroom's `/v1/codex/responses` endpoint.

Kit loads a local extension for this process, even with `--no-extensions`.
Config, extensions, skills, history, resume, and print-mode arguments stay intact.
The extension pins Copilot's URL and placeholder token after auth resolution,
without replacing native protocols. Other providers keep their normal routes.

Tested with Pi **0.85.1**; see [validation](validation.md#pi-copilot-routing) and
[Pi providers](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/providers.md).

## OpenCode v2

Install [OpenCode v2](https://opencode.ai/v2/docs) and use `/connect` in normal
OpenCode to configure a provider. OpenAI and Anthropic need API keys. For Copilot,
connect GitHub there and [authorize Headroom](#copilot-cli) separately.

```sh
opencode-headroom
opencode-headroom run --model openai/<model-id> "Explain this project"
opencode-headroom run --model github-copilot/<model-id> "Explain this project"
```

Kit starts a private server and leaves the normal background service alone.
`opencode-headroom ./path` and `mini` also work; use normal `opencode` for account
and service commands. OpenCode v1 is rejected.

The local plugin routes `openai`, `anthropic`, `opencode` (Zen/free, best effort),
and `github-copilot`, including titles and compaction. It overrides per-model
endpoints and uses HTTP streaming, not WebSockets. Copilot keeps native model and
protocol selection, but model requests use the shared Copilot proxy and Headroom's
credential. Account catalog discovery stays native. Other providers are unchanged.

Kit appends the plugin to the child's `OPENCODE_CONFIG_CONTENT`, which must be a
JSON object. Existing inline settings and JSONC files stay intact. See
[OpenCode config](https://opencode.ai/v2/docs/config/) and
[plugins](https://opencode.ai/v2/docs/plugins/).

OpenCode **2.0.11** passed local and live routing checks; see
[validation](validation.md#opencode-copilot-routing), including the certificate
caveat. **2.0.3** can fail concurrent private-server startup even without Kit;
start sessions one at a time if you see a JSON bootstrap error.

## Copilot in VS Code

[Authorize Headroom](#copilot-cli) and install the Copilot extension for your channel:

```sh
copilot-vscode-headroom .
HEADROOM_VSCODE_CHANNEL=insiders copilot-vscode-headroom .
```

Kit opens a separate profile. **Normal settings are untouched; Settings Sync is
off.** Sign in to GitHub there if prompted. Repeat the command for another window.

Model requests use **Headroom's account**, even if the editor has another GitHub
credential. Use matching accounts for consistent model listings. Kit does not
touch the editor's credential store. Live GUI routing is unverified.

| Default location | Stable | Insiders |
| --- | --- | --- |
| macOS user data | `~/Library/Application Support/Code Headroom` | `~/Library/Application Support/Code - Insiders Headroom` |
| Linux user data | `${XDG_CONFIG_HOME:-~/.config}/Code Headroom` | `${XDG_CONFIG_HOME:-~/.config}/Code - Insiders Headroom` |
| Existing extensions | `~/.vscode/extensions` | `~/.vscode-insiders/extensions` |

[Path overrides](configuration.md#options) must use a **dedicated Kit profile**,
never normal editor data. Escaping `User` or settings-file symlinks are rejected.
Pass one file or folder, with no extra editor flags. Remote hosts, SSH, containers,
and WSL are unverified. See [Headroom's editor integration](https://docs.headroomlabs.ai/docs/vscode-copilot).

## Codex macOS app

Sign in through the app, select its built-in OpenAI provider, then **quit it**:

```sh
codex-app-headroom
```

Kit refuses an already-running app. The launcher returns after opening it; the
shared proxy stays up and Codex CLI can reuse it. A fresh Dock launch uses normal
settings. Routing uses undocumented hooks and has not been verified with live GUI
requests.

## Proxy lifetime

Compatible clients share a proxy. It stays up after clients and terminals exit;
there is no launchd or systemd service.

```sh
headroom-kit status
headroom-kit stop 8788
```

**Stop interrupts every client on that port.** It does not close clients or replay
requests. Status and stop use bundled Python without downloading Headroom.
Home Manager includes the control command. For individual packages, add
`headroom-kit-control` or use `nix run <kit-source>#headroom-kit -- status`.

| Route | Default port | Share when |
| --- | --- | --- |
| Codex CLI/app | 8788 | Same configuration |
| Copilot CLI/editor and Pi/OpenCode `github-copilot` | 8787 | Same Headroom OAuth credential |
| Pi | 8790 | Same configuration |
| OpenCode | 8791 | Same configuration; each client has its own OpenCode server |

A healthy port is not enough: incompatible proxies and unrelated listeners are
left alone. Stop the managed instance or choose another port. Storage and telemetry
settings also affect [compatibility](configuration.md#local-metrics-and-storage).

Copilot model and client environment changes do not prevent reuse. Access-token
rotation is handled automatically, but a **new OAuth credential requires a stop**,
even for the same account. Client sign-out does not revoke the proxy's credential.
For a second account, authorize Headroom for it and use another port:

```sh
HEADROOM_VSCODE_PORT=8789 copilot-vscode-headroom .
```

Locks and control sockets live in `/tmp/headroom-kit-<uid>`, without credentials or
PID files. Dead proxies recover on the next launch. If Headroom survives a killed
owner, inspect the listener yourself; Kit will not kill an unverified process.
Do not delete live locks or sockets. Stop proxies before garbage-collecting their
environment. Reboot stops them.

## Troubleshooting

| Problem | Check |
| --- | --- |
| Agent not found | Check `command -v`; set its [executable option](configuration.md#options) if needed |
| Runtime download fails | Check version, uv index access, cache permissions, and CA certificates; try `UV_NATIVE_TLS=true` if needed |
| Proxy never becomes ready | Try Headroom 0.37.0 and a free port; increase `HEADROOM_STARTUP_TIMEOUT` for slow startup |
| Port occupied | Inspect `headroom-kit status`; stop the managed port or choose another. Leave unknown listeners alone |
| Copilot auth/model failure | Check `headroom copilot-auth status`, matching accounts, and available model IDs (`gemini`, not `gemma`) |
| Copilot auth fails with custom CA settings | `SSL_CERT_FILE` can break token exchange and appear as a login failure; see [#8](https://github.com/ruarfff/headroom-kit-nix/issues/8). Do not disable certificate verification or assume another login will fix it |
| Editor settings conflict | Repair JSONC or conflicting endpoints in the isolated profile, then restart its wrapper |

Readiness failure stops the launch; there is no direct-connection fallback.
Raw proxy and resolver diagnostics are suppressed because they can contain credentials.

## Migration and rollback

Back up settings and remove only the old setup's endpoint overrides, including
shell exports. Keep credentials. Close old clients and stop their proxies from
the owner terminals. Kit's control commands cannot adopt v0.1.0 wrapper-owned
proxies. Check the ports are free; leave unknown listeners alone.

To leave Kit, close wrapped clients, stop its managed ports, remove Kit from your
package list, and rebuild. Use normal agent commands. The isolated editor profile
still points at Headroom until you delete it or unwrap it:

```sh
headroom unwrap vscode --settings-file '/path/to/isolated/User/settings.json'
```

## Privacy and routing

Managed proxies bind to `127.0.0.1`. External beacons, full message logging, and
learning are off. Kit creates no proxy log file. Credentials stay outside Nix
and source control, in memory or the normal credential stores.

CLI clients bypass forward proxies for loopback, keeping existing exclusions.
A wildcard `NO_PROXY` or `no_proxy` makes all client traffic direct and removes
proxy variables from the child. Headroom keeps the caller's upstream proxy policy;
the caller's environment is unchanged.

All wrappers use Headroom's native coding profile, with explicit profile and
compression overrides supported. OpenAI routes stay lossless until the pinned
release's CCR retrieval gaps are fixed; Anthropic uses the selected profile.
See [profile selection, downloads, and rollback](configuration.md#compression-profiles).
Semantic caching and rate limiting remain disabled for the Codex, Pi, and OpenCode
proxies; Copilot keeps its native defaults for those features.

[Metrics and storage settings](configuration.md#local-metrics-and-storage) also
pass through. Other inherited `HEADROOM_*` settings and upstream overrides are
still filtered. Direct `headroom` commands accept upstream flags and are unmanaged.
See [Headroom proxy controls](https://docs.headroomlabs.ai/docs/proxy).

## Metrics and retention

Persistence and local telemetry are on by default. This permits Headroom's normal
local state writes, not just counters; it does not enable external beacons or full
message logging.

- Per-proxy lifetime totals appear in the dashboard and in `/stats` at
  `persistent_savings.lifetime`; live process counters are separate. Graceful
  stops flush pending batches; abrupt termination can lose them.
- `headroom savings` reads the shared event ledger and retains only **30 days**,
  even where its JSON says `lifetime`. It is not an all-time report. Kit does not
  merge per-port counter files.

After upgrading, stop existing proxies and relaunch their wrappers. Previously
discarded history cannot be recovered. See [storage settings](configuration.md#local-metrics-and-storage),
[Headroom savings](https://docs.headroomlabs.ai/docs/savings), and
[metrics](https://docs.headroomlabs.ai/docs/metrics).

## Check routing and compression

A working dashboard proves startup, not routing. Compare selected-model request
counters before and after an authorized model call. A direct launch should not
increment them. Measure compression separately; see [validation](validation.md).
