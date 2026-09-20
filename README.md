# Headroom Kit

[![Checks and releases](https://github.com/ruarfff/headroom-kit-nix/actions/workflows/tag.yml/badge.svg?branch=main)](https://github.com/ruarfff/headroom-kit-nix/actions/workflows/tag.yml)
[![Nix flake](https://img.shields.io/badge/Nix-flake-5277C3?logo=nixos&logoColor=white)](https://nixos.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Run your existing coding agents through a local
[Headroom](https://github.com/headroomlabs-ai/headroom) proxy using Nix.
Normal launches keep their settings. Kit does not install agents or system services.

```mermaid
flowchart LR
    Agent[Wrapped agent] --> Headroom[Headroom on localhost] --> Provider[Model provider]
```

## Quick start

You need **Nix with flakes** and an installed, signed-in coding agent.
Runtime checks cover Apple Silicon macOS; [Linux is unverified](docs/validation.md).

```sh
nix run github:ruarfff/headroom-kit-nix/v0.1.1#codex-headroom
```

The first launch downloads Headroom 0.37.0 using your uv package-index settings.
[Change version or index](docs/configuration.md#versions-and-package-indexes).
For Copilot, [authorize Headroom](docs/usage.md#copilot-cli) first.

## Install in your Nix configuration

Pin the release:

```nix
inputs.headroom-kit.url = "github:ruarfff/headroom-kit-nix/v0.1.1";
```

In a Home Manager module that receives `inputs`:

```nix
{ inputs, ... }:
{
  imports = [ inputs.headroom-kit.homeManagerModules.default ];
  programs.headroom-kit.enable = true;
}
```

That installs `headroom`, `headroom-kit`, `codex-headroom`, and `copilot-headroom`.
[Configuration](docs/configuration.md#nix-integration) covers Pi, OpenCode, GUI wrappers,
and NixOS/nix-darwin without Home Manager.

## Choose a command

| Command | Setup |
| --- | --- |
| `codex-headroom` | Use your existing Codex sign-in |
| `copilot-headroom --model <model-id>` | [Authorize Headroom for Copilot](docs/usage.md#copilot-cli) first |
| `pi-headroom --provider openai --model <model-id>` | [Configure Pi](docs/usage.md#pi) with an OpenAI or Anthropic API key |
| `pi-headroom --provider github-copilot --model <model-id>` | [Authorize Headroom for Copilot](docs/usage.md#copilot-cli) first |
| `opencode-headroom` | [Configure OpenCode v2](docs/usage.md#opencode-v2) with an OpenAI or Anthropic API key |
| `opencode-headroom run --model github-copilot/<model-id>` | [Authorize Headroom for Copilot](docs/usage.md#copilot-cli) first |
| `copilot-vscode-headroom .` | [Authorize Copilot](docs/usage.md#copilot-in-vs-code); opens an isolated VS Code Stable profile |
| `codex-app-headroom` | Quit the macOS Codex app first; [experimental routing](docs/usage.md#codex-macos-app) |
| `headroom` | Run the Headroom CLI directly |
| `headroom-kit status` / `headroom-kit stop <port>` | Inspect or stop shared proxies |

Compatible sessions share a proxy that outlives the client. `headroom-kit stop`
interrupts everyone on that port. See [proxy lifetime](docs/usage.md#proxy-lifetime)
before upgrading from `v0.1.0`.

## Set up with an agent

Give your agent the [v0.1.1 setup skill](https://github.com/ruarfff/headroom-kit-nix/blob/v0.1.1/skills/install-headroom-kit/SKILL.md).

## Reference

| Read | For |
| --- | --- |
| [Configuration](docs/configuration.md) | Nix examples, ports, versions, and package indexes |
| [Usage](docs/usage.md) | Authentication, editor isolation, privacy, and fixes |
| [Development](docs/development.md) | Checks, runtime smoke test, and releases |
| [Validation](docs/validation.md) | Tested platforms and known limits |

[MIT](LICENSE). See [NOTICE](NOTICE.md) for dependency licenses and attribution.
