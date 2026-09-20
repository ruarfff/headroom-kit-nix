# Configuration

Start with the [quick setup](../README.md#quick-start). Settings are optional;
environment variables override Nix options for one launch.

## Nix integration

Add the [README input](../README.md#install-in-your-nix-configuration). Pass `inputs`
through `specialArgs` (NixOS/nix-darwin), `extraSpecialArgs` (standalone Home Manager),
or `home-manager.extraSpecialArgs` (Home Manager as a system module).

| Setup | Package option |
| --- | --- |
| NixOS or nix-darwin | `environment.systemPackages` |
| Home Manager | `home.packages` or the Kit module |

### Home Manager

Default wrappers: `headroom`, `headroom-kit`, `codex-headroom`, and `copilot-headroom`.
Pick others with `wrappers`; `headroom` and the control command are always included.

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

Wrappers start their runtime on demand.

### Without the Kit module

Select individual packages, or `kit.headroom-kit` for all eight commands:

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

Headroom defaults to **0.37.0**:

```sh
HEADROOM_VERSION=0.37.0 codex-headroom
HEADROOM_VERSION=latest codex-headroom
```

Exact versions fail without fallback. `latest` refreshes, skips prereleases, and
prints the resolved version. A Kit tag pins launcher code; `HEADROOM_VERSION` pins
the Headroom runtime. Neither locks every Python dependency.

uv uses Nix Python in an isolated tool environment. It keeps your user/system index
and auth, ignores project `uv.toml`/`pyproject.toml`, and will not download Python
or load dotenv. Explicit uv env still applies. Keep credentials out of Nix and
source control.
See [uv configuration](https://docs.astral.sh/uv/concepts/configuration-files/).

## Options

Home Manager paths are under `programs.headroom-kit`. The last column is
`lib.mkHeadroomKit`.

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

Ports are 1–65535. Codex and Copilot need different ports. Copilot CLI and the
editor can share a port when they share the Headroom OAuth credential. Pi and
OpenCode each need their own port. Startup timeout is seconds after runtime
resolution.

Executables are names on `PATH` or single paths, never shell commands. Quote paths
with spaces. The app path must be a macOS `.app` bundle. Unset an environment
variable to use the default; empty is an error.
