# Plugin Compatibility Reports

This page tracks observed compatibility outcomes for popular plugins on SilkMC. Reports come from internal smoke tests and community feedback.

Status values:

- **Works** - loads and runs without intervention.
- **Works with metadata** - loads after adding `silk-supported: true` (or `folia-supported: true`).
- **Works (warnings)** - loads in compatibility warning mode; behavior verified.
- **Partial** - core functionality works, with documented caveats.
- **Incompatible** - cannot be used safely; SilkMC will refuse or auto-disable.

## Starter matrix

| Plugin family            | Type        | Status               | Notes                                                                                                                  |
| ------------------------ | ----------- | -------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| EssentialsX              | Bukkit/Spigot | Works (warnings)   | Legacy sync scheduler usage is bridged. Heavy cross-region teleport patterns may emit warnings.                        |
| LuckPerms                | Paper/Bukkit | Works              | Uses async-safe APIs and its own thread management.                                                                    |
| Vault                    | Bukkit       | Works (warnings)   | Wrapper plugin; depends on the providers it adapts.                                                                    |
| PlaceholderAPI           | Bukkit       | Works (warnings)   | Most expansions are region-safe; some legacy expansions may need adjustment.                                           |
| WorldEdit                | Bukkit       | Partial            | Async edits work. Large region-spanning operations should be staged through async edit sessions.                       |
| WorldGuard               | Bukkit       | Partial            | Region flags and protections work. Some legacy listeners assume a single main thread.                                  |
| ProtocolLib              | Bukkit       | Works with metadata | Operates near-protocol; tested with `silk-supported: true` for known-compatible builds.                                |
| ViaVersion / ViaBackwards | Bukkit     | Works              | Designed to be thread-aware.                                                                                           |
| Multiverse-Core          | Bukkit       | Partial            | World creation and teleport now route through async teleport bridge; large cross-world batch operations may warn.       |
| CoreProtect              | Bukkit       | Works              | Async-first design.                                                                                                    |
| GriefPrevention          | Bukkit       | Partial            | Most listeners work; some bulk admin operations across regions are sequenced through the global region scheduler.       |
| dynmap                   | Bukkit       | Works              | Render workers use their own threads; map updates are async-safe.                                                      |
| BlueMap                  | Paper        | Works              | Async-first by design.                                                                                                 |

## How to contribute a report

1. Open an issue using the "Plugin compatibility" template.
2. Include plugin name, version, SilkMC version, and outcome.
3. Attach the relevant lines of `logs/latest.log` if a compatibility failure was logged.
4. If you added `silk-supported: true` locally, mention it.

## Disclaimer

These reports reflect observed behavior at the moment of testing. Plugin authors may change behavior in future releases, and SilkMC compatibility coverage continues to evolve.
