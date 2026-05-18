# Compatibility Testing

Initial validation targets for SilkMC:

- Paper-oriented plugins with scheduler usage
- Bukkit and Spigot plugins with legacy sync assumptions
- vanilla gameplay systems: redstone, chunk loading, combat, inventories, commands, networking, scoreboards, world generation

## Suggested matrix

- no plugins
- Paper-only plugin pack
- mixed Paper/Bukkit/Spigot plugin pack
- plugin pack with known scheduler-heavy workloads

## Pass criteria

- clean startup
- no thread-ownership crashes during smoke tests
- expected `/version` and branding output
- world save/load integrity
- legacy `runTask` / `runTaskTimer` calls execute without `UnsupportedOperationException`
- legacy sync `teleport` calls succeed or warn gracefully
