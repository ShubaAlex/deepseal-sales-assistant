import pytest

from deepseal.quantity import area_to_packs, discounted, half_step, round_packs


def test_round_packs_tolerance():
    assert round_packs(11.09) == 11       # дробная часть до 0,09 — вниз
    assert round_packs(11.10) == 12
    assert round_packs(0.3) == 1          # минимум одна упаковка


def test_area_to_packs():
    r = area_to_packs(21.35, 1.86, 5)
    assert r["packs"] == 12 and r["qty"] == pytest.approx(22.32)


def test_area_validation():
    with pytest.raises(ValueError):
        area_to_packs(0, 1.86)


@pytest.mark.parametrize("q,expected", [(2.3, 2.5), (2.5, 2.5), (2.51, 3.0), (0.1, 0.5), (1, 1)])
def test_half_step(q, expected):
    assert half_step(q) == expected


def test_discount():
    assert discounted(8488, 10) == 7639.2
