# SilkMC region workload benchmark harness

A deterministic, client-free workload generator for measuring SilkMC's region scheduler, region
parallelism, entity ticking, chunk ticking and global-region behaviour.

Standard library Python only. Nothing is downloaded or installed, and the harness adds no
instrumentation to the server's tick loop.

## What this measures - and what it does not

This harness exists so that performance changes to the region scheduler, tick loop and memory
behaviour can be compared before and after. It is **not** a substitute for a real player/bot
benchmark.

| Exercised | Not exercised |
| --- | --- |
| Region creation and parallel region ticking | Connection tick (`RegionizedServer.tickConnections`) |
| Entity ticking (real AI, real pathfinding) | Player packet processing |
| Chunk ticking via `forceload` | Player-count scaling |
| Block/redstone updates (`--workload redstone`) | Anything requiring a connected client |
| Global-region tick cost | Chunk loading driven by player movement |

The connection-tick paths are exactly the ones that scale with player count, and they cannot be
reached without clients. Do not draw conclusions about them from this harness.

## How it works

1. Writes a fresh server directory: `server.properties` (superflat, fixed seed) and
   `config/paper-global.yml` carrying the `threaded-regions` thread count and scheduler for the run.
   Production defaults are never modified - each run gets its own directory.
2. Launches the server and drives it entirely through **console commands** on stdin.
3. `forceload`s a cluster of chunks per region. Forceload is what keeps chunks ticking with no player
   online, and is the reason this harness can work at all without clients.
4. Summons a deterministic entity population per region (seeded RNG, so the same config and seed
   always produce the same placement).
5. Warms up, then samples `/silkmc bench` on an interval.
6. Aggregates: median across samples within a repetition, then median across repetitions.

### Keeping regions apart

The single most important correctness property is that the run actually creates the requested number
of regions rather than one merged blob. Clusters are separated by `--region-spacing-chunks`
(default 96), and the harness **refuses to run** if that spacing is smaller than the workload
footprint plus two regioniser sections (`2^grid-exponent`, default 16 chunks).

Always check `Rgn` and `Act` in the output table against what you asked for. If `Rgn` is 1 when you
asked for 8, the run measured a single region and the numbers mean nothing about parallelism.

### Determinism

Gamerules are set to remove every source of drift we can control: no daylight or weather cycle, no
random block ticks, no natural mob spawning, no mob griefing, no fire spread, no raids. Entity
placement is seeded. Repeated runs with the same config produce equivalent workloads.

Determinism is *not* perfect - JIT warmup, GC timing and OS scheduling still vary - which is why the
methodology uses a warmup period, multiple repetitions and medians.

## Metrics

### Automated (collected by the harness)

Read from `/silkmc bench`, which reports the tick windows the server **already maintains**. No
instrumentation is added to the tick loop; the command only formats data that is collected on every
region tick regardless.

| Metric | Source |
| --- | --- |
| **TPS (per region, global)** | `tpsData().segmentAll().average()` |
| Average MSPT (per region, global) | `timePerTickData().segmentAll().average()` |
| Median MSPT | `segmentAll().median()` |
| Worst 5% / worst 1% MSPT | `segment5PercentWorst()` / `segment1PercentWorst()` |
| Worst single tick | `segmentAll().greatest()` |
| Utilisation (wall, **not** CPU) | `TickReportData.utilisation()` |
| Blocked time per tick | `missingCPUTimeData().segmentAll().average()` |
| Region count / active region count | regioniser enumeration |
| Tick threads | `TickRegions.getScheduler().getTotalThreadCount()` |
| Chunks / entities / players per region | `TickRegions.RegionStats` |
| Heap used / max | `Runtime` |

**Read TPS and MSPT together, and read TPS first.** When a region cannot keep up it skips ticks, and
the ticks it does manage are the cheap ones - so its *average MSPT falls* while the server gets
worse. A configuration that looks best on MSPT can be the one that is failing. This is not
hypothetical: the first saturated matrix run here showed 1 tick thread with the *lowest* MSPT of any
configuration (12.9 ms) while actually running at 11.9 TPS, against 20.07 TPS everywhere else. The
`minTPS` column exists so that trap is visible in the table rather than something you have to
remember to check.

**Utilisation is wall time, not CPU time.** `utilisation` is the fraction of the interval that a
region spent *inside* its tick method - and a region blocked on a lock is still inside its tick. So
`SumUtil` rising with thread count does **not** by itself mean more CPU is being burned; it can
equally mean threads are spending longer waiting. This is an easy and tempting misreading, and it
was made here before the `Blocked` column existed.

`Blocked` is the mean per-tick wall time during which the region thread held no CPU at all
(`tick wall time - tick CPU time`). Read the two together:

- `SumUtil` up, `Blocked` flat -> the extra utilisation is real work.
- `SumUtil` up, `Blocked` up -> the extra utilisation is contention, and adding threads is making
  things worse rather than better.

Measured on the saturating baseline (8 regions, EDF, medians of 2 reps), all rows at ~20 TPS:

| Threads | WorstRgn avg | Blocked | avg - Blocked (on-CPU) | SumUtil |
| --: | --: | --: | --: | --: |
| 2 | 11.445 | 3.051 | 8.39 | 1.393 |
| 4 | 12.654 | 2.761 | 9.89 | 1.570 |
| 8 | 15.400 | 1.981 | 13.42 | 2.135 |

Blocked time *falls* as threads are added, so the rising utilisation is not lock contention. On-CPU
time per tick rises ~60% instead, for identical work at identical TPS - consistent with memory-system
effects (less cache sharing, more cross-core traffic) rather than with anything in the region locking
design.

**On "P95/P99":** the server tracks the *mean of the worst 5%* and *mean of the worst 1%* of ticks,
not true percentiles. These are reported as `worst5%` and `worst1%` rather than relabelled p95/p99,
because they are not the same thing and at small sample counts the two can even order
counter-intuitively. Use `maxTick` for the genuine worst tick.

### External (JFR / OS tools)

These are deliberately **not** collected by the server, to avoid adding tick-loop overhead:

| Metric | How |
| --- | --- |
| CPU utilisation | `--jfr` then read `jdk.CPULoad`, or OS tools during the run |
| Allocation rate | `--jfr` then `jdk.ObjectAllocationSample` |
| GC time / count / pause distribution | `--jfr` then `jdk.GCPhasePause`, `jdk.YoungGarbageCollection` |
| Per-thread CPU | `--jfr` then `jdk.ThreadCPULoad` (shows tick-thread utilisation directly) |
| Heap over time | `--jfr` then `jdk.GCHeapSummary` |

`--jfr` starts a `settings=profile` recording dumped to `recording.jfr` in each run directory. JFR
ships with the JDK; nothing extra is needed. Read it with `jfr summary`, `jfr print`, or JDK Mission
Control.

## Usage

```bash
python tools/benchmark/silkbench.py \
  --jar silkmc-server/build/libs/silkmc-paperclip-26.2.local-SNAPSHOT.jar \
  --out bench-results \
  --regions 4 --chunks-per-region 6 --entities-per-region 800 \
  --warmup 45 --measure 60 --reps 2 \
  --threads 1 2 4 6 8 --schedulers EDF WORK_STEALING
```

Entity density presets are available instead of `--entities-per-region`:

```bash
--density light      # 20 entities/region
--density medium     # 80
--density heavy      # 200
--density extreme    # 500
```

Redstone / block-update workload:

```bash
--workload hopper --block-layers 4    # planes of hopper block entities (heaviest per command)
--workload redstone --block-layers 2  # redstone planes driven by torch/repeater clocks
--workload mixed --block-layers 4     # entities + hoppers + redstone
```

**Recommended saturating baseline** (needs ~2.4 tick threads):

```bash
python tools/benchmark/silkbench.py   --jar silkmc-server/build/libs/silkmc-paperclip-26.2.local-SNAPSHOT.jar   --out bench-results   --regions 8 --chunks-per-region 8 --entities-per-region 300   --workload mixed --block-layers 4   --warmup 45 --measure 60 --reps 2   --threads 1 2 4 6 8 --schedulers EDF WORK_STEALING --heap 8G
```

With JFR for CPU/GC/allocation:

```bash
--jfr --reps 1 --measure 120
```

### Key options

| Option | Default | Meaning |
| --- | --- | --- |
| `--regions` | 4 | Number of separate region clusters |
| `--chunks-per-region` | 4 | Side length; `n^2` chunks forceloaded per region |
| `--entities-per-region` | 80 | Entity population per region |
| `--region-spacing-chunks` | 96 | Distance between clusters; guards against merging |
| `--warmup` / `--measure` | 120 / 180 | Seconds |
| `--reps` | 3 | Repetitions; results are medians |
| `--seed` | 1234 | Entity placement and level seed |
| `--threads` | `-1` | Tick thread counts to sweep (`-1` = SilkMC default) |
| `--schedulers` | `EDF` | `EDF` and/or `WORK_STEALING` |
| `--heap` | 4G | `-Xms`/`-Xmx` |
| `--workload` | entity | `entity`, `hopper`, `redstone`, `mixed` |
| `--block-layers` | 1 | Planes of ticking blocks per region; the main load dial |
| `--random-tick-speed` | 0 | 0 keeps runs deterministic; raising it adds block-tick load |
| `--jvm-arg` | - | Extra JVM argument, repeatable; appended after the baseline flags |

`--jvm-arg` is what makes GC hypotheses testable without editing the harness. Because the value
starts with `-`, it must be passed with an `=` or argparse will read it as another option:

```bash
--jvm-arg=-XX:G1MaxNewSizePercent=15     # correct
--jvm-arg -XX:G1MaxNewSizePercent=15     # error: expected one argument
```

## Relationship to `docs/benchmarking.md`

`docs/benchmarking.md` describes the player-based methodology (warmup, sampling window, repetitions,
medians) and assumes real clients connect. This harness follows the same **methodology** - warmup,
timed measurement window, multiple repetitions, median reporting - but replaces the player-driven
workload with forceloaded chunks and summoned entities.

The consequence is that the "Player-spread SMP" scenario in that document cannot be reproduced here,
and neither can anything that depends on connection ticking. Those still need real clients or bots.

## Reaching saturation

An entity-only workload cannot saturate the server: `summon` places one entity per console command,
so the achievable population is bounded by command throughput, and passive mobs on superflat are
cheap. Even 1500 cows/region across 4 regions leaves total utilisation around 0.10 - ten percent of a
single thread - at which point thread count and scheduler cannot possibly matter, and a matrix run at
that level measures nothing but noise.

Block entities are the lever. `/fill` places thousands per command, and every hopper block entity
runs its transfer logic each tick (Paper's hopper options here do not skip idle hoppers). Use
`--workload hopper` or `--workload mixed` with `--block-layers`.

Measured on a 12-core machine, superflat, `--chunks-per-region 8`:

| Config | Worst-region avg MSPT | SumUtil |
| --- | --: | --: |
| 4 regions, 800 cows/region | 1.4 | 0.10 |
| 4 regions, hoppers, 2 layers | 7.7 | 0.59 |
| 4 regions, mixed, 4 layers, 300 cows | 14.0 | 0.93 |
| **8 regions, mixed, 4 layers, 300 cows** | **17.5** | **2.40** |

`SumUtil` is the number to watch: it is total region utilisation, so `1.0` means one tick thread's
worth of work. **Below ~1.0 a thread-count or scheduler comparison is meaningless.** The last row is
the recommended baseline config - it needs roughly 2.4 threads, so adding threads has something to
actually do.

## Verifying a run actually did something

Every repetition prints:

```
setup_ok=True chunks=1152 blocksChanged=1052480
```

- `setup_ok` - all chunks loaded and no content command hit an unloaded chunk.
- `chunks` - chunks actually loaded, compared against `regions * chunks_per_region^2`.
- `blocksChanged` - blocks confirmed placed, parsed from `/fill` and `/setblock` responses.

**Do not trust a run where `blocksChanged` is 0 or `setup_ok` is False.** Both failure modes produce
plausible-looking MSPT numbers for a world that is actually empty. Two real bugs found during
development had exactly this signature:

- Gamerule identifiers are snake_case in this Minecraft version (`spawn_mobs`, `advance_weather`,
  `random_tick_speed`), not the historical camelCase. The old names are rejected, and the workload
  then runs with natural mob spawning still enabled.
- `/fill` and `/summon` run before `forceload` has finished loading chunks unless the harness waits,
  and every one is rejected with "That position is not loaded".

Both are fixed, and both are now detected rather than assumed.

## GC pauses

A stop-the-world pause halts *every* region thread at once, so it is the one cost regionisation
cannot amortise: it is the same pause on a 1-thread server and an 8-thread one.

Measured on the saturating baseline with the flags in `docs/benchmarking.md` (8G heap), against the
same flags with a smaller young generation (`G1NewSizePercent=5`, `G1MaxNewSizePercent=15`), two runs
per arm:

| Arm | Pauses | Total GC ms | Mean pause | **Worst pause** |
| --- | --: | --: | --: | --: |
| Documented flags | 79 / 79 | 972 / 970 | 12.3 / 12.3 | **119 / 118** |
| Smaller young gen | 204 / 184 | 1080 / 1026 | 5.3 / 5.6 | **64 / 65** |

The GC effect is large and reproduces tightly: worst pause roughly halves and mean pause drops ~55%,
paid for with ~2.4x as many pauses and ~6% more total GC time. Throughput is unaffected (both arms
held ~20 TPS at ~11.4 ms average).

**What is *not* established is that this improves the observed tick tail.** The first pair of runs
showed `maxTick` falling 20.6 -> 14.3 and that looked conclusive; the confirmation pair had the
baseline at 15.2 against 15.1, i.e. no difference at all. The 20.6 was baseline variance, not the
flags. Worst-tick figures here are medians of 15-second windows, and the handful of pauses that
exceed a tick budget are rare enough that they often do not land in a sampled window - so this
harness can measure the pause distribution reliably but cannot currently resolve its effect on tick
tails. Do not cite a tail-latency improvement from these numbers.

## Known limitations

- **Setup time scales with entity count.** Entities are summoned one console command at a time;
  block workloads do not have this problem.
- **No connection-tick coverage.** See the table at the top.
- **`worst5%` / `worst1%` are not true percentiles.** See the metrics note above.
- Superflat terrain means no worldgen cost and no terrain variety; chunk *generation* is not
  meaningfully exercised.
