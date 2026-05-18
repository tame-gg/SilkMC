# Compatibility Guide

SilkMC is designed to be more forgiving than upstream Folia without hiding correctness problems.

## Current policy

- `silk-supported: true` is the preferred plugin metadata flag.
- `folia-supported: true` is still accepted.
- Unmarked plugins can load in warning mode.
- Servers can switch back to strict enforcement when needed.
- Legacy Bukkit scheduler calls are bridged where SilkMC can map them safely.

## Modes

SilkMC currently supports:

- compatibility warning mode for unmarked plugins
- strict supported-plugin enforcement
- automatic disabling for plugins that hit known unsafe compatibility boundaries
- upstream enum compatibility toggles through `bukkit.yml`

## Per-plugin overrides

SilkMC writes a second operator-owned file named `silkmc-plugin-overrides.yml` on first boot:

```yaml
overrides: {}
```

Each entry can pin a compatibility decision before SilkMC applies its normal jar inspection heuristics:

```yaml
overrides:
  "LegacyClaims":
    classification: SAFE
    force-load: false
    reason: "Validated on staging after replacing legacy sync world access."
  "InternalBridge":
    classification: AUTO
    force-load: true
    reason: "Temporary production exception while upstream metadata catches up."
```

- `classification` accepts `SAFE`, `COMPATIBLE`, `UNSAFE`, `UNKNOWN`, or `AUTO`.
- `AUTO` keeps SilkMC's scanned classification and only applies `force-load` if set.
- `force-load: true` bypasses strict-mode blocking for an otherwise `UNKNOWN` plugin and is logged at `INFO` with the operator reason.
- Every override application is logged so operators have an audit trail for manual exceptions.

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
