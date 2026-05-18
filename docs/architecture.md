# Architecture

SilkMC keeps Folia's regional multithreading model as the core execution architecture. This document is a high-level map of how SilkMC layers compatibility on top of that model.

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

- compatibility policy for unmarked plugins (warn vs strict) - `gg.tame.silkmc.server.compat.SilkPluginCompatibility`
- scheduler bridging: legacy Bukkit sync tasks route to the Global Region Scheduler - `org.bukkit.craftbukkit.scheduler.SilkSchedulerBridge`
- teleport bridging: legacy sync teleport routes to `teleportAsync` when safe - `org.bukkit.craftbukkit.entity.CraftEntity` and `CraftPlayer`
- plugin lifecycle wrapping: `beginLifecycle` / `endLifecycle` thread-local context lets failures be classified with a phase
- compatibility-focused documentation and migration guidance
- configurable compatibility modes via `silkmc-compatibility.yml`
- release and benchmarking scaffolding for repeatable validation

## Component map

```
+----------------------------------------------------------+
|                       SilkMC Server                      |
|                                                          |
|  +--------------------+   +---------------------------+  |
|  | Plugin Manager     |-->| SilkPluginCompatibility   |  |
|  +--------------------+   |  - policy (yml-backed)    |  |
|            |              |  - lifecycle context      |  |
|            |              |  - failure classifier     |  |
|            v              +---------------------------+  |
|  +--------------------+              ^                   |
|  | CraftScheduler     |--------------+                   |
|  | (legacy sync API)  |                                  |
|  +--------------------+                                  |
|            |                                             |
|            v                                             |
|  +--------------------+   +---------------------------+  |
|  | SilkSchedulerBridge|-->| Global Region Scheduler   |  |
|  +--------------------+   +---------------------------+  |
|                                                          |
|  +--------------------+   +---------------------------+  |
|  | CraftEntity        |-->| teleportAsync             |  |
|  | / CraftPlayer      |   | (region-aware teleport)   |  |
|  +--------------------+   +---------------------------+  |
|                                                          |
|  +--------------------+   +---------------------------+  |
|  | Region Threading   |-->| Per-region ticking worker |  |
|  | (upstream Folia)   |   +---------------------------+  |
|  +--------------------+                                  |
+----------------------------------------------------------+
```

## Where the patches live

- `silkmc-server/paper-patches/features/` - server-side compatibility and branding patches
- `silkmc-server/minecraft-patches/features/` - server-side Minecraft-level region threading patches
- `silkmc-api/paper-patches/features/` - API-side compatibility metadata and additions
- `silkmc-server/paper-patches/files/` - new files added by SilkMC (e.g. `SilkPluginCompatibility.java`)

## Where new compatibility shims should go

Add new shims in `gg.tame.silkmc.server.compat` (or a sibling package) and integrate them through small, reviewable patches against `paper-server`. Aim for additive compatibility layers, not broad rewrites of upstream code.
