"""Назначение платежа для платёжного поручения по позициям счёта поставщика.
Правило: раздел продукции стоит в начале названия — берём покрытие, названное раньше всех; сопутствующее (подложка, клей…) идёт после основного."""
import re

FLOOR = [   # покрытия: (регулярка по названию, как писать в «за …»); при равной позиции в названии побеждает более ранняя строка списка
    (r"инженерн\w+\s+доск|engineered", "инженерную доску"),
    (r"паркетн\w+\s+доск", "паркетную доску"),
    (r"массивн\w+\s+доск", "массивную доску"),
    (r"террасн\w+\s+доск|декинг", "террасную доску"),
    (r"модульн\w+\s+паркет", "модульный паркет"),
    (r"штучн\w+\s+паркет", "штучный паркет"),
    (r"кварц\w*\s+ламинат", "кварцевый ламинат"),
    (r"кварц\w*\s+паркет", "кварцевый паркет"),
    (r"\bspc\b|\blvt\b|кварц\w*[\s\-]*винил|плитк\w+\s+пвх|пвх[\s\-]*покрыт|винил|каменно-полимер", "виниловое покрытие"),
    (r"ламинат", "ламинат"),
    (r"паркет", "паркет"),
    (r"ковролин|ковер|ковёр|ковры", "ковровые покрытия"),
]
ACCESS = [   # сопутствующее: подложка, клей, плинтус…
    (r"подложк", "подложку"),
    (r"клей|герметик|шпатл", "клей"),
    (r"грунт|праймер|primer", "грунт"),
    (r"\bлак|лак\b", "лак"),
    (r"масл|воск", "масло"),
    (r"плинтус", "плинтус"),
    (r"порог|профил", "порожки и профили"),
]


def categories(names):
    """Категории по названиям позиций в порядке появления: сначала покрытия, потом сопутствующее; подложка — последней."""
    main, extra = [], []
    for name in names:
        name = (name or "").lower()
        label = next((lab for rx, lab in ACCESS if re.match(r"\W*(?:\d+[\w\-]*\s+)?(?:" + rx + ")", name)), None)   # название начинается с сопутствующего
        target = extra
        if label is None:
            hits = [(m.start(), i, lab) for i, (rx, lab) in enumerate(FLOOR) for m in [re.search(rx, name)] if m]
            label = min(hits)[2] if hits else None
            target = main
        if label is None:
            label = next((lab for rx, lab in ACCESS if re.search(rx, name)), None)
            target = extra
        if label and label not in main + extra:
            target.append(label)
    return main + [c for c in extra if c != "подложку"] + (["подложку"] if "подложку" in extra else [])


def purpose(number: str, date: str, names, vat: float = 0.0, vat_rate: float = 0.0) -> str:
    """«Оплата по счету № 123 от 01.01.2026 за ламинат и подложку. В т.ч. НДС 22% - 1000.00 руб.»"""
    cats = categories(names)
    what = (", ".join(cats[:-1]) + " и " + cats[-1] if len(cats) > 1 else cats[0]) if cats else ""
    nds = (f"В т.ч. НДС {vat_rate:g}% - {vat:.2f} руб." if vat_rate else f"В т.ч. НДС - {vat:.2f} руб.") if vat else "Без НДС"
    return (f"Оплата по счету № {number}" + (f" от {date}" if date else "") + (f" за {what}" if what else "") + f". {nds}")[:210]
