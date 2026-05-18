# Plugin Developer Migration

## Recommended metadata

Add this to `plugin.yml`:

```yaml
silk-supported: true
```

SilkMC also honors the legacy upstream key:

```yaml
folia-supported: true
```

## Practical guidance

- use region, entity, async, and global schedulers intentionally
- avoid cross-region mutable state without explicit synchronization
- treat event handlers as potentially parallel
- prefer async-safe APIs where teleport, chunk access, or world interaction can cross ownership boundaries

## What SilkMC tries to help with

- loading legacy plugins in warning mode instead of refusing immediately
- documenting unsafe assumptions clearly
- exposing compatibility toggles for transition periods
