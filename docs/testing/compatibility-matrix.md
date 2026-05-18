# Compatibility Testing

This page describes how SilkMC validates compatibility with the Paper, Bukkit, and Spigot plugin ecosystems. It is intended for contributors and server operators who want to reproduce or extend the suite.

## Initial validation targets

- Paper-oriented plugins with scheduler usage
- Bukkit and Spigot plugins with legacy sync assumptions
- vanilla gameplay systems: redstone, chunk loading, combat, inventories, commands, networking, scoreboards, world generation

## Suggested matrix

| Tier | Plugin pack                                       | Goal                                                                    |
| ---- | ------------------------------------------------- | ----------------------------------------------------------------------- |
| 1    | no plugins                                        | Verify clean SilkMC startup and vanilla gameplay regressions.           |
| 2    | Paper-only plugin pack                            | Verify modern plugins keep their behavior unchanged.                    |
| 3    | mixed Paper/Bukkit/Spigot plugin pack             | Verify legacy plugin survivability through the compatibility layer.     |
| 4    | scheduler-heavy plugin pack (lots of `runTaskTimer`) | Verify scheduler bridging stability and overhead.                    |
| 5    | teleport-heavy plugin pack (warps, multiverse)    | Verify teleport bridging stability.                                     |

## Pass criteria

- clean startup with `SilkMC` branding in the banner and `/version`
- no thread-ownership crashes during smoke tests
- expected `/version` and build metadata output
- world save/load integrity preserved
- legacy `runTask` / `runTaskTimer` calls execute without `UnsupportedOperationException`
- legacy synchronous `teleport` calls succeed or downgrade to a clear warning rather than crash
- compatibility config file (`silkmc-compatibility.yml`) is auto-generated on first startup with sane defaults
- compatibility log entries are actionable: plugin name, phase, and operator-facing reason are present

## Smoke test checklist

The SilkMC team runs this checklist before tagging a release.

- [ ] Server starts on JDK 25 with default config
- [ ] `silkmc-compatibility.yml` is generated on first run
- [ ] Login, chat, inventory, and command flow work in survival mode
- [ ] A second player can join while the first explores far chunks (forces region split)
- [ ] At least one legacy `runTask` and one legacy sync `teleport` plugin runs without crashing
- [ ] No unhandled `UnsupportedOperationException` appears in `logs/latest.log`
- [ ] Compatibility warnings appear when expected and include plugin name and phase
- [ ] World saves and reloads cleanly across restart

## Reporting compatibility outcomes

Open issues using the "Plugin compatibility" template. Include:

- SilkMC build hash
- plugin name and version
- whether the plugin was marked `silk-supported` or `folia-supported`
- relevant compatibility log lines

See also: [plugin-compatibility-reports.md](plugin-compatibility-reports.md).
