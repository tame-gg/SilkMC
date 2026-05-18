# Compatibility Guide

SilkMC is designed to be more forgiving than upstream Folia without hiding correctness problems.

## Current policy

- `silk-supported: true` is the preferred plugin metadata flag.
- `folia-supported: true` is still accepted.
- Unmarked plugins can load in warning mode.
- Servers can switch back to strict enforcement when needed.
- Legacy Bukkit scheduler calls (`runTask`, `runTaskLater`, `runTaskTimer`, `callSyncMethod`) are bridged to the Global Region Scheduler.
- Legacy synchronous `Entity.teleport()` and `Player.teleport()` are bridged to `teleportAsync` when on the owning region; cross-region sync teleports warn and return optimistically.

## Modes

SilkMC currently supports:

- compatibility warning mode for unmarked plugins
- strict supported-plugin enforcement
- automatic disabling for plugins that hit known unsafe compatibility boundaries
- upstream enum compatibility toggles through `bukkit.yml`

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

## Known limitations

- no fake global main thread is introduced
- plugins that mutate cross-region state unsafely can still fail
- some traditional Bukkit scheduler tasks still lack enough location or entity context for SilkMC to infer a safe owning region
- some event ordering assumptions from traditional single-threaded servers remain impossible to preserve fully
