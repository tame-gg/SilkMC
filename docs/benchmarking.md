# Benchmarking

SilkMC ships with existing upstream profiling surfaces and release automation suitable for repeatable benchmarking.

## Tooling

- `/tps`
- spark integration
- startup version and build metadata
- GitHub Actions build artifacts for repeatable binaries

## Initial benchmark note

This repository scaffold does not claim finished production benchmark numbers yet.

Recommended first-pass benchmark scenarios:

- vanilla baseline with pregenerated world
- player-spread SMP workload
- plugin-heavy compatibility workload
- redstone-heavy stress workload
