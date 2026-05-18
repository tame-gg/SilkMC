# Plugin Developer Migration

This guide is for plugin authors targeting SilkMC. It covers the metadata SilkMC understands, the compatibility behaviors it provides, and the patterns that travel best across Paper, Folia, and SilkMC.

## Recommended metadata

Add this to `plugin.yml`:

```yaml
silk-supported: true
```

SilkMC also honors the legacy upstream key:

```yaml
folia-supported: true
```

Either one is sufficient. Marking your plugin tells SilkMC that you have at least reviewed the regional threading model and consider your plugin compatibility-aware.

## Practical guidance

- Use the region, entity, async, and global schedulers intentionally instead of `BukkitScheduler.runTask*`.
- Avoid cross-region mutable state without explicit synchronization.
- Treat event handlers as potentially parallel - do not assume two events run on the same thread.
- Prefer async-safe APIs where teleport, chunk access, or world interaction can cross ownership boundaries (`teleportAsync`, `getChunkAtAsync`).
- Use `Bukkit.isOwnedByCurrentRegion(entityOrLocation)` before mutating entity state in a generic listener.

## What SilkMC tries to help with

- loading legacy plugins in warning mode instead of refusing immediately
- bridging legacy sync scheduler calls to the Global Region Scheduler so plugins do not crash on `runTaskLater` / `runTaskTimer`
- bridging legacy sync `Entity.teleport()` / `Player.teleport()` to the async variant when on the owning region
- classifying compatibility failures with a clear operator-facing message and auto-disabling the offending plugin to keep the server stable
- documenting unsafe assumptions clearly
- exposing compatibility toggles for transition periods (`silkmc-compatibility.yml`)

## What SilkMC will not do

- introduce a fake global main thread that mutates world state
- silently succeed when a cross-region write cannot be safely performed
- bypass region ownership checks to keep a plugin running

## Patterns that travel well

```java
// Schedule on the entity's owning region
entity.getScheduler().run(plugin, task -> {
    entity.setHealth(20);
}, null);

// Schedule global tick work
Bukkit.getGlobalRegionScheduler().run(plugin, task -> { /* ... */ });

// Async teleport (works on Paper, Folia, SilkMC)
player.teleportAsync(target).thenAccept(success -> { /* ... */ });
```

## Patterns to avoid on SilkMC

```java
// Legacy sync schedule with no region context.
// SilkMC bridges this through the Global Region Scheduler, but plugins should
// migrate to the region/entity/global schedulers explicitly.
Bukkit.getScheduler().runTaskTimer(plugin, () -> { /* ... */ }, 0L, 20L);

// Synchronous cross-world teleport in a tick callback.
// SilkMC will warn and return optimistically; the actual teleport runs async.
entity.teleport(somewhereInAnotherWorld);
```

## Detection

Plugins that want to identify the server platform can check `Bukkit.getServer().getName()` or `ServerBuildInfo`. SilkMC reports brand `SilkMC` with key `gg.tame:silkmc`. The upstream Folia classes still exist under their original packages for binary compatibility, so feature-detection (rather than name-detection) remains the most reliable approach.
