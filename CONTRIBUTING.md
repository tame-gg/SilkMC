# Contributing to SilkMC

Thanks for helping with SilkMC.

## Principles

- Preserve correctness first.
- Prefer compatibility shims and warnings over unsafe behavior.
- Keep changes small and upstream-mergeable when possible.
- Document user-facing behavior changes.

## Local setup

1. Install JDK 25.
2. Set `JAVA_HOME` to that JDK.
3. Run `./gradlew applyAllPatches`.
4. Make changes in the generated `paper-api/` or `paper-server/` trees unless the change belongs in repository scaffolding.
5. Run `./rb.bat` or `./rb.sh` to rebuild patch files.
6. Run `./gradlew build`.

## Patch workflow

- Maintained patch sources live in `silkmc-api/` and `silkmc-server/`.
- Generated working trees live in `paper-api/` and `paper-server/`.
- Keep upstream attribution intact in patch headers.

## Compatibility changes

When changing compatibility behavior:

- explain the failure mode being addressed
- document what remains unsafe
- add or update migration notes
- favor warnings and opt-in modes over silent behavior changes

## Pull requests

- keep the scope focused
- include test evidence or explain why tests were not practical
- call out upstream-sensitive changes clearly
