# Configuration

Start with the [quick setup](../README.md#quick-start). All settings are optional;
environment variables override Nix options for one launch.

## Nix integration

Add the input shown in the [README](../README.md#install-in-your-nix-configuration),
then choose the package option your configuration uses:

| Setup | Package option |
| --- | --- |
| NixOS or nix-darwin | `environment.systemPackages` |
| Home Manager | `home.packages` or the Kit module below |

These modules receive `inputs` through your existing module arguments:
`specialArgs` for NixOS/nix-darwin, `extraSpecialArgs` for standalone Home Manager,
or `home-manager.extraSpecialArgs` when Home Manager is a system module.

### Home Manager

The module installs `headroom`, the `headroom-kit` control command,
`codex-headroom`, and `copilot-headroom` by default.
To choose wrappers, set `wrappers` explicitly:

```nix
{ inputs, ... }:
{
  imports = [ inputs.headroom-kit.homeManagerModules.default ];
  programs.headroom-kit = {
    enable = true;
    wrappers = [ "codex-headroom" "pi-headroom" "opencode-headroom" "copilot-vscode-headroom" ];
    vscode.port = 8789;
    # vscode.channel = "insiders"; # Stable is the default
  };
}
```

`headroom` and the control command are always included. The module installs packages;
wrappers start their shared runtime on demand.

### Without the Kit module

Select individual packages or `kit.headroom-kit` for all eight commands:

```nix
{ inputs, pkgs, ... }:
let
  kit = inputs.headroom-kit.lib.mkHeadroomKit {
    inherit pkgs;
    vscodePort = 8789;
  };
in {
  environment.systemPackages = [ kit.headroom kit.headroom-kit-control kit.codex-headroom kit.copilot-vscode-headroom ];
}
```

Use `home.packages` with the same list in Home Manager.

## Versions and package indexes

Headroom defaults to **0.37.0**. Select an exact stable version or opt into latest:

```sh
HEADROOM_VERSION=0.37.0 codex-headroom
HEADROOM_VERSION=latest codex-headroom
```

Exact versions fail without fallback. `latest` refreshes and upgrades Headroom,
excludes prereleases, and prints the resolved version. A Kit release tag selects
the launcher code; `HEADROOM_VERSION` selects the runtime. Neither pins every
Python dependency or optional download.

uv uses the Nix Python in an isolated tool environment. It preserves **user and
system package-index configuration and authentication policy**, ignores project
`uv.toml`/`pyproject.toml`, and disables Python downloads and dotenv loading.
Explicit uv environment settings still apply. Keep credentials in your runtime
credential store, outside Nix and source control.
See [uv configuration](https://docs.astral.sh/uv/concepts/configuration-files/).

## Options

Home Manager paths below are under `programs.headroom-kit`. The last column names
arguments to `lib.mkHeadroomKit`.

| Environment variable | Default | Home Manager | Package argument |
| --- | --- | --- | --- |
| `HEADROOM_VERSION` | `0.37.0` | `version` | `version` |
| `HEADROOM_STARTUP_TIMEOUT` | 180 seconds | `startupTimeout` | `startupTimeout` |
| `HEADROOM_CODEX_EXECUTABLE` | `codex` | `codex.executable` | `codexExecutable` |
| `HEADROOM_CODEX_PORT` | 8788 | `codex.port` | `codexPort` |
| `HEADROOM_CODEX_APP_PATH` | Find installed Codex app | `codex.appPath` | `codexAppPath` |
| `HEADROOM_COPILOT_EXECUTABLE` | `copilot` | `copilot.executable` | `copilotExecutable` |
| `HEADROOM_COPILOT_PORT` | 8787 | `copilot.port` | `copilotPort` |
| `HEADROOM_PI_EXECUTABLE` | `pi` | `pi.executable` | `piExecutable` |
| `HEADROOM_PI_PORT` | 8790 | `pi.port` | `piPort` |
| `HEADROOM_OPENCODE_EXECUTABLE` | `opencode` | `opencode.executable` | `opencodeExecutable` |
| `HEADROOM_OPENCODE_PORT` | 8791 | `opencode.port` | `opencodePort` |
| `HEADROOM_VSCODE_CHANNEL` | `stable`; also `insiders` | `vscode.channel` | `vscodeChannel` |
| `HEADROOM_VSCODE_EXECUTABLE` | `code` or `code-insiders` | `vscode.executable` | `vscodeExecutable` |
| `HEADROOM_VSCODE_PORT` | 8787 | `vscode.port` | `vscodePort` |
| `HEADROOM_VSCODE_USER_DATA_DIR` | [Isolated profile](usage.md#copilot-in-vs-code) | `vscode.userDataDir` | `vscodeUserDataDir` |
| `HEADROOM_VSCODE_EXTENSIONS_DIR` | Existing channel extensions | `vscode.extensionsDir` | `vscodeExtensionsDir` |

Ports must be 1–65535. Codex and Copilot need different ports. Copilot CLI and
the editor can share a port when their configuration and Headroom OAuth context match. Pi and OpenCode each need
a separate port from every other wrapper. The startup timeout is a
positive integer in seconds, measured after runtime resolution.

Executable values are names on `PATH` or single paths, never shell commands.
Quote paths with spaces. The app path must be a macOS `.app` bundle.
Unset an environment variable to use its default; an empty value is an error.
