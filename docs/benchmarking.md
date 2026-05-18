# Benchmarking

SilkMC ships with upstream profiling surfaces plus the project's own scheduler bridging telemetry. This document describes how to run repeatable benchmarks.

## Tooling

- `/tps` - per-region TPS readout
- `/silkmc tps` (upstream `/tps` alias preserved) - aggregated TPS
- spark integration - profile any region or async thread
- startup version and build metadata - exposed via `/version`
- GitHub Actions build artifacts - repeatable binaries from `build.yml`

## Suggested scenarios

| Scenario                  | Goal                                                                                  |
| ------------------------- | ------------------------------------------------------------------------------------- |
| Vanilla baseline          | Establish lowest-overhead TPS floor with no plugins on a pregenerated world.          |
| Player-spread SMP         | Multiple players spread across distant chunks - exercises regional parallelism.       |
| Plugin-heavy compatibility | Mixed Paper/Bukkit/Spigot plugin pack - measures scheduler-bridge overhead.           |
| Redstone-heavy            | Stress block-update propagation inside a region.                                      |
| Mob farm                  | Stress entity ticking and chunk loading at region boundaries.                         |

## Suggested protocol

1. Use the same world snapshot between runs (copy a known-good world directory).
2. Use identical JVM flags. Recommended starting point:

   ```text
   -Xms6G -Xmx6G
   -XX:+UseG1GC
   -XX:+ParallelRefProcEnabled
   -XX:MaxGCPauseMillis=200
   -XX:+UnlockExperimentalVMOptions
   -XX:+DisableExplicitGC
   -XX:+AlwaysPreTouch
   -XX:G1NewSizePercent=30
   -XX:G1MaxNewSizePercent=40
   -XX:G1HeapRegionSize=8M
   -XX:G1ReservePercent=20
   -XX:G1HeapWastePercent=5
   -XX:G1MixedGCCountTarget=4
   ```

3. Warm up for at least 5 minutes before sampling.
4. Sample TPS, MSPT, and spark profile data for 10 minutes.
5. Repeat each scenario at least three times and report median values.

## Interpreting results

- Compare per-region TPS, not just global TPS - that is what region threading optimizes for.
- The scheduler bridge runs legacy sync tasks on the Global Region Scheduler. Expect higher contention on this scheduler when plugin packs are heavy with legacy sync work.
- Watch the SilkMC compatibility log for warnings - excessive warnings often correlate with reduced parallelism.

## Reporting

Open an issue with the "Performance problems" template if you observe regressions versus an earlier SilkMC build, and include:

- SilkMC build hash
- world snapshot description
- JVM flags
- plugin list
- TPS / MSPT samples
- spark profile (optional but encouraged)
