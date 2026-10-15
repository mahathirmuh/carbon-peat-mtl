"""Simulate the PLAN.md split rule to show why block_size_m must be a multiple of the patch size.

Rule (PLAN.md, Fase 4): blocks are shuffled into splits; a patch takes the split of the block that holds
its centre and is dropped if it also overlaps a block of another split.
Writes outputs/metrics/block_alignment.json.

Usage: python scripts/check_block_alignment.py [--config config/config.yaml] [--seeds 20]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # lets `python scripts/check_block_alignment.py` import src/

from src.config import DEFAULT_CONFIG, load_config  # noqa: E402

ORIGINAL_BLOCK_M = 5000  # PLAN.md default before Fase 0, kept for comparison


def assign_blocks(n_blocks: int, ratios: list[float], rng: random.Random) -> list[int]:
    """Shuffle block ids and cut them into consecutive splits; returns the split index of each block."""
    order = list(range(n_blocks))
    rng.shuffle(order)
    split = [0] * n_blocks
    start = 0
    for k, ratio in enumerate(ratios):
        end = n_blocks if k == len(ratios) - 1 else start + round(ratio * n_blocks)
        for block in order[start:end]:
            split[block] = k
        start = end
    return split


def simulate(width_px: int, height_px: int, patch_px: int, block_px: int,
             ratios: list[float], seeds: int = 20) -> dict:
    """Fraction of non-overlapping patches dropped by the split rule, averaged over random block assignments."""
    n_cols = -(-width_px // block_px)
    n_rows = -(-height_px // block_px)
    kept = [0] * len(ratios)
    total = [0] * len(ratios)
    for seed in range(seeds):
        split = assign_blocks(n_cols * n_rows, ratios, random.Random(seed))
        for y in range(0, height_px - patch_px + 1, patch_px):
            for x in range(0, width_px - patch_px + 1, patch_px):
                cx, cy = x + patch_px // 2, y + patch_px // 2
                s = split[(cy // block_px) * n_cols + cx // block_px]
                cols = {x // block_px, (x + patch_px - 1) // block_px}
                rows = {y // block_px, (y + patch_px - 1) // block_px}
                total[s] += 1
                kept[s] += all(split[r * n_cols + c] == s for c in cols for r in rows)
    n_kept = sum(kept)
    return {
        "dropped_fraction": round(1 - n_kept / sum(total), 4),
        "kept_fraction_per_split": [round(k / t, 4) if t else None for k, t in zip(kept, total)],
        "effective_ratios": [round(k / n_kept, 4) if n_kept else None for k in kept],
    }


def aoi_size_px(cfg: dict) -> tuple[int, int]:
    """Width and height of the AOI bounding box on the working grid (crs, scale)."""
    from rasterio.warp import transform_bounds

    left, bottom, right, top = transform_bounds("EPSG:4326", cfg["crs"], *cfg["aoi_bbox"])
    return int((right - left) // cfg["scale"]), int((top - bottom) // cfg["scale"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Simulate patch loss for unaligned vs aligned blocks.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--seeds", type=int, default=20)
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    width, height = aoi_size_px(cfg)
    patch = cfg["patch_size"]
    split_ratios = [cfg["split_ratios"][s] for s in ("train", "val", "test")]
    result = {"aoi_px": [width, height], "patch_px": patch, "seeds": args.seeds, "scenarios": []}

    for block_m in (ORIGINAL_BLOCK_M, cfg["block_size_m"]):
        for name, ratios in (("train_val_test", split_ratios), ("10_fold", [0.1] * 10)):
            stats = simulate(width, height, patch, block_m // cfg["scale"], ratios, args.seeds)
            result["scenarios"].append({"block_size_m": block_m, "splits": name, **stats})
            print(f"block {block_m} m, {name:<14} dropped {stats['dropped_fraction']:6.1%}  "
                  f"kept per split {stats['kept_fraction_per_split'][:3]}  "
                  f"effective ratios {stats['effective_ratios'][:3]}")

    out = ROOT / "outputs" / "metrics" / "block_alignment.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"AOI {width} x {height} px; saved {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
