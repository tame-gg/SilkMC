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

### The global region is the serial bottleneck

Region ticking parallelises; the global region does not. Anything on it is work that does not get
faster as regions or tick threads are added, so its contents are worth knowing. Per global tick
(`RegionizedServer.globalTick`): click-callback expiry, the global region scheduler, clocks, console
input, the player ping sample, a per-world pass (world border, weather, sleep, raids, sky brightness,
time, ticket updates, map autosave), connection ticking, and `PlayerList.tick()`.

Three of those scale with something an operator can increase, and are recorded here so they are not
rediscovered as mysteries:

- **`PlayerList.tick()` is O(n^2) in player count**, every 600 ticks (30s). For each player it builds
  a `canSee`-filtered view of every other player and sends a latency update, so 1000 players is on
  the order of a million visibility checks in a single global tick, on the one thread that cannot
  parallelise. This is inherited CraftBukkit behaviour, but Folia's execution model concentrates it
  on the serial region.
- **`tickConnections()` is O(total connections) per tick even when almost every connection is
  region-owned**, because ownership is tested inside the loop after the list has already been copied
  and shuffled. The per-connection cost is small; the scan is not free at high player counts.
- **`autoSaveMaps()` performs synchronous disk I/O on the global tick thread**, so a server with many
  map items stalls every region for the duration of the write.

None of these are currently measurable by `tools/benchmark`, which runs without clients and without
map items - so none has been changed. They are documented as known scaling limits rather than fixed
on the strength of a code reading.

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
