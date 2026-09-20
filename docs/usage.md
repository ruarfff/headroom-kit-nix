# Usage and troubleshooting

Shared proxies, Pi, and OpenCode are available from **v0.1.1**. Upgrading from
v0.1.0: [stop the old wrapper-owned proxies](#migration-and-rollback) first.

## Codex CLI

Sign in with `codex login`, then launch from your project:

```sh
codex-headroom
# or resume a session
codex-headroom resume --last
```

Kit keeps your sign-in, history, working directory, arguments, and terminal input.
Help and version requests skip Headroom. The wrapper supports Codex's built-in
OpenAI provider; use normal Codex for custom or local providers.
API-key routing is [unverified](validation.md).

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

An explicit model is required; automatic selection does not carry over. Kit uses
subscription auth and the Responses API, not API tokens. The shared proxy pins
Headroom's OAuth credential and refreshes access tokens per Copilot integration.
Subscription routing is experimental; enterprise domains are unverified.

## Pi

Install [Pi](https://pi.dev), configure an OpenAI or Anthropic **API key** through
Pi's normal setup, then launch from your project:

```sh
pi-headroom --provider openai --model <model-id>
# ChatGPT Codex login (best effort):
pi-headroom --provider openai-codex --model gpt-5.6-luna
# GitHub Copilot through Headroom:
pi-headroom --provider github-copilot --model <model-id>
# Or use Anthropic:
pi-headroom --provider anthropic --model <model-id>
```

Pi keeps its config, catalog, extensions, skills, history, and sign-in. Kit loads
a local extension for this process only, including with `--no-extensions`. Resume
and print-mode arguments pass through.
Routed providers: `openai`, `openai-codex` (ChatGPT login, `/v1/codex/responses` at
Headroom), `anthropic`, and `github-copilot`. Copilot traffic uses the shared Copilot
proxy and [Headroom's Copilot login](#copilot-cli), not Pi's. Pi keeps its native
Copilot client; Kit only swaps the token. Other providers keep their normal routes.
See [Pi providers](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/providers.md).

## OpenCode v2

Install [OpenCode v2](https://opencode.ai/v2/docs), then use `/connect` to configure
an OpenAI or Anthropic **API key** and pick a model:

```sh
opencode-headroom
opencode-headroom run --model openai/<model-id> "Explain this project"
```

Kit starts a private server with the existing config and leaves the normal
background service alone. `opencode-headroom ./path` and `opencode-headroom mini`
work; account and service commands stay on normal `opencode`. OpenCode v1 is rejected.

OpenCode 2.0.3 can fail concurrent private-server startup with a JSON bootstrap
error, including without Kit. Start sessions one at a time if that happens.
See [validation](validation.md#real-clients).

A local plugin routes `openai`, `anthropic`, `opencode` (Zen/free, best effort),
and `github-copilot` through Headroom, including titles and compaction. It overrides
per-model endpoints and uses HTTP streaming, not WebSockets. Copilot traffic uses
the shared Copilot proxy and [Headroom's Copilot login](#copilot-cli), not OpenCode's.
OpenCode keeps its native Copilot client; Kit only swaps the token. Other providers
keep their normal routes.
Kit appends the plugin to the child's `OPENCODE_CONFIG_CONTENT` (must be a JSON
object); existing inline settings stay. JSONC files are unchanged.
See [OpenCode config](https://opencode.ai/v2/docs/config/) and
[plugins](https://opencode.ai/v2/docs/plugins/).

## Copilot in VS Code

Complete [Headroom authorization](#copilot-cli), make sure the Copilot extension is
installed for your channel, then:

```sh
copilot-vscode-headroom .
HEADROOM_VSCODE_CHANNEL=insiders copilot-vscode-headroom .
```

Kit opens a separate profile after the proxy is ready. **Normal settings are
untouched and Settings Sync is off.** Sign in to GitHub in the new profile if prompted.
Repeat the command for another window in the same instance.

**Routed model requests use Headroom's authorized account**, even if the editor
holds another GitHub credential. Use the same account in both if you want matching
model listings. Kit does not touch the editor's credential store. Live GUI routing
is unverified.

| Default location | Stable | Insiders |
| --- | --- | --- |
| macOS user data | `~/Library/Application Support/Code Headroom` | `~/Library/Application Support/Code - Insiders Headroom` |
| Linux user data | `${XDG_CONFIG_HOME:-~/.config}/Code Headroom` | `${XDG_CONFIG_HOME:-~/.config}/Code - Insiders Headroom` |
| Existing extensions | `~/.vscode/extensions` | `~/.vscode-insiders/extensions` |

[Override these paths](configuration.md#options) only with a **dedicated Kit
profile**. `User` symlinks that escape it are rejected, and the checks cannot catch
concurrent symlink changes, so pick a directory Kit will not mistake for a normal
profile. One folder or file, no extra editor flags. Remote hosts, SSH, containers,
and WSL are unverified. See
[Headroom's editor integration](https://docs.headroomlabs.ai/docs/vscode-copilot).

## Codex macOS app

Sign in through the app, use its built-in OpenAI provider, then **quit the app**
before:

```sh
codex-app-headroom
```

An already-running app is refused. The launcher returns after opening; the shared
proxy stays up and Codex CLI can use it. Undocumented hooks; live GUI routing is
unverified. A fresh Dock launch uses the app's normal settings.

## Proxy lifetime

Wrappers start a compatible proxy if they need one, then share it. Clients and
terminals can exit; the proxy stays until you stop it. No reference count, launchd
job, or systemd service.

```sh
headroom-kit status
headroom-kit stop 8788
```

**Stop interrupts every client on that port.** It does not close them or replay
requests. Status/stop use bundled Python and do not download Headroom. Individual
package installs: `nix run <kit-source>#headroom-kit -- status`, or add
`headroom-kit-control`. Home Manager already includes it.

| Route | Default port | Share when |
| --- | --- | --- |
| Codex CLI/app | 8788 | Same configuration |
| Copilot CLI/editor and Pi/OpenCode `github-copilot` | 8787 | Same Headroom OAuth credential (model and client env do not matter) |
| Pi | 8790 | Same configuration |
| OpenCode | 8791 | Same configuration; each client still has its own OpenCode server |

A healthy port is not enough. Incompatible proxies and unrelated listeners are left
alone; stop the managed instance or pick another port. Copilot access-token rotation
keeps reuse; a new OAuth credential is a new context even for the same account, so
stop first. Signing out of a client does not revoke the credential the proxy still
holds. Second Copilot account:

```sh
HEADROOM_VSCODE_PORT=8789 copilot-vscode-headroom .
```

Runtime state is `/tmp/headroom-kit-<uid>` (locks and control sockets, no credentials
or PID files). Dead proxies recover on the next launch. If you kill the owner and
Headroom survives, inspect the listener yourself; Kit will not touch an unverified
process. Do not delete live lock/socket files. Stop proxies before garbage-collecting
their environment. Reboot stops them.

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

When replacing another proxy setup, back up settings and remove only its endpoint
overrides, including shell exports. Keep credentials. Close old clients and stop
their proxies from the owner terminals first; `headroom-kit status`/`stop` cannot
adopt wrapper-owned proxies from v0.1.0. Check the ports are free; leave unknown
listeners alone.

To leave Kit, close wrapped clients, stop each port from `headroom-kit status`,
then use normal commands. Remove Kit from your package list and rebuild. The
isolated editor profile still points at Headroom until you delete it or unwrap:

```sh
headroom unwrap vscode --settings-file '/path/to/isolated/User/settings.json'
```

## Privacy and routing

Managed proxies bind to `127.0.0.1`. External beacons and message logging are off;
Kit creates no proxy log file. Authentication stays in memory or the client's
normal credential store, outside Nix and source control.

CLI-launched clients bypass forward proxies for loopback. Existing exclusions are
kept; a wildcard bypass keeps all client traffic direct. Headroom keeps the
caller's upstream proxy policy. Normal launches and the caller's environment are
unchanged.

<details>
<summary>Routing and proxy policy details</summary>

- Codex gets per-process `model_provider="openai"` and a local `openai_base_url`.
  Kit groups all `-c` options before a literal `--` so Codex 0.154.0 still sees
  subcommand overrides. `CODEX_HOME` is unchanged.
- The macOS app uses `open --env` with `CODEX_APP_SERVER_OPENAI_BASE_URL` and
  `CODEX_APP_SERVER_FORCE_CLI=1`. Those hooks can change with app updates; shell
  proxy exclusions do not prove live GUI routing.
- Copilot CLI gets a non-secret local bearer placeholder, `/v1`, and the
  Responses wire API. The proxy strips client credentials on Copilot upstream
  requests and uses its pinned Headroom OAuth context. Access tokens are exchanged
  per integration ID and refreshed by Headroom.
- CLI clients merge `NO_PROXY`/`no_proxy` and add `127.0.0.1`, `localhost`, and
  `::1`. A standalone `*` sets both spellings to `*` and removes HTTP, HTTPS, and
  ALL proxy variables (both cases) from the client copy only.
- Codex, Pi, and OpenCode use cache mode with lossless, stateless operation.
  Kompress/fallback, semantic cache, rate limiting, learning, wire debug, output
  shaping, effort routing, and verbosity autotuning are off. Copilot keeps
  standard compression and local dashboard stats, with no learning.
- `HEADROOM_TELEMETRY` is off for Codex, Pi, and OpenCode; on for Copilot.
  `DO_NOT_TRACK=1` is set. Inherited `HEADROOM_*` tuning and upstream overrides are
  dropped. Direct `headroom` still accepts upstream flags.
- A detached Kit owner holds the port lock and a reserved TCP socket. Headroom
  inherits that socket, so another listener cannot win a startup race. The private
  control socket verifies the live instance; stop never signals a recorded PID.
- On macOS, Kit sets allocator defaults before spawn and disables Headroom's
  re-exec so the inherited socket and account adapter stay installed. Tested with
  Headroom 0.37.0.

See [Headroom proxy controls](https://docs.headroomlabs.ai/docs/proxy).

</details>

## Check routing and compression

The dashboard proves the proxy is up, not that traffic is routed. Compare request
counters before and after an authorized model request; a direct launch should not
increment them. Measure compression separately. See [validation](validation.md).
