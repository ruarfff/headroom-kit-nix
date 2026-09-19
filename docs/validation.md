# Validation and limitations

A Nix build proves packaging, not authenticated model routing or compression quality.

## Platforms

| System | Nix evaluation | Runtime |
| --- | --- | --- |
| `aarch64-darwin` | Pass | Headroom 0.37.0 proxy, writer, and local auth-adapter smoke pass |
| `aarch64-linux` | Pass | Unverified |
| `x86_64-linux` | Pass | Unverified |

The Codex app wrapper requires macOS. Consumer integration was not changed or activated.

## Shared lifecycle

The first regressions failed on the old implementation: two sequential launches
created two proxies, and simultaneous launches failed immediately on the lock.
The same tests now pass with a detached owner. Traffic tests verify one proxy
instance and increasing request counts across clients, rather than readiness alone.

Coverage includes:

- Sequential and simultaneous reuse for supported CLI routes; normal exit,
  Ctrl+C, forced kill, and a killed creator during startup.
- Continued requests from surviving clients and reuse by later launches.
- Selected-instance stop, startup failure, dead proxies, abandoned sockets,
  stale/recycled PID metadata, and healthy foreign listeners.
- Version, environment, and account separation; Copilot reuse across model and
  client environment; access-token rotation; caller environment and normal routing
  preservation.
- Repeated and simultaneous isolated editor windows, settings-path guards, and
  Settings Sync isolation. Editor processes are stand-ins.

The real runtime smoke caught Headroom's macOS allocator re-exec discarding the
inherited socket. Kit now supplies allocator defaults before spawning and prevents
that re-exec. Real Headroom checks verify startup, persistent lifetime, reuse,
explicit stop, and its settings writer.

A local token endpoint exercises the real Headroom Copilot adapter with fake
credentials. It verifies pinned OAuth context, separate CLI/editor integration IDs,
access-token refresh, and unchanged authentication on unrelated upstream routes.
No GitHub authorization or provider model request was made.

## Real clients

macOS routing checks used Codex **0.154.0**, Pi **0.85.1**, and OpenCode **2.0.3**,
temporary homes, fake credentials, and local endpoints. External network access
was blocked for the routing suites.

Codex and Pi passed both shared-client cases: two concurrent clients under ordinary
and wildcard proxy settings. Each pair reached one managed fake proxy, with two
requests and both distinct prompts observed. OpenCode's ordinary case passed with
nine requests, including serial initialization and auxiliary requests.

**OpenCode 2.0.3 has an intermittent concurrent private-server startup failure.**
One wildcard-case client failed with a JSON bootstrap error, even after a serial
initialization launch. A separate local reproduction confirmed the same failure
in plain OpenCode without Kit, its plugin, Headroom, or forward-proxy variables.
Starting sessions one at a time avoids that concurrent startup path. Kit does not
change OpenCode's database or service startup implementation.
A full repeat passed all six cases; both OpenCode cases then made nine requests
and included both prompts. The repeat does not remove the intermittent limitation.

The existing eight Pi/OpenCode provider cases also pass: OpenAI/Anthropic with
ordinary/wildcard proxy settings. No requests reached the conflicting configured
endpoint or forward proxy; configuration files and caller environments stayed
unchanged. These local error responses establish routing, not model support.

## Commands and results

Run development-shell commands with `nix develop "path:$PWD" --command`.
Validation on 2026-09-16:

| Command | Result |
| --- | --- |
| `python -m unittest discover -s tests -v` | 65 passed |
| `node --test tests/test_client_adapters.mjs` | 2 passed |
| `python tests/shared_agent_smoke.py` | Initial run: 5 of 6 passed, with the OpenCode startup failure above; repeat: all 6 passed |
| `python tests/agent_routing_smoke.py` | 8 provider-routing cases passed |
| `ruff check libexec tests .github/scripts` | Passed |
| `ruff format --check libexec tests .github/scripts` | Passed |
| `nixfmt --check flake.nix nix/*.nix` | Passed |
| `pre-commit run anti-slop-python --files libexec/*.py tests/*.py .github/scripts/*.py` | Passed |
| `nix flake check "path:$PWD" --no-write-lock-file` | Native checks passed |
| `nix flake check "path:$PWD" --no-build --all-systems --no-write-lock-file` | All three systems evaluated |
| `nix build "path:$PWD#headroom-kit" --no-write-lock-file --no-link --print-out-paths` | Aggregate built |
| `python tests/runtime_smoke.py <built-package> --cache-dir <test-cache>` | Real proxies, 2 writer tests, and local Copilot refresh passed |

## Remaining limits

- Linux runtime, live Codex app routing, isolated editor chat, and remote editor hosts.
- Authenticated providers, Copilot enterprise domains/model combinations, and
  Pi/OpenCode subscriptions or custom provider runtimes. Their `openai` and
  `anthropic` providers are routed; other providers retain their normal routes.
- Compression quality and savings under representative concurrent workloads.
- Consumer integration. Published revisions run Linux and macOS checks in the
  [release workflow](https://github.com/ruarfff/headroom-kit-nix/actions/workflows/tag.yml).

Copilot credential identity is conservative: a new OAuth credential requires an
explicit stop even for the same account. A killed owner with a surviving Headroom
process needs manual inspection; Kit will not kill an unverified listener.
Interrupted model requests are not replayed.

Exact versions do not lock every Python dependency or optional download. Editor
path checks cannot prevent concurrent symlink changes. Follow the
[migration instructions](usage.md#migration-and-rollback) before replacing older
wrapper-owned proxies.
