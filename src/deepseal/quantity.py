"""Расчёт количества товара для счёта и КП: кратно упаковкам, запас на подрезку, шаг 0,5 шт для отдельных позиций."""
import math


def round_packs(x: float) -> int:
    """Округление числа упаковок: дробная часть до 0,09 — вниз (допуск на погрешность), больше — вверх. Минимум одна упаковка."""
    x = round(x, 2)
    n = math.floor(x + 1e-9)
    frac = round(x - n, 2)
    return max(1, n if frac <= 0.09 else n + 1)


def area_to_packs(net_area: float, pack_area: float, cut_percent: float = 0.0) -> dict:
    """Чистая площадь → упаковки с запасом на подрезку.
    Пример: 21,35 кв.м, упаковка 1,86 кв.м, запас 5% → 22,42 кв.м → 12 упаковок = 22,32 кв.м (округление терпит 0,09 уп.)."""
    if net_area <= 0 or pack_area <= 0:
        raise ValueError("площадь и площадь упаковки должны быть положительными")
    with_cut = net_area * (1 + cut_percent / 100.0)
    packs = round_packs(with_cut / pack_area)
    return {"area_with_cut": round(with_cut, 2), "packs": packs, "qty": round(packs * pack_area, 3)}


def half_step(qty: float) -> float:
    """Количество кратно 0,5 шт (например, клей в мешках по 14 кг, который продают половинками): 2,3 → 2,5; минимум 0,5."""
    return max(0.5, math.ceil(qty * 2 - 1e-9) / 2)


def discounted(price: float, percent: float) -> float:
    return round(price * (1 - percent / 100.0), 2)
