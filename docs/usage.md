# Usage and troubleshooting

Shared proxies, Pi, and OpenCode are available from **v0.1.1**.
When upgrading from v0.1.0, follow [migration](#migration-and-rollback) to stop its
wrapper-owned proxies first.

## Codex CLI

Sign in with `codex login`, then launch from your project:

```sh
codex-headroom
# or resume a session
codex-headroom resume --last
```

Kit keeps your sign-in, history, working directory, arguments, and terminal input.
Help and version requests skip Headroom startup. The wrapper supports Codex's
built-in OpenAI provider; use normal Codex for custom or local providers.
API-key routing remains [unverified](validation.md).

## Copilot CLI

1. Sign in with the normal `copilot` CLI, then exit it.
2. Authorize Headroom separately:

   ```sh
   headroom copilot-auth login
   ```

3. Choose a model available to your account:

   ```sh
   copilot-headroom --model <model-id>
   ```

An explicit model is required; automatic selection does not carry over to this
route. If a model fails, test it in normal Copilot and select a supported model.
Kit uses subscription authorization and the Responses API. The shared proxy pins
Headroom's OAuth credential and refreshes access tokens for each Copilot client
integration. API-token-only authorization is refused. Subscription routing is
experimental; authenticated-provider tests and custom enterprise domains are unverified.

## Pi

Install [Pi](https://pi.dev), then configure an OpenAI or Anthropic **API key**
through Pi's normal credential setup or environment. Launch from your project:

```sh
pi-headroom --provider openai --model <model-id>
# Or use Anthropic:
pi-headroom --provider anthropic --model <model-id>
```

Pi keeps its configuration, model catalog, extensions, skills, history, and sign-in.
Kit loads a local extension for this process only; it also loads when you pass
`--no-extensions`. Resume and print-mode arguments pass through unchanged.
See [Pi provider configuration](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/providers.md).

Only the `openai` and `anthropic` providers are routed. Other providers retain their
normal routes. Subscription authentication, custom provider runtimes, and extensions
that replace routing are unverified.

## OpenCode v2

Install [OpenCode v2](https://opencode.ai/v2/docs), then use its normal `/connect`
workflow to configure an OpenAI or Anthropic **API key** and select a model:

```sh
opencode-headroom
# Or run a prompt with an explicit model:
opencode-headroom run --model openai/<model-id> "Explain this project"
```

Kit starts a private server with the existing configuration and credentials.
The normal background service stays unchanged. Use `opencode-headroom ./path`
for another directory or `opencode-headroom mini` for the minimal interface.
Use normal `opencode` for account, service, and other management commands.

OpenCode 2.0.3 can fail during simultaneous private-server startup with a JSON
bootstrap error, including without Kit. If this occurs, start sessions one at a
time. See [validation details](validation.md#real-clients).

A local plugin routes `openai` and `anthropic` requests, including titles and
compaction, through Headroom. It overrides per-model endpoints and uses HTTP
streaming instead of WebSockets. Other providers retain their normal routes.
Subscription authentication and custom provider runtimes are unverified.

Kit appends its plugin to the child process's `OPENCODE_CONFIG_CONTENT`; existing
inline settings and plugins are preserved. This variable must contain a JSON
object. Normal JSONC files remain supported and unchanged. OpenCode v1 is rejected.
See [OpenCode configuration](https://opencode.ai/v2/docs/config/) and
[plugins](https://opencode.ai/v2/docs/plugins/).

## Copilot in VS Code

Complete [Headroom authorization](#copilot-cli), ensure the Copilot extension is
installed for your chosen channel, then run:

```sh
copilot-vscode-headroom .
# For Insiders:
HEADROOM_VSCODE_CHANNEL=insiders copilot-vscode-headroom .
```

Kit opens a separate profile after the proxy is ready. **Normal settings stay
unchanged and Settings Sync is off.** Sign in to GitHub in the new profile if
prompted, then use the editor's model picker. Repeat the command to open another
window in the same isolated instance. Its startup lock is released after opening.

**Routed model requests use Headroom's authorized account**, including when the
editor holds another GitHub credential. Use the same account in both for consistent
model listings. The editor still owns its sign-in and other GitHub features;
Kit does not read or change its credential store. Live GUI routing is unverified.

| Default location | Stable | Insiders |
| --- | --- | --- |
| macOS user data | `~/Library/Application Support/Code Headroom` | `~/Library/Application Support/Code - Insiders Headroom` |
| Linux user data | `${XDG_CONFIG_HOME:-~/.config}/Code Headroom` | `${XDG_CONFIG_HOME:-~/.config}/Code - Insiders Headroom` |
| Existing extensions | `~/.vscode/extensions` | `~/.vscode-insiders/extensions` |

[Override these paths](configuration.md#options) only with a **dedicated Kit
profile**. Settings and `User` symlinks that escape it are rejected. Keep the paths
unchanged during startup; the checks cannot prevent concurrent symlink changes.
Kit cannot identify every custom normal profile, so choose a separate directory.

The launcher accepts one folder or file, not arbitrary editor flags. Remote
extension hosts, SSH, containers, and WSL are unverified. See
[Headroom's editor integration](https://docs.headroomlabs.ai/docs/vscode-copilot).

## Codex macOS app

Sign in through the app's normal workflow, use its built-in OpenAI provider,
then **quit the app** before running:

```sh
codex-app-headroom
```

An already-running app is refused. The launcher returns after opening the app;
its shared proxy remains running. Codex CLI sessions can use the same proxy.
This route uses undocumented hooks and still needs live GUI validation.
A fresh Dock launch uses the app's normal settings.

## Proxy lifetime

Wrappers start a compatible proxy automatically. Repeated and simultaneous launches
share it. Clients and terminals can exit without stopping it; there is no client
reference count, launchd job, or systemd service.

```sh
headroom-kit status
headroom-kit stop 8788
```

**Stopping a shared proxy interrupts every attached client.** It does not close
clients or replay interrupted requests. The next wrapper launch starts a new proxy.
Status/stop use bundled Python and do not download Headroom or authenticate.
For an individual package installation, use `nix run <kit-source>#headroom-kit -- status`
or install `headroom-kit-control`. Home Manager includes the control command.

| Route | Default port | Sharing |
| --- | --- | --- |
| Codex CLI/app | 8788 | Same configuration |
| Copilot CLI/editor | 8787 | Same Headroom OAuth credential; model and client env do not matter |
| Pi | 8790 | Same configuration |
| OpenCode | 8791 | Same configuration; each client keeps its private OpenCode server |

Copilot CLI and editor launches share one proxy when Headroom version, Kit code,
and the Headroom OAuth credential match. `--model`, `--reasoning-effort`, uv's
Python path, and pane environment do not mint a new proxy. Codex, Pi, and OpenCode
still require matching upstream credentials and proxy/TLS settings. A healthy port
alone is never accepted. Incompatible proxies and unrelated listeners are left
running; stop the known managed instance explicitly or choose another port. For a
separate Copilot account, use a different editor port:

```sh
HEADROOM_VSCODE_PORT=8789 copilot-vscode-headroom .
```

Copilot access-token rotation preserves reuse. A changed OAuth credential is treated
as a new context, even if it belongs to the same account; stop the old proxy before
relaunching on that port. This conservative check avoids an extra account lookup.
Signing out of a client does not revoke the credential held by a running proxy.
Stop the proxy when changing accounts or revoking access.

The per-user runtime uses a private `/tmp/headroom-kit-<uid>` directory for port
locks and Unix control sockets. It stores no credentials or PID metadata. Startup
waits up to `HEADROOM_STARTUP_TIMEOUT` after resolution. Dead proxies and abandoned
sockets recover on the next launch. If an owner is forcibly killed while Headroom
survives, Kit refuses the unverified listener; inspect it manually. Never remove
live lock/socket files or clean this directory while proxies run. Stop proxies
before garbage-collecting their runtime environment. Reboot stops them.

## Troubleshooting

| Problem | Check |
| --- | --- |
| Agent not found | Check the agent with `command -v`; set the [executable option](configuration.md#options) if needed |
| Runtime download fails | Check the version, uv index access, cache permissions, and CA certificates; use `UV_NATIVE_TLS=true` if needed |
| Proxy never becomes ready | Try `HEADROOM_VERSION=0.37.0` and a free port; increase `HEADROOM_STARTUP_TIMEOUT` for slow startup |
| Port occupied | Use `headroom-kit status` and stop the selected managed port, or choose another port; inspect unknown listeners separately |
| Copilot auth/model failure | Run `headroom copilot-auth status`; check your subscription and explicit model |
| Editor settings conflict | Repair JSONC or conflicting endpoint settings in the isolated profile, then restart its wrapper |

Readiness failures stop the launch; there is no direct-connection fallback.
Raw proxy and resolver diagnostics are suppressed because they can contain credentials.

## Migration and rollback

When replacing another proxy setup, back up affected settings and remove only its
endpoint overrides, including permanent shell exports. Preserve credentials and
other preferences. Before adopting shared proxies, close clients using the old version and stop
its proxies from their owner terminals. The new status/stop command cannot adopt
or stop older wrapper-owned proxies. Check that their ports are free; leave
unidentified listeners alone.

To stop using Kit, close wrapped clients and explicitly stop each port listed by
`headroom-kit status`, then use normal commands. Remove Kit from your package list and rebuild when ready. Keep or delete
the isolated profile separately; its settings still point at Headroom after exit.
To remove only the managed editor block:

```sh
headroom unwrap vscode --settings-file '/path/to/isolated/User/settings.json'
```

## Privacy and routing

Managed proxies bind to `127.0.0.1`. External beacons and message logging are off;
Kit creates no proxy log file. Authentication stays in memory or the client's
normal credential store, outside Nix and source control.

CLI-launched clients bypass forward proxies for loopback. Existing exclusions are
preserved; a wildcard bypass keeps all client traffic direct. Headroom retains the
caller's upstream proxy policy. Normal launches and the caller's environment are unchanged.

<details>
<summary>Routing and proxy policy details</summary>

- Codex receives per-process `model_provider="openai"` and a local
  `openai_base_url`. Kit groups all `-c` options before a literal `--` to preserve
  subcommand overrides in Codex 0.154.0. `CODEX_HOME` stays unchanged.
- The macOS app uses `open --env` with `CODEX_APP_SERVER_OPENAI_BASE_URL` and
  `CODEX_APP_SERVER_FORCE_CLI=1`. These hooks can change with app updates; shell
  proxy exclusions do not establish live GUI routing.
- Copilot CLI receives a non-secret local bearer placeholder, `/v1`, and the
  `responses` wire API. The proxy removes client credentials on Copilot upstream
  requests and uses its pinned Headroom OAuth context. Access tokens are exchanged
  separately for each integration ID and refreshed by Headroom.
- CLI clients merge `NO_PROXY`/`no_proxy` and add `127.0.0.1`, `localhost`, and `::1`.
  A standalone `*` entry sets both spellings to `*` and removes uppercase/lowercase
  HTTP, HTTPS, and ALL proxy variables from the client copy only.
- Codex, Pi, and OpenCode use cache mode with lossless, stateless operation. Kompress/fallback,
  semantic cache, rate limiting, learning, wire debug, output shaping, effort
  routing, and verbosity autotuning are off. Copilot keeps standard compression
  and local dashboard stats, with stateless operation and no learning.
- `HEADROOM_TELEMETRY` controls local stats: off for Codex, Pi, and OpenCode; on for Copilot.
  `DO_NOT_TRACK=1` is set. Arbitrary inherited `HEADROOM_*` tuning and upstream
  overrides are excluded. Direct `headroom` accepts upstream flags independently.
- A detached Kit owner holds the port lock and a reserved TCP socket. Headroom
  inherits that socket, so another listener cannot win a startup race. The private
  control socket verifies the live instance; stop never signals a recorded PID.
- Kit supplies macOS allocator defaults before spawning and disables Headroom's
  re-exec so the inherited socket and account adapter remain installed. This embedding path is tested with Headroom 0.37.0.

See [Headroom proxy controls](https://docs.headroomlabs.ai/docs/proxy).

</details>

## Check routing and compression

Open the printed dashboard. A healthy proxy proves readiness, not routed traffic.
For live validation, compare request counters before and after an authorized model
request; a direct launch should not increment them. Measure compression separately
with a representative workload: token savings, failures, and answer correctness.
See [validation limits](validation.md).
