"""Собирает примеры КП из вымышленных данных: python examples/make_demo_kp.py → папка output/."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from deepseal import kp_pdf  # noqa: E402
from deepseal.quantity import area_to_packs, discounted  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "output")
SPECS = {"Класс нагрузки": "33", "Размер, мм": "1380x190x8", "Толщина, мм": "8", "Фаска": "4 стороны", "Гарантия": "25 лет", "Площадь упаковки, м2": "2,69"}


PHOTOS = os.path.join(os.path.dirname(__file__), "photos")


def real(name):
    with open(os.path.join(PHOTOS, name + ".jpg"), "rb") as f:
        return f.read()


def item(title, photos, pack=2.69, specs=SPECS):
    return {"title": title, "specs": specs, "pack_area": pack, "images": [real(n) for n in photos]}


def row(i, name, area, price, unit="м2"):
    qty = f"{area:g} м2".replace(".", ",") if unit == "м2" else f"{area:g} шт."
    return [i, name, unit, area, "", price, qty, round(area * price)]


def build(name, items, rows, **extra):
    discs = extra.get("discs", {})                                 # скидка на позицию (индекс строки → %)
    total = round(sum(r[7] * (1 - discs.get(k, 0) / 100) for k, r in enumerate(rows) if r[1]))
    rows = rows + [["", "", "", "", "", "", "Итого:", total]]
    ctx = {"number": "ДЕМО-101", "date": "26.10.2026", "company": "Demo Floors LLC", "items": items, "main": set(range(len(items))), "rows": rows,
           "pos_text": "", "delivery_text": "Срок поставки: 5 рабочих дней", "extra_lines": [], "manager": "Иван Петров", "phone": "+7 (900) 111-22-33", **extra}
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    with open(path, "wb") as f:
        f.write(kp_pdf.render(ctx))
    print("готово:", path)


if __name__ == "__main__":
    pk = area_to_packs(21.35, 2.69, 5)                 # чистая площадь 21,35 кв.м с запасом 5% → целые упаковки
    a = item("Инженерная доска Demo Oak Rustic, 1900x190x15 мм, 2,69 м2/уп", ["oak_plank"],
             specs={"Материал": "Дуб", "Размер, мм": "1900x190x15", "Селекция": "рустик", "Покрытие": "масло", "Фаска": "4 стороны", "Площадь упаковки, м2": "2,69"})
    b = item("Паркетная доска Demo Ёлка Natur, 600x120x14 мм, 2,2 м2/уп", ["herringbone", "herringbone_interior"], 2.2,
             specs={"Материал": "Дуб", "Размер, мм": "600x120x14", "Укладка": "английская ёлка", "Покрытие": "лак", "Площадь упаковки, м2": "2,2"})
    glue = {"title": "Клей для паркета Demo Bond 14 кг", "specs": {}, "images": []}
    build("kp_single.pdf", [a], [row(1, a["title"], pk["qty"], 4890)])
    build("kp_multi.pdf", [a, b, glue], [row(1, a["title"], pk["qty"], 4890), row(2, b["title"], 17.6, 5650), row(3, glue["title"], 2, 6400, "шт"),
                                         ["", "Доставка", "", 1, "", 2500, "", 2500]])
    build("kp_discount.pdf", [a], [row(1, a["title"], pk["qty"], 4890)], discs={0: 10.0}, disc_pct=True)
    build("kp_no_total.pdf", [a, b], [row(1, a["title"], pk["qty"], 4890), row(2, b["title"], 17.6, 5650)], no_total=True,
          item_terms={0: "3-5 календарных дней", 1: "в наличии"}, item_cmts={0: "Цена действует до конца месяца"}, delivery_text="")
    print("скидка 10% на 4890 =", discounted(4890, 10))
