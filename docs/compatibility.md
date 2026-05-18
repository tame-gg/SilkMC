# Compatibility Guide

SilkMC is designed to be more forgiving than upstream Folia without hiding correctness problems.

## Current policy

- `silk-supported: true` is the preferred plugin metadata flag.
- `folia-supported: true` is still accepted.
- Unmarked plugins can load in warning mode.
- Servers can switch back to strict enforcement when needed.

## Modes

SilkMC currently supports:

- compatibility warning mode for unmarked plugins
- strict supported-plugin enforcement
- upstream enum compatibility toggles through `bukkit.yml`

## Fail-safe behavior

When SilkMC cannot safely emulate a legacy expectation, it should:

1. stop the unsafe operation
2. log a clear warning or exception
3. preserve server stability

## Known limitations

- no fake global main thread is introduced
- plugins that mutate cross-region state unsafely can still fail
- some event ordering assumptions from traditional single-threaded servers remain impossible to preserve fully
