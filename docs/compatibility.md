# Compatibility Guide

SilkMC is designed to be more forgiving than upstream Folia without hiding correctness problems. This guide describes the compatibility policy, configurable behavior, and the boundaries SilkMC will not cross for the sake of compatibility.

## Current policy

- `silk-supported: true` is the preferred plugin metadata flag.
- `folia-supported: true` is still accepted for upstream interoperability.
- Every plugin JAR is inspected by `SilkPluginCompatibilityManager` before enable: metadata read, classes byte-scanned for API and NMS usage, then assigned one of `SAFE` / `COMPATIBLE` / `UNSAFE` / `UNKNOWN`.
- Legacy Bukkit scheduler calls (`runTask`, `runTaskLater`, `runTaskTimer`, `callSyncMethod`) are bridged to the Global Region Scheduler.
- Legacy synchronous `Entity.teleport()` and `Player.teleport()` are bridged to `teleportAsync` when the call is made on the owning region; cross-region sync teleports warn and return optimistically.
- The plugin lifecycle (enable/disable) is wrapped in a compatibility context so failures can be classified and reported with operator-friendly messages.

## Classification

| Class | Trigger | Action |
| --- | --- | --- |
| `SAFE` | declares `silk-supported` or `folia-supported` | load normally |
| `COMPATIBLE` | uses Bukkit/Spigot/Paper APIs but no unsafe patterns | load under shim layer (scheduler bridge, teleport bridge) |
| `UNSAFE` | async scheduling + direct NMS-level world access | refuse to load; print structured rejection log; continue startup |
| `UNKNOWN` | no detectable APIs or unreadable JAR | refuse under strict-mode; allowed with warning if `allow-unknown-plugins: true` |

## Modes

SilkMC currently supports:

- compatibility warning mode for unmarked plugins (default)
- strict supported-plugin enforcement
- automatic disabling for plugins that hit known unsafe compatibility boundaries
- upstream enum compatibility toggles through `bukkit.yml`

## Configuration: `silkmc-compatibility.yml`

SilkMC auto-generates this file on first startup. See [examples/server/silkmc-compatibility.yml](../examples/server/silkmc-compatibility.yml) for a copy-pastable starting point.

| Key                                       | Default | Effect                                                                                                  |
| ----------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------- |
| `plugins.unsupported-plugin-mode`         | `WARN`  | `WARN` allows unmarked plugins to load; `REQUIRE_DECLARATION` refuses them at load time.                |
| `plugins.warn-on-load`                    | `true`  | Whether to log a warning when an unmarked plugin loads.                                                 |
| `plugins.disable-incompatible-plugins`    | `true`  | Whether SilkMC should auto-disable plugins that hit known unsafe boundaries (instead of crash-looping). |
| `plugins.log-compatibility-stacktraces`   | `true`  | Whether compatibility failures include full stack traces in the log.                                    |
| `compatibility.strict-mode`               | `true`  | Whether the manager refuses to load plugins it classifies as `UNKNOWN`.                                 |
| `compatibility.allow-unknown-plugins`     | `false` | When `true`, `UNKNOWN` plugins load with a warning instead of being blocked.                            |
| `compatibility.log-analysis`              | `true`  | When `true`, a one-line compatibility analysis summary is logged for every plugin.                      |

## Fail-safe behavior

When SilkMC cannot safely emulate a legacy expectation, it should:

1. stop the unsafe operation
2. disable the plugin when the failure matches a known compatibility boundary
3. log a clear operator-facing reason
4. preserve server stability

SilkMC currently classifies and disables plugins for known startup or task-time failures such as:

- world and chunk access from the wrong thread or region context
- global-region-only operations triggered from an ambiguous legacy context
- legacy scheduler paths that still lack enough ownership context to bridge safely
- synchronous teleport assumptions that cannot be preserved safely

Each classified failure produces a log entry with:

- the plugin display name
- the lifecycle phase (`startup`, `async scheduler task`, `global region task`, ...)
- a one-paragraph operator-facing reason
- (optional) the original stack trace

## Stability rules

SilkMC will not, under any compatibility policy:

- fake region ownership to silence a thread check
- pretend a cross-region operation succeeded when it actually didn't write
- introduce a fake global "main" thread that mutates world state
- corrupt world or player data to keep a plugin running

When in doubt, SilkMC fails the operation cleanly and disables the plugin.

## Known limitations

- no fake global main thread is introduced
- plugins that mutate cross-region state unsafely can still fail
- some traditional Bukkit scheduler tasks still lack enough location or entity context for SilkMC to infer the safest owning region and are routed to the global region scheduler
- some event ordering assumptions from traditional single-threaded servers remain impossible to preserve fully
- some plugins detect "Folia" by class name lookup; the upstream classes still exist under their original packages for binary compatibility, but plugins that hard-fail on Folia detection should be updated to recognize SilkMC's brand
