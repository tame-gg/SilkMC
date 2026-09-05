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

### API and Paper-server changes

`paper-api/` and `paper-server/` are git repositories, and **each commit in them becomes a feature
patch**. The workflow is:

1. Edit files in `paper-server/` (or `paper-api/`).
2. Commit inside that tree, with one commit per logical change - the commit message becomes the
   patch filename, and separate commits keep regressions bisectable.
3. Run `./rb.bat` / `./rb.sh` from the repository root.
4. The new patches appear under `silkmc-server/paper-patches/features/`.

Uncommitted changes in those trees are **not** captured by `rb`, and they are destroyed the next time
`./gradlew applyAllPatches` runs.

### NMS (`silkmc-server/src/minecraft/`) changes

> **This tree behaves differently. Read this before editing it.**

`silkmc-server/src/minecraft/` is a **generated output**, not a tracked source root. It is listed in
`.gitignore`, it has no git repository of its own, and - unlike `paper-server/` - **`rb` does not
capture edits made to it**. `rebuildMinecraftPatches` derives its output from a separate baseline
under `silkmc-server/.gradle/caches/paperweight/`, never from `src/minecraft`.

The practical consequence: if you edit a file under `silkmc-server/src/minecraft/`, run `./rb.sh`,
and then run `./gradlew applyAllPatches`, **your work is silently gone**. No error is reported, and
the regenerated patch files are byte-identical to what they were before.

Until the tooling is changed, capture NMS changes manually:

1. Make and test your edits in `silkmc-server/src/minecraft/java/...`.
2. Copy the edited files somewhere safe (this is the "after" state).
3. Run `./gradlew applyAllPatches` to reset the tree to its patched state, and copy the same files
   again (this is the "before" state).
4. Produce a diff, rewriting the path prefixes so they are relative to the minecraft source root
   (`a/net/minecraft/...`, not `a/before/net/minecraft/...`):

   ```bash
   git diff --no-index --src-prefix=a/ --dst-prefix=b/ before after > raw.diff
   sed -e 's|^diff --git a/before/|diff --git a/|' \
       -e 's| b/after/| b/|' \
       -e 's|^--- a/before/|--- a/|' \
       -e 's|^+++ b/after/|+++ b/|' raw.diff > clean.diff
   ```

5. Write the patch to `silkmc-server/minecraft-patches/features/` using the next free number, with a
   git mailbox header matching the existing patches:

   ```
   From 0000000000000000000000000000000000000000 Mon Sep 17 00:00:00 2001
   From: Your Name <you@example.com>
   Date: <date>
   Subject: [PATCH] Short description

   <clean.diff contents>
   ```

6. **Verify it applies**: run `./gradlew applyAllPatches` again and confirm your changes are present
   in `silkmc-server/src/minecraft/`. A patch that does not round-trip is not finished.
7. Build and run the test suite.

Do not modify `rb.sh` to work around this. Whether `src/minecraft` is intended to be a git-backed
tree is a question for Paperweight upstream, and guessing at it risks corrupting the patch set.

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
