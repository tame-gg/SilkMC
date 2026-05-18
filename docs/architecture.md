# Architecture

SilkMC keeps Folia's regional multithreading model as the core execution architecture.

## Design goals

- preserve upstream region ownership semantics
- improve plugin survivability around legacy assumptions
- keep upstream merges clean and understandable
- avoid compatibility hacks that compromise world correctness

## Execution model

- nearby loaded chunks are grouped into ticking regions
- each region ticks independently on a scheduler-managed worker
- global tasks remain explicit instead of pretending there is a single main thread
- cross-region operations should bridge intentionally and fail loudly when unsafe

## SilkMC additions

- compatibility policy for unmarked plugins
- compatibility-focused documentation and migration guidance
- configurable compatibility modes
- release and benchmarking scaffolding for repeatable validation
