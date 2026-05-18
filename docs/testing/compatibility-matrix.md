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

## CI smoke test

The repository ships a curated plugin smoke test in `.github/workflows/smoke-test.yml`.

- It builds the SilkMC paperclip jar on every pull request and every push to `main`.
- It stages a disposable offline-mode server with a pinned plugin pack from official project sources.
- It fails the job when `logs/latest.log` contains unallowlisted `ERROR` or `SEVERE` lines.
- It always uploads `logs/latest.log` so regressions can be triaged from CI artifacts.
