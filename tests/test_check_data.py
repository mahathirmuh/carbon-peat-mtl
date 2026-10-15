from gee.check_data import compare_to_reference, count_distribution


def test_compare_to_reference():
    diff = compare_to_reference({"a": 110, "b": None}, {"a": 100, "b": 5})
    assert diff == {"a": 0.1, "b": None}


def test_count_distribution():
    stats = count_distribution([0, 0, 5, 10])
    assert stats["n_cells"] == 4
    assert stats["share_with_gedi"] == 0.5
    assert stats["max"] == 10


def test_count_distribution_empty():
    assert count_distribution([]) == {"n_cells": 0}
