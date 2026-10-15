from scripts.check_block_alignment import simulate

RATIOS = [0.70, 0.15, 0.15]


def test_aligned_blocks_drop_no_patches():
    stats = simulate(2048, 2048, patch_px=256, block_px=512, ratios=RATIOS, seeds=3)
    assert stats["dropped_fraction"] == 0


def test_unaligned_blocks_drop_patches():
    stats = simulate(2048, 2048, patch_px=256, block_px=500, ratios=RATIOS, seeds=3)
    assert stats["dropped_fraction"] > 0
