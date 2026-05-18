# SilkMC

SilkMC is an open-source Minecraft server platform focused on smooth multithreaded performance and practical plugin compatibility.

It preserves Folia's regional multithreading architecture while presenting SilkMC as its own project, with upstream attribution kept to the places where it is legally and technically required.

## Goals

- Preserve high-throughput regional multithreading.
- Maximize compatibility with Paper, Bukkit, and Spigot plugins.
- Keep vanilla gameplay stable: redstone, AI, chunk loading, combat, scoreboards, commands, world generation, and networking.
- Prefer safe fallbacks, detailed warnings, and maintainable architecture over risky hacks.

## Current state

- Upstream baseline: Folia `26.1.2` (`ver/26.1.x`, synced May 17, 2026)
- Project stage: `v0.1.2-alpha`
- Java toolchain: JDK 25
- Build system: Gradle + Paperweight patch workflow

## Compatibility stance

SilkMC is compatibility-focused by default.

- Plugins marked with `silk-supported: true` are treated as compatibility-aware.
- Legacy `folia-supported: true` metadata is still honored for upstream interoperability.
- Unmarked plugins can be allowed with warnings through SilkMC compatibility policy instead of being hard-blocked immediately.
- Unsafe assumptions still fail safely where the server cannot preserve correctness.

See [docs/compatibility.md](docs/compatibility.md) and [docs/migration/plugin-developers.md](docs/migration/plugin-developers.md).

## Build

```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
./gradlew applyAllPatches
./gradlew build
./gradlew :silkmc-server:createPaperclipJar
```

Use the runnable Paperclip-style server jar for local testing and releases:

```powershell
java -Xms4G -Xmx4G -jar .\silkmc-server\build\libs\silkmc-paperclip-26.1.2.local-SNAPSHOT.jar nogui
```

The plain `silkmc-server` jar is a module artifact and is not intended to be launched standalone.

## Repository layout

- `silkmc-api/` - maintained API patches and module build logic
- `silkmc-server/` - maintained server patches and module build logic
- `paper-api/` and `paper-server/` - generated working trees from patch application
- `.github/` - CI, release automation, templates
- `docs/` - architecture, compatibility, benchmarking, and contributor docs
- `examples/server/` - example setup and config snippets

## Development workflow

```powershell
./gradlew applyAllPatches
./gradlew build
./rb.bat
```

`rb.bat` rebuilds maintained patch files after editing the generated `paper-*` source trees.

## Documentation

- [Architecture](docs/architecture.md)
- [Compatibility Guide](docs/compatibility.md)
- [Plugin Migration Guide](docs/migration/plugin-developers.md)
- [Compatibility Testing](docs/testing/compatibility-matrix.md)
- [Plugin Compatibility Reports](docs/testing/plugin-compatibility-reports.md)
- [Benchmarking](docs/benchmarking.md)
- [Upstream and Attribution](docs/development/upstream.md)
- [Alpha Release Notes](docs/releases/v0.1.2-alpha.md)

## Attribution

SilkMC is derived from Folia and Paper. Upstream names are retained only where required for license compliance, attribution, or developer-facing upstream maintenance notes.
