---
name: install-headroom-kit
description: Set up or migrate Headroom Kit in a Nix flake or Home Manager configuration. Use when a user wants Headroom wrappers for Codex, Copilot, Pi, OpenCode v2, or an isolated VS Code profile while preserving normal agent settings.
---

# Install Headroom Kit

Configure the consumer repository, then build the selected launchers. Keep normal
agent configuration and authentication under their existing owner.

## Locate the consumer

1. Read its `AGENTS.md`, flake inputs, and relevant package or Home Manager module.
   Identify the target system and existing wrapper declarations. Preserve unrelated
   work, input pins, module ownership, and `home.stateVersion`.
2. Check that Nix flakes and the requested agents are available. Kit supplies Python
   and uv, but does not install agents, editors, or extensions. Check the requested
   system against the package outputs and `docs/validation.md`. Linux runtime
   support is unvalidated; the Codex app launcher is macOS only.
3. Use the README and `docs/configuration.md` from
   the requested Kit revision. Preserve an existing pin or user-specified revision;
   otherwise use that README's tagged GitHub input and retain the resulting lock.
   Use a `path:` input only when the user selects a local checkout.
   If this skill was installed alone, obtain the docs from that exact GitHub
   revision or Nix input source before applying examples. The source repository is
   https://github.com/ruarfff/headroom-kit-nix; do not assume its default branch
   matches the consumer pin.

## Make the change

1. Add the Kit input and either import `homeManagerModules.default` or select
   packages. Use the consumer's existing method to pass `inputs` to its module.
   Use `environment.systemPackages` for NixOS/nix-darwin package selection or
   `home.packages` for Home Manager. Follow the existing layout and host selection.
   The default Home Manager selection includes `headroom`, `headroom-kit` control,
   Codex CLI, and Copilot CLI.
2. Select only requested wrappers. Use `lib.mkHeadroomKit` when the consumer needs
   custom packages without Home Manager. Start with the pinned Headroom default;
   use `latest` only when the user requests it.
   Add `pi-headroom` or `opencode-headroom` explicitly when requested. These and
   shared proxy support require Kit v0.1.1 or later.
3. Check executable names and port conflicts. Codex and Copilot must use different
   ports. Copilot CLI and the editor can share only with matching configuration and
   Headroom OAuth credentials. Use different ports for separate contexts.
   Pi and OpenCode each need a separate port from all other wrappers.
   Match the editor channel to the user's installation; Stable is the default,
   and Insiders is an explicit choice.
   An editor user-data directory must be dedicated to Kit. Keep Settings Sync off;
   do not reuse a normal profile or link its settings into the isolated directory.
4. Remove obsolete package declarations only within the authorized migration.
   Do not change permanent agent endpoint settings silently. Follow the migration
   section in `docs/usage.md` if the user asks to remove old overrides.
   Preserve sign-in, history, preferences, and unrelated shell settings.
   Before adopting shared proxies, have the user stop older wrapper-owned proxies
   in their original terminals. The new control command cannot adopt them.
5. Keep package-index credentials out of source and the Nix store. Kit uses user
   and system uv policy without reading project configuration. Do not inspect
   credential files to prove this; use the local-index regression instead.

## Build and hand off

1. Run the consumer's formatter and affected configuration build. For a standalone
   Kit checkout, run `nix flake check "path:$PWD"` and
   `nix build "path:$PWD#headroom-kit"`. A `path:` source includes untracked files
   without staging them. Do not update unrelated lock inputs.
2. Resolve build failures before activation. Install or activate only within the
   user's authorization and the consumer's normal workflow. Do not commit or push
   unless requested.
3. Explain authentication without reading or copying credentials: Codex keeps its
   existing sign-in; Copilot additionally needs `headroom copilot-auth login` and
   `copilot-headroom --model <model-id>`. Let the user complete interactive sign-in.
   Shared Copilot requires reusable OAuth; routed editor requests use Headroom
   authorization even if the editor is signed into another account.
   Pi and OpenCode route OpenAI and Anthropic API keys, plus Pi's ChatGPT Codex
   login and OpenCode Zen/free models. Follow their setup sections in
   `docs/usage.md`; other providers keep their normal routes. OpenCode requires
   v2 and uses a private server.
4. For requested runtime checks, use the isolated smoke test in
   `docs/development.md`. It uses no accounts or live GUI apps.
   Authenticated model requests and live GUI changes require explicit authorization.
   Health alone does not prove routed traffic or useful compression.
5. Explain `headroom-kit status` and `headroom-kit stop <port>`. Shared proxies
   survive client/terminal exit; stop interrupts every attached client. Stop the
   old proxy explicitly when changing OAuth contexts or Kit/runtime versions.
6. Report changed files, actual checks, remaining limitations, and the next required
   user action. Setup is complete when the requested packages build and the user
   has clear launch and rollback instructions. Do not claim untested routes work.
