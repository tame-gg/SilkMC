# Example SilkMC Server Setup

A minimal walkthrough for getting SilkMC running locally.

## 1. Pick a JVM

SilkMC requires JDK 25 (Temurin or any recent OpenJDK distribution is fine). Confirm with:

```powershell
java -version
```

## 2. Download a paperclip jar

Use the runnable paperclip-style jar built by `:silkmc-server:createPaperclipJar` or downloaded from the latest GitHub release: <https://github.com/tame-gg/SilkMC/releases>.

## 3. Start the server

```powershell
java -Xms4G -Xmx4G -jar silkmc-paperclip.jar nogui
```

`-Xms` and `-Xmx` should match each other and your machine's available RAM. For benchmarking flag suggestions see [docs/benchmarking.md](../../docs/benchmarking.md).

## 4. Tune compatibility

On first startup SilkMC writes a `silkmc-compatibility.yml` next to `eula.txt`. The example in this folder is a copy of the defaults:

- `silkmc-compatibility.yml` - SilkMC compatibility policy

For full description of each key see [docs/compatibility.md](../../docs/compatibility.md).

## 5. Add plugins

Drop plugins into the `plugins/` directory. SilkMC will, by default:

- accept plugins marked `silk-supported: true` or `folia-supported: true` without question
- accept unmarked plugins with a warning
- auto-disable plugins that hit known unsafe compatibility boundaries (with a clear log message)

Switch to strict enforcement by setting:

```yaml
plugins:
  unsupported-plugin-mode: REQUIRE_DECLARATION
```

## Example values

- `motd=SilkMC | smooth, lightweight, compatibility-focused`
- pregenerated worlds for high player-count deployments
- enable compatibility warning mode first when migrating plugin packs

## Note

The `silkmc-server` module jar is not self-contained and should not be used as the end-user startup jar. Use the paperclip jar.
