#!/usr/bin/env python3
"""SilkMC region-workload benchmark harness.

Generates a deterministic, server-side workload that exercises real region ticking without any
external client, then samples the statistics the server already maintains.

See README.md in this directory for what this does and does not measure.

Standard library only - nothing is downloaded or installed.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import random
import re
import shutil
import statistics
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

# --------------------------------------------------------------------------------------------------
# Workload definition
# --------------------------------------------------------------------------------------------------

# Entity densities, in entities per region. "Light" is roughly an idle farm; "extreme" is well past
# what a healthy server would carry, and is there to show where MSPT falls over.
DENSITIES = {"light": 20, "medium": 80, "heavy": 200, "extreme": 500}

# Mobs that tick meaningfully (AI, pathfinding, collision) but do not despawn, wander far, breed or
# fight, so the workload stays stable across the measurement window and between repetitions.
# NoAI would defeat the purpose - the point is to tick real AI.
WORKLOAD_MOBS = {
    "entity": "minecraft:cow",
    "mixed": "minecraft:cow",
}


@dataclass
class BenchConfig:
    regions: int = 4
    chunks_per_region: int = 4          # side length: chunks_per_region^2 chunks forceloaded per region
    entities_per_region: int = 80
    density: str | None = None          # overrides entities_per_region when set
    workload: str = "entity"            # entity | redstone | mixed
    region_spacing_chunks: int = 96     # must exceed the region grid size so regions cannot merge
    warmup_seconds: int = 120
    measure_seconds: int = 180
    sample_interval_seconds: int = 15
    repetitions: int = 3
    seed: int = 1234
    threads: int = -1                   # -1 = SilkMC default
    scheduler: str = "EDF"              # EDF | WORK_STEALING
    heap: str = "4G"
    jfr: bool = False
    grid_exponent: int = 4              # SilkMC default; region section = 2^grid_exponent chunks
    block_layers: int = 1               # planes of ticking blocks (hoppers/redstone) per region
    random_tick_speed: int = 0          # 0 keeps the run deterministic; raise to add block-tick load

    def entity_count(self) -> int:
        if self.density:
            return DENSITIES[self.density]
        return self.entities_per_region


# --------------------------------------------------------------------------------------------------
# Server process control
# --------------------------------------------------------------------------------------------------


class ServerProcess:
    """Drives a server over stdin/stdout. Console commands are the only interface used."""

    READY = re.compile(r'\]: Done \([0-9.]+s\)!')

    def __init__(self, jar: Path, cwd: Path, heap: str, jfr_path: Path | None):
        self.jar = jar
        self.cwd = cwd
        self.heap = heap
        self.jfr_path = jfr_path
        self.proc: subprocess.Popen | None = None
        self.lines: "queue.Queue[str]" = queue.Queue()
        self._reader: threading.Thread | None = None
        self._log: list[str] = []

    def _pump(self) -> None:
        assert self.proc and self.proc.stdout
        for raw in self.proc.stdout:
            line = raw.rstrip("\n")
            self._log.append(line)
            self.lines.put(line)
        self.lines.put(None)  # type: ignore[arg-type]

    def start(self, java: str) -> None:
        flags = [
            java,
            f"-Xms{self.heap}", f"-Xmx{self.heap}",
            "-XX:+UseG1GC", "-XX:+ParallelRefProcEnabled", "-XX:MaxGCPauseMillis=200",
            "-XX:+UnlockExperimentalVMOptions", "-XX:+DisableExplicitGC", "-XX:+AlwaysPreTouch",
            "-XX:G1NewSizePercent=30", "-XX:G1MaxNewSizePercent=40", "-XX:G1HeapRegionSize=8M",
            "-XX:G1ReservePercent=20", "-XX:G1HeapWastePercent=5", "-XX:G1MixedGCCountTarget=4",
        ]
        if self.jfr_path:
            flags.append(
                "-XX:StartFlightRecording=settings=profile,disk=true,"
                f"filename={self.jfr_path},dumponexit=true"
            )
        flags += ["-jar", str(self.jar), "nogui"]

        self.proc = subprocess.Popen(
            flags, cwd=str(self.cwd), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, bufsize=1,
        )
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

    def wait_ready(self, timeout: float = 300.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                line = self.lines.get(timeout=1.0)
            except queue.Empty:
                continue
            if line is None:
                return False
            if self.READY.search(line):
                return True
        return False

    def send(self, command: str) -> None:
        assert self.proc and self.proc.stdin
        self.proc.stdin.write(command + "\n")
        self.proc.stdin.flush()

    def drain(self) -> list[str]:
        out = []
        while True:
            try:
                line = self.lines.get_nowait()
            except queue.Empty:
                break
            if line is None:
                break
            out.append(line)
        return out

    def collect(self, marker: str, timeout: float = 20.0) -> list[str]:
        """Sends nothing; waits for lines containing `marker` to stop arriving."""
        got: list[str] = []
        deadline = time.time() + timeout
        idle_after_first = 2.0
        last = None
        while time.time() < deadline:
            try:
                line = self.lines.get(timeout=0.5)
            except queue.Empty:
                if got and last and (time.time() - last) > idle_after_first:
                    break
                continue
            if line is None:
                break
            if marker in line:
                got.append(line)
                last = time.time()
        return got

    def stop(self, timeout: float = 180.0) -> None:
        if not self.proc:
            return
        try:
            self.send("stop")
        except Exception:
            pass
        try:
            self.proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.proc.kill()

    def save_log(self, path: Path) -> None:
        path.write_text("\n".join(self._log), encoding="utf-8", errors="replace")


# --------------------------------------------------------------------------------------------------
# World setup
# --------------------------------------------------------------------------------------------------


def region_origins(cfg: BenchConfig) -> list[tuple[int, int]]:
    """Chunk coordinates for each region cluster.

    Clusters are laid out on a grid and separated by `region_spacing_chunks`. The separation must be
    larger than the workload footprint plus the regioniser's own section size, or adjacent clusters
    end up in one region and the run silently measures a single region instead of N.
    """
    section = 1 << cfg.grid_exponent
    footprint = cfg.chunks_per_region
    minimum = footprint + 2 * section
    if cfg.region_spacing_chunks < minimum:
        raise SystemExit(
            f"region_spacing_chunks={cfg.region_spacing_chunks} is too small for "
            f"chunks_per_region={footprint} at grid_exponent={cfg.grid_exponent}; "
            f"need at least {minimum} or regions will merge."
        )

    side = 1
    while side * side < cfg.regions:
        side += 1

    origins = []
    for i in range(cfg.regions):
        gx, gz = i % side, i // side
        origins.append((gx * cfg.region_spacing_chunks, gz * cfg.region_spacing_chunks))
    return origins


# Vanilla's /fill has a hard block limit per command.
FILL_LIMIT = 32768


def _fill(x0: int, z0: int, x1: int, z1: int, y: int, block: str) -> list[str]:
    """Fills a horizontal plane, splitting into strips so no single command exceeds /fill's limit.

    Bulk block placement is what makes a saturating workload practical at all: `summon` places one
    entity per command, so an entity-only workload is bounded by how many console commands can be
    pushed through stdin, while a single `fill` can create thousands of ticking block entities.
    """
    width = x1 - x0 + 1
    depth = z1 - z0 + 1
    if width * depth <= FILL_LIMIT:
        return [f"fill {x0} {y} {z0} {x1} {y} {z1} {block}"]

    rows_per_cmd = max(1, FILL_LIMIT // width)
    cmds = []
    z = z0
    while z <= z1:
        z_end = min(z1, z + rows_per_cmd - 1)
        cmds.append(f"fill {x0} {y} {z} {x1} {y} {z_end} {block}")
        z = z_end + 1
    return cmds


def _hopper_load(x0: int, z0: int, x1: int, z1: int, layers: int) -> list[str]:
    """Planes of hoppers, which is the densest per-command source of block-entity tick work.

    Every hopper block entity runs its transfer logic each tick; Paper's hopper options here
    (`cooldown-when-full`, `disable-move-event`) do not skip idle hoppers, so the tick cost is paid
    per hopper regardless of contents. Hoppers all face one direction so any items that do enter
    flow along the plane and keep transfer work alive rather than settling immediately.
    """
    cmds = []
    for layer in range(layers):
        y = -59 + (layer * 2)
        cmds += _fill(x0, z0, x1, z1, y, "minecraft:hopper[facing=east]")
        # A chest at the end of each plane gives the conveyor somewhere to deliver, so transfers
        # actually complete instead of erroring against a wall.
        cmds.append(f"setblock {x1} {y} {z0} minecraft:chest")
    return cmds


def _redstone_load(x0: int, z0: int, x1: int, z1: int, layers: int) -> list[str]:
    """Redstone planes driven by torches, to exercise the real block-update pipeline.

    Redstone wire propagation is block-update work rather than block-entity work, so this stresses a
    different part of the tick than the hopper workload.
    """
    cmds = []
    for layer in range(layers):
        y = -59 + (layer * 3)
        cmds += _fill(x0, z0, x1, z1, y - 1, "minecraft:stone")
        cmds += _fill(x0, z0, x1, z1, y, "minecraft:redstone_wire")
        # Torch/repeater pairs spaced along the plane act as clocks that keep the wire updating.
        for i, x in enumerate(range(x0, x1 + 1, 12)):
            for z in range(z0, z1 + 1, 12):
                cmds.append(f"setblock {x} {y - 1} {z} minecraft:redstone_torch")
                cmds.append(f"setblock {x} {y} {z} minecraft:repeater[facing=east,delay=1]")
    return cmds


def build_setup_commands(cfg: BenchConfig) -> list[str]:
    """Deterministic world setup. Same seed and config always produces the same commands."""
    rng = random.Random(cfg.seed)
    # Gamerule identifiers are snake_case in this Minecraft version (advance_weather, spawn_mobs,
    # ...), NOT the historical camelCase (doWeatherCycle, doMobSpawning). Sending the old names fails
    # silently as far as the run is concerned - the console prints "Incorrect argument for command"
    # and the workload then runs with natural mob spawning still enabled, which quietly destroys
    # determinism. Names here are taken from net.minecraft.world.level.gamerules.GameRules.
    cmds: list[str] = [
        # Remove every source of nondeterminism we can: no day/weather cycle, no random ticks moving
        # blocks around, no natural spawning competing with our own population, no mob griefing.
        "gamerule advance_time false",
        "gamerule advance_weather false",
        f"gamerule random_tick_speed {cfg.random_tick_speed}",
        "gamerule spawn_mobs false",
        "gamerule spawn_monsters false",
        "gamerule spawn_patrols false",
        "gamerule spawn_phantoms false",
        "gamerule spawn_wandering_traders false",
        "gamerule mob_drops false",
        "gamerule block_drops false",
        "gamerule mob_griefing false",
        "gamerule raids false",
        "gamerule tnt_explodes false",
        "gamerule send_command_feedback true",
        "time set noon",
        "weather clear",
        "difficulty normal",  # peaceful would despawn hostile mobs and change AI behaviour
    ]

    return cmds


def build_forceload_commands(cfg: BenchConfig) -> list[str]:
    """Forceload each cluster. Forceload is what keeps chunks ticking with no player online, and is
    the whole reason this harness can work without clients.

    These MUST complete - and the chunks MUST actually finish loading - before any content command
    runs, or every fill and summon is rejected with "That position is not loaded" and the run
    silently measures an empty world.
    """
    cmds = []
    for (ox, oz) in region_origins(cfg):
        x0, z0 = ox, oz
        x1, z1 = ox + cfg.chunks_per_region - 1, oz + cfg.chunks_per_region - 1
        cmds.append(f"forceload add {x0 * 16} {z0 * 16} {x1 * 16 + 15} {z1 * 16 + 15}")
    return cmds


def build_content_commands(cfg: BenchConfig) -> list[str]:
    """Entity and block workload. Only safe to run once the forceloaded chunks are loaded."""
    rng = random.Random(cfg.seed)
    cmds: list[str] = []
    mob = WORKLOAD_MOBS.get(cfg.workload, "minecraft:cow")
    entity_total = cfg.entity_count()

    for (ox, oz) in region_origins(cfg):
        x0, z0 = ox, oz
        x1, z1 = ox + cfg.chunks_per_region - 1, oz + cfg.chunks_per_region - 1

        bx0, bz0 = x0 * 16, z0 * 16
        bx1, bz1 = x1 * 16 + 15, z1 * 16 + 15

        if cfg.workload in ("entity", "mixed"):
            for _ in range(entity_total):
                ex = rng.randint(bx0, bx1)
                ez = rng.randint(bz0, bz1)
                # Summon onto solid ground so the mob settles and ticks AI normally instead of
                # falling forever.
                cmds.append(f"summon {mob} {ex} -59 {ez}")

        if cfg.workload in ("hopper", "mixed"):
            cmds += _hopper_load(bx0, bz0, bx1, bz1, cfg.block_layers)

        if cfg.workload in ("redstone", "mixed"):
            cmds += _redstone_load(bx0, bz0, bx1, bz1, max(1, cfg.block_layers // 2))

    return cmds


# --------------------------------------------------------------------------------------------------
# Sampling
# --------------------------------------------------------------------------------------------------

KV = re.compile(r"(\w+)=([^\s]+)")


def parse_bench_lines(lines: list[str]) -> dict:
    """Parses `SILKBENCH` output into structured data."""
    out: dict = {"global": None, "summary": None, "regions": []}
    for line in lines:
        idx = line.find("SILKBENCH ")
        if idx < 0:
            continue
        body = line[idx + len("SILKBENCH "):]
        # strip ANSI colour if the console emitted any
        body = re.sub(r"\x1b\[[0-9;]*m", "", body)
        parts = body.split(None, 1)
        if len(parts) < 2:
            continue
        kind, rest = parts[0], parts[1]
        fields = {}
        for k, v in KV.findall(rest):
            try:
                fields[k] = float(v) if ("." in v or v.replace("-", "").isdigit()) else v
            except ValueError:
                fields[k] = v
        if kind == "global":
            out["global"] = fields
        elif kind == "summary":
            out["summary"] = fields
        elif kind == "region":
            out["regions"].append(fields)
    return out


@dataclass
class RunResult:
    config: dict
    samples: list = field(default_factory=list)
    setup_ok: bool = False
    chunks_loaded: int = 0
    blocks_changed: int = 0
    notes: list = field(default_factory=list)

    def aggregate(self) -> dict:
        """Median across samples; per-region figures are aggregated across regions first."""
        if not self.samples:
            return {}

        def med(vals):
            vals = [v for v in vals if v is not None]
            return round(statistics.median(vals), 3) if vals else None

        g = [s["global"] for s in self.samples if s.get("global")]
        summ = [s["summary"] for s in self.samples if s.get("summary")]

        region_avg, region_p95, region_p99, region_worst, region_util = [], [], [], [], []
        region_tps = []
        for s in self.samples:
            regs = [r for r in s.get("regions", []) if r.get("ticks", 0)]
            if not regs:
                continue
            # With N regions ticking in parallel the slowest one bounds perceived server health, so the
            # worst region is the figure of interest. Pick that region ONCE per sample by average MSPT
            # and read every statistic off it. Taking max() per statistic independently would let the
            # avg, p95 and p99 come from different regions, which produces incoherent rows - p95 above
            # p99, for instance - and describes no region that actually exists.
            worst_region = max(regs, key=lambda r: r.get("avg", 0.0))
            region_avg.append(worst_region.get("avg"))
            region_tps.append(min(r.get("tps", 20.0) for r in regs))
            region_p95.append(worst_region.get("p95"))
            region_p99.append(worst_region.get("p99"))
            region_worst.append(worst_region.get("worst"))
            # Summed utilisation across regions approximates how many tick threads' worth of work the
            # server is actually doing: 1.0 == one thread saturated.
            region_util.append(sum(r.get("util", 0.0) for r in regs))

        return {
            "global_avg_mspt": med([x.get("avg") for x in g]),
            "global_worst5pct_mspt": med([x.get("p95") for x in g]),
            "global_worst1pct_mspt": med([x.get("p99") for x in g]),
            "global_worst_mspt": med([x.get("worst") for x in g]),
            "global_util": med([x.get("util") for x in g]),
            "global_tps": med([x.get("tps") for x in g]),
            "min_region_tps": med(region_tps),
            "worst_region_avg_mspt": med(region_avg),
            "worst_region_worst5pct_mspt": med(region_p95),
            "worst_region_worst1pct_mspt": med(region_p99),
            "worst_region_worst_mspt": med(region_worst),
            "summed_region_util": med(region_util),
            "regions": med([x.get("regions") for x in summ]),
            "active_regions": med([x.get("activeRegions") for x in summ]),
            "tick_threads": med([x.get("tickThreads") for x in summ]),
            "chunks": med([x.get("chunks") for x in summ]),
            "entities": med([x.get("entities") for x in summ]),
            "heap_used_mb": med([x.get("heapUsedMB") for x in summ]),
            "samples": len(self.samples),
        }


# --------------------------------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------------------------------


def write_server_config(run_dir: Path, cfg: BenchConfig) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    (run_dir / "server.properties").write_text(
        "level-type=minecraft:flat\n"
        "online-mode=false\n"
        "max-players=20\n"
        "view-distance=10\n"
        "simulation-distance=10\n"
        "spawn-protection=0\n"
        f"level-seed={cfg.seed}\n"
        "sync-chunk-writes=false\n",
        encoding="utf-8",
    )
    # paper-global.yml carries the region-threading knobs. Written fresh each run so the matrix
    # controls them explicitly rather than inheriting whatever a previous run left behind.
    cfgdir = run_dir / "config"
    cfgdir.mkdir(exist_ok=True)
    (cfgdir / "paper-global.yml").write_text(
        "_version: 30\n"
        "threaded-regions:\n"
        f"  threads: {cfg.threads}\n"
        f"  grid-exponent: {cfg.grid_exponent}\n"
        f"  scheduler: {cfg.scheduler}\n",
        encoding="utf-8",
    )


def run_once(jar: Path, java: str, cfg: BenchConfig, run_dir: Path, rep: int) -> RunResult:
    result = RunResult(config=asdict(cfg))
    if run_dir.exists():
        shutil.rmtree(run_dir, ignore_errors=True)
    write_server_config(run_dir, cfg)

    jfr = (run_dir / "recording.jfr") if cfg.jfr else None
    server = ServerProcess(jar, run_dir, cfg.heap, jfr)
    server.start(java)
    try:
        if not server.wait_ready():
            result.notes.append("server did not reach ready state")
            return result

        # Phase 1: gamerules and world settings.
        for cmd in build_setup_commands(cfg):
            server.send(cmd)
            time.sleep(0.01)
        time.sleep(1)
        gamerule_errors = [l for l in server.drain() if "Incorrect argument" in l or "Unknown or incomplete" in l]
        if gamerule_errors:
            result.notes.append(f"{len(gamerule_errors)} setup commands rejected by the server")

        # Phase 2: forceload, then WAIT for the chunks to actually load. Skipping this wait makes
        # every content command fail with "That position is not loaded", and the run then measures an
        # empty world while still reporting plausible-looking MSPT.
        for cmd in build_forceload_commands(cfg):
            server.send(cmd)
            time.sleep(0.05)

        expected_chunks = cfg.regions * (cfg.chunks_per_region ** 2)
        loaded = 0
        for _ in range(60):
            time.sleep(2)
            server.drain()
            server.send("silkmc bench")
            snap = parse_bench_lines(server.collect("SILKBENCH"))
            summary = snap.get("summary") or {}
            loaded = int(summary.get("chunks", 0))
            if loaded >= expected_chunks:
                break
        result.chunks_loaded = loaded
        if loaded < expected_chunks:
            result.notes.append(f"only {loaded}/{expected_chunks} chunks loaded before content setup")

        # Phase 3: content. Verify it actually landed rather than assuming.
        server.drain()
        content = build_content_commands(cfg)
        for cmd in content:
            server.send(cmd)
            time.sleep(0.004)
        time.sleep(3)
        responses = server.drain()
        not_loaded = sum(1 for l in responses if "not loaded" in l)
        if not_loaded:
            result.notes.append(f"{not_loaded} content commands hit unloaded chunks")
        # /fill reports "filled N block(s)"; /setblock reports "Changed the block at x, y, z".
        # Counting both is the only direct confirmation that the workload actually landed - MSPT alone
        # cannot distinguish "workload placed" from "workload silently rejected".
        result.blocks_changed = sum(
            int(m.group(1).replace(",", ""))
            for l in responses
            for m in [re.search(r"filled ([\d,]+) block", l)] if m
        ) + sum(1 for l in responses if "Changed the block at" in l)
        result.setup_ok = not_loaded == 0 and loaded >= expected_chunks

        time.sleep(5)
        server.drain()

        print(f"      warmup {cfg.warmup_seconds}s...", flush=True)
        time.sleep(cfg.warmup_seconds)

        deadline = time.time() + cfg.measure_seconds
        while time.time() < deadline:
            server.drain()
            server.send("silkmc bench")
            lines = server.collect("SILKBENCH")
            parsed = parse_bench_lines(lines)
            if parsed.get("summary"):
                result.samples.append(parsed)
            time.sleep(cfg.sample_interval_seconds)
    finally:
        server.stop()
        server.save_log(run_dir.parent / f"{run_dir.name}-rep{rep}.log")
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="SilkMC region workload benchmark")
    ap.add_argument("--jar", required=True, type=Path)
    ap.add_argument("--java", default="java")
    ap.add_argument("--out", type=Path, default=Path("bench-results"))
    ap.add_argument("--regions", type=int, default=4)
    ap.add_argument("--chunks-per-region", type=int, default=4)
    ap.add_argument("--entities-per-region", type=int, default=80)
    ap.add_argument("--density", choices=sorted(DENSITIES))
    ap.add_argument("--workload", choices=["entity", "hopper", "redstone", "mixed"], default="entity")
    ap.add_argument("--block-layers", type=int, default=1,
                    help="planes of ticking blocks (hoppers/redstone) per region")
    ap.add_argument("--random-tick-speed", type=int, default=0,
                    help="0 keeps runs deterministic; raising it adds block-tick load")
    ap.add_argument("--region-spacing-chunks", type=int, default=96)
    ap.add_argument("--warmup", type=int, default=120)
    ap.add_argument("--measure", type=int, default=180)
    ap.add_argument("--sample-interval", type=int, default=15)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--heap", default="4G")
    ap.add_argument("--jfr", action="store_true")
    ap.add_argument("--threads", type=int, nargs="+", default=[-1])
    ap.add_argument("--schedulers", nargs="+", default=["EDF"])
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    matrix = []
    for scheduler in args.schedulers:
        for threads in args.threads:
            cfg = BenchConfig(
                regions=args.regions,
                chunks_per_region=args.chunks_per_region,
                entities_per_region=args.entities_per_region,
                density=args.density,
                workload=args.workload,
                block_layers=args.block_layers,
                random_tick_speed=args.random_tick_speed,
                region_spacing_chunks=args.region_spacing_chunks,
                warmup_seconds=args.warmup,
                measure_seconds=args.measure,
                sample_interval_seconds=args.sample_interval,
                repetitions=args.reps,
                seed=args.seed,
                threads=threads,
                scheduler=scheduler,
                heap=args.heap,
                jfr=args.jfr,
            )
            matrix.append(cfg)

    all_results = []
    for cfg in matrix:
        label = f"{cfg.scheduler}-t{cfg.threads}"
        print(f"[{label}] regions={cfg.regions} entities/region={cfg.entity_count()} "
              f"workload={cfg.workload}", flush=True)
        reps = []
        for rep in range(cfg.repetitions):
            print(f"   rep {rep + 1}/{cfg.repetitions}", flush=True)
            run_dir = args.out / f"run-{label}-rep{rep}"
            res = run_once(args.jar, args.java, cfg, run_dir, rep)
            print(f"      setup_ok={res.setup_ok} chunks={res.chunks_loaded} "
                  f"blocksChanged={res.blocks_changed}"
                  + (f" NOTES: {'; '.join(res.notes)}" if res.notes else ""), flush=True)
            agg = res.aggregate()
            if agg:
                reps.append(agg)
            else:
                print(f"      no samples ({'; '.join(res.notes) or 'unknown'})", flush=True)

        if reps:
            merged = {}
            for key in reps[0]:
                vals = [r[key] for r in reps if r.get(key) is not None]
                merged[key] = round(statistics.median(vals), 3) if vals else None
            merged["scheduler"] = cfg.scheduler
            merged["threads_requested"] = cfg.threads
            merged["entities_per_region"] = cfg.entity_count()
            merged["regions_requested"] = cfg.regions
            merged["workload"] = cfg.workload
            merged["reps"] = len(reps)
            all_results.append(merged)
            print(f"   -> minTPS={merged.get('min_region_tps')} worst-region avg={merged.get('worst_region_avg_mspt')}ms "
                  f"worst1%={merged.get('worst_region_worst1pct_mspt')}ms "
                  f"global avg={merged.get('global_avg_mspt')}ms "
                  f"regions={merged.get('regions')} threads={merged.get('tick_threads')}", flush=True)

    (args.out / "results.json").write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    print(f"\nWrote {args.out / 'results.json'}")
    print_table(all_results)
    return 0


def print_table(rows: list[dict]) -> None:
    if not rows:
        print("no results")
        return
    # TPS first: it is what says whether the server kept up. A row with a flattering MSPT and a TPS
    # below 20 is a saturated server skipping ticks, not a fast one.
    hdr = ["Scheduler", "Thr", "Rgn", "minTPS", "WorstRgn avg", "worst5%", "worst1%", "maxTick",
           "Global avg", "SumUtil", "HeapMB"]
    print("\n| " + " | ".join(hdr) + " |")
    print("|" + "|".join(["---"] * len(hdr)) + "|")
    for r in rows:
        print("| " + " | ".join(str(x) for x in [
            r.get("scheduler"), r.get("tick_threads"), r.get("regions"), r.get("min_region_tps"),
            r.get("worst_region_avg_mspt"), r.get("worst_region_worst5pct_mspt"),
            r.get("worst_region_worst1pct_mspt"), r.get("worst_region_worst_mspt"), r.get("global_avg_mspt"),
            r.get("summed_region_util"), r.get("heap_used_mb"),
        ]) + " |")


if __name__ == "__main__":
    sys.exit(main())
