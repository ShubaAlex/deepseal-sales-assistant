"""Генератор коммерческого предложения (КП) в PDF: страница рисуется прямо в reportlab, без шаблонов и офисных программ.
Раскладки: один товар («герой» с фото), несколько товаров (таблица), режим «без общей суммы» (отдельная таблица на каждую позицию).
Всё всегда помещается на одну страницу: масштаб шапки, фото и шрифтов подбирается ступенями."""
import io
import os
import re

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image as RLImage
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Flowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
pdfmetrics.registerFont(TTFont("KP", os.path.join(ASSETS, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("KP-B", os.path.join(ASSETS, "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFontFamily("KP", normal="KP", bold="KP-B", italic="KP", boldItalic="KP-B")

# Реквизиты и подписи бренда — демо-значения; в рабочей версии подставляются данные компании
BRAND = {"phone": "+7 (900) 000-00-00", "email": "info@example.com", "telegram": "@demo_company", "whatsapp_url": "https://wa.me/79000000000",
         "max_url": "https://max.ru/", "site": "example.com", "team": "Demo Floors"}

GOLD = colors.HexColor("#E3B724")
INK = colors.HexColor("#1F2328")
GREY = colors.HexColor("#6B7280")
LINE = colors.HexColor("#D9DCE1")
HEAD_BG = colors.HexColor("#EEF0F3")
W, H = A4
M = 40
CONTENT_W = W - 2 * M

UK_HEAD = "Закажите укладку вместе с покрытием"           # блок «Укладка» в жёлтой рамке рядом с контактами
UK_BODY = ("Мы доверяем укладку только проверенным мастерам. Все работы выполняются по технологии и с гарантией, "
           "а стоимость и сроки согласовываются заранее.")
COVERINGS = ("ламинат", "spc", "кварц", "винил", "пвх")                       # ламинат и «виниловые» покрытия
WOODS = ("доска", "паркет")                                                    # паркетная, инженерная, массивная доска, модульный паркет
SPEC_SETS = {"cov": ["Класс", "Размер", "Толщина", "Фаска", "Гарантия"], "wood": ["Размер", "Толщина", "Покрытие"], "other": ["Размер", "Толщина"]}


def kind_of(title):
    t = (title or "").lower()
    if any(w in t for w in WOODS) and "ламинат" not in t:
        return "wood"
    if any(w in t for w in COVERINGS):
        return "cov"
    return "other"


def pick_specs(title, specs, pack_area=None):
    """Нужные характеристики по типу товара + площадь упаковки: [(подпись, значение)]."""
    out = {}
    for k, v in (specs or {}).items():
        label = re.sub(r"\s+", " ", k.split("?")[0]).strip().replace(" ,", ",")
        value = re.sub(r"\s+", " ", str(v)).strip()
        if label and value and value != "?":
            out[label] = value
    res = []
    for want in SPEC_SETS[kind_of(title)]:
        for label, value in out.items():
            base = label.split(",")[0].strip()
            if base == want or (want == "Класс" and base.startswith("Класс")):
                if label.endswith(", мм") and not value.endswith("мм"):
                    value += " мм"
                res.append((want, value if len(value) <= 34 else value[:33] + "…"))
                break
    area = next((v for k, v in out.items() if k.startswith("Площадь упаковки")), None)
    if area is None and pack_area:
        area = f"{pack_area:g}".replace(".", ",")
    if area:
        res.append(("Площадь упаковки", f"{area} м²"))
    return res


def _sq(img_bytes, px=None):
    im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    w, h = im.size
    s = min(w, h)
    im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
    if px and s < px:
        im = im.resize((px, px), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=92)
    buf.seek(0)
    return buf


class PhotoBox(Flowable):
    """Главное фото (квадрат) и вторая картинка уменьшенной в правом нижнем углу — как в образце."""
    def __init__(self, main, thumb, size):
        super().__init__()
        self.main = ImageReader(_sq(main)) if main else None
        self.thumb = ImageReader(_sq(thumb, 240)) if thumb and main else None
        self.size = size

    def wrap(self, aw, ah):
        return self.size, self.size

    def draw(self):
        c, sz = self.canv, self.size
        if self.main:
            c.drawImage(self.main, 0, 0, sz, sz)
        if self.thumb:
            t = sz * 0.46
            c.setFillColor(colors.white)
            c.rect(sz - t - 2, -2, t + 4, t + 4, stroke=0, fill=1)
            c.drawImage(self.thumb, sz - t, 0, t, t)


class Icon(Flowable):
    """Логотип/ярлычок из файла (assets/ic_*.png), прижатый к правому краю колонки шириной col_w."""
    def __init__(self, kind, size, col_w=None):
        super().__init__()
        self.img = ImageReader(os.path.join(ASSETS, f"ic_{kind}.png"))
        self.size, self.col_w = size, col_w or size

    def wrap(self, aw, ah):
        return self.col_w, self.size

    def draw(self):
        self.canv.drawImage(self.img, self.col_w - self.size, 0, self.size, self.size, mask="auto", preserveAspectRatio=True)


def _logo(width):
    im = Image.open(os.path.join(ASSETS, "logo.png")).convert("RGB")
    w, h = im.size
    im = im.crop((0, int(h * 0.09), w, int(h * 0.92)))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    buf.seek(0)
    return RLImage(buf, width=width, height=width * im.size[1] / im.size[0])


BADGE = ("#B07A12", True)      # цвет и жирность метки «-10%» рядом со старой ценой


def _pc(v, d, S, badge=False):
    """Цена/сумма: без скидки — как есть; со скидкой — старая тёмно-серая с тонкой светлой чертой (и меткой «-10%» у цены), ниже новая жирным."""
    if not d:
        return Paragraph(money(v), S["cellc"])
    fs = S["cellc"].fontSize
    old = f'<strike color="#C4C8CE" width="0.5"><font color="#6B7280" size="{fs * 0.88:.1f}">{money(v)}</font></strike>'
    if badge:
        col, bold = BADGE
        tag = f'<font color="{col}" size="{fs * 0.8:.1f}">{"<b>" if bold else ""}-{d:g}%{"</b>" if bold else ""}</font>'
        old += " " + tag
    return [Paragraph(old, S["cellc"]), Paragraph(f"<b>{money(v * (1 - d / 100.0))}</b>", S["cellc"])]


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def money(v):
    return f"{round(float(v)):,}".replace(",", " ") + " руб."


def _qty(t):
    return str(t or "").replace("м2", "м²")


def styles(k):
    def st(name, **kw):
        base = dict(fontName="KP", fontSize=10 * k, leading=13 * k, textColor=INK)
        base.update(kw)
        return ParagraphStyle(name, **base)
    return {
        "title": st("t", fontName="KP-B", fontSize=19 * k, leading=23 * k, alignment=TA_CENTER), "title_l": st("tl", fontName="KP-B", fontSize=19 * k, leading=23 * k),
        "sub": st("s", fontSize=11 * k, leading=15 * k, alignment=TA_CENTER), "num": st("n", fontSize=10 * k, leading=14 * k, alignment=TA_CENTER, textColor=GREY),
        "num_l": st("nl", fontSize=10 * k, leading=14 * k, textColor=GREY), "tag": st("tg", fontSize=10 * k, leading=14 * k, textColor=GREY),
        "tval": st("tv", fontSize=9 * min(k, 1.0), leading=12 * min(k, 1.0)),
        "prod": st("p", fontName="KP-B", fontSize=14 * k, leading=18 * k), "name": st("nm", fontName="KP-B", fontSize=9 * min(k, 1.0), leading=12 * min(k, 1.0)),
        "lbl": st("l", fontSize=9 * k, leading=12 * k, textColor=GREY), "val": st("v", fontSize=9 * k, leading=12 * k),
        "cell": st("c", fontSize=9 * min(k, 1.0), leading=12 * min(k, 1.0)), "cellc": st("cc", fontSize=9 * min(k, 1.0), leading=12 * min(k, 1.0), alignment=TA_CENTER),
        "head": st("h", fontName="KP-B", fontSize=9 * min(k, 1.0), leading=12 * min(k, 1.0), alignment=TA_CENTER),
        "total": st("tt", fontName="KP-B", fontSize=14 * k, leading=18 * k, alignment=TA_RIGHT),
        "total2": st("t2", fontSize=10 * k, leading=14 * k, alignment=TA_RIGHT, textColor=GREY),
        "note": st("nt", fontSize=9 * k, leading=12 * k, textColor=GREY), "text": st("tx", fontSize=10 * k, leading=14 * k),
        "man": st("m", fontName="KP-B", fontSize=11 * k, leading=15 * k)}


def _spec_rows(S, title, item, k, label_w):
    return [[Paragraph(esc(a), S["lbl"]), Paragraph(esc(b), S["val"])] for a, b in pick_specs(title, item.get("specs"), item.get("pack_area"))]


def _blocks(ctx, S, k, items, rows, discs, show_pct, imgs, main_idx):
    """КП «без общей суммы»: у каждой позиции своя небольшая таблица в обычном оформлении (шапка и одна строка), под строкой — срок и комментарий позиции; итогов нет."""
    out, svc = [], []
    terms, cmts = ctx.get("item_terms") or {}, ctx.get("item_cmts") or {}
    ph_t, prod_w = 62 * min(k, 1.2), 168
    pad = 5 * k
    compact = sum(1 for r in rows if r[1] and r[0] != "") >= 4            # от четырёх позиций шапка таблицы только у первой — иначе всё мелко
    first = True
    for idx, r in enumerate(rows):
        number, name, _u, _a, _x, price, qty_text, amount = r
        if not name:
            continue
        if number == "":                                                 # доставка, подъём — отдельными строками под таблицами
            svc.append(Paragraph(f"{esc(name)}: <b>{money(amount)}</b>", S["text"]))
            continue
        it = items[idx] if idx < len(items) else {}
        qty = Paragraph(esc(_qty(qty_text)) if qty_text else "1", S["cellc"])
        d = discs.get(idx)
        hh = 1 if (first or not compact) else 0                          # есть ли строка шапки
        first = False
        style = [("GRID", (0, 0), (-1, -1), 0.6, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                 ("TOPPADDING", (0, 0), (-1, -1), pad), ("BOTTOMPADDING", (0, 0), (-1, -1), pad)]
        if hh:
            style.append(("BACKGROUND", (0, 0), (-1, 0), HEAD_BG))
        if idx in main_idx:
            main, _t = imgs(idx)
            nm = Paragraph(esc(name), S["name"])
            prod = Table([[PhotoBox(main, None, ph_t), nm]], colWidths=[ph_t + 6, prod_w - ph_t - 10]) if main else nm
            if main:
                prod.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
            chars = [Paragraph("• " + esc(a_) + ": " + esc(b_), S["tval"]) for a_, b_ in pick_specs(it.get("title") or name, it.get("specs"), it.get("pack_area"))]
            head = [Paragraph(x, S["head"]) for x in ("№", "Товар", "Характеристики", "Цена за ед.", "Кол-во", "Сумма")]
            row = [Paragraph(str(number), S["cellc"]), prod, chars, _pc(price, d, S, show_pct), qty, _pc(amount, d, S, show_pct)]
            cw = [22, prod_w, CONTENT_W - 22 - prod_w - 80 - 54 - 88, 80, 54, 88]
        else:                                                            # клей, грунт, подложка — строка без фото и характеристик
            head = [Paragraph(x, S["head"]) for x in ("№", "Наименование", "", "Цена за ед.", "Кол-во", "Сумма")]
            row = [Paragraph(str(number), S["cellc"]), Paragraph(esc(name), S["cell"]), "", _pc(price, d, S, show_pct), qty, _pc(amount, d, S, show_pct)]
            cw = [22, prod_w, CONTENT_W - 22 - prod_w - 80 - 54 - 88, 80, 54, 88]
            style += [("SPAN", (1, r_), (2, r_)) for r_ in range(hh + 1)]
        data = [head, row] if hh else [row]
        extra = []
        net = it.get("net")
        if net:                                                          # чистая площадь именно этой позиции
            extra.append(f'<font color="#6B7280">Расчет выполнен на {net:g}'.replace(".", ",") + ' кв.м.</font>')
        if terms.get(idx):
            extra.append(f'<font color="#6B7280">Срок поставки:</font> <b>{esc(terms[idx])}</b>')
        if cmts.get(idx):
            extra.append(f'<font color="#6B7280">Комментарий:</font> {esc(cmts[idx])}')
        if extra:
            data.append([Paragraph("<br/>".join(extra), S["val"]), "", "", "", "", ""])
            style += [("SPAN", (0, hh + 1), (-1, hh + 1)), ("ALIGN", (0, hh + 1), (-1, hh + 1), "LEFT")]
        tbl = Table(data, colWidths=cw)
        tbl.setStyle(TableStyle(style))
        out += [KeepTogether(tbl), Spacer(1, (4 if compact else 8) * k)]
    for p_ in svc:
        out.append(p_)
    if ctx.get("delivery_text"):
        out += [Spacer(1, 4), Paragraph(esc(ctx["delivery_text"]), S["text"])]
    for ln in ctx.get("extra_lines") or []:
        out.append(Paragraph(esc(ln), S["text"]))
    return out


def _flow(ctx, k):
    S = styles(k)
    discs = {int(i): float(d) for i, d in (ctx.get("discs") or {}).items()}
    show_pct = ctx.get("disc_pct", True)                                # False: у позиций зачёркнутая цена без числа процента (процент остаётся в итоговой строке)
    items = ctx.get("items") or []
    rows = ctx["rows"]
    main_idx = ctx.get("main")
    if main_idx is None:
        main_idx = {i for i, it in enumerate(items) if not any(w in (it.get("title") or "").lower() for w in ("клей", "грунт", "подложка"))}
    main_idx = sorted(main_idx)
    nt = bool(ctx.get("no_total"))
    multi = len(main_idx) > 1 or nt                                   # «без общей суммы» — шапка как у КП с несколькими позициями
    sp = lambda h: Spacer(1, h * k)
    fl = []
    line = Table([[""]], colWidths=[CONTENT_W], rowHeights=[2])
    line.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 1, GOLD)]))
    num = f"№ {esc(ctx['number'])} от {ctx['date']}" + (f" · {esc(ctx['company'])}" if ctx.get("company") else "")
    if multi:                                                           # логотип слева и подпись, заголовок слева — как в образце с несколькими позициями
        tag = Paragraph("Напольные покрытия<br/>от ведущих производителей<br/>с доставкой по России", S["tag"])
        hd = Table([[_logo(110 * k), tag]], colWidths=[110 * k + 20, CONTENT_W - 110 * k - 20])
        hd.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
        fl += [hd, sp(4), Paragraph("Коммерческое предложение", S["title_l"]), Paragraph(num, S["num_l"]), sp(6), line, sp(8)]
    else:
        fl += [_logo(150 * k), sp(4), Paragraph("Коммерческое предложение", S["title"]), Paragraph("на поставку напольных покрытий", S["sub"]), sp(4),
               Paragraph(num, S["num"]), sp(6), line, sp(8)]

    def imgs(i):
        im = (items[i].get("images") or []) if i < len(items) else []
        return (im[0] if im else None), (im[1] if len(im) > 1 else None)

    if not multi and main_idx:
        it = items[main_idx[0]]
        main, thumb = imgs(main_idx[0])
        ph = 200 * k
        right = [Paragraph(esc(it.get("title", "")), S["prod"]), sp(6)]
        sr = _spec_rows(S, it.get("title"), it, k, 92)
        if sr:
            right.append(Table(sr, colWidths=[100 * k, CONTENT_W - ph - 22 - 100 * k - 6],
                               style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 2 * k), ("BOTTOMPADDING", (0, 0), (-1, -1), 2 * k),
                                                 ("LEFTPADDING", (0, 0), (-1, -1), 0)])))
        if main:
            top = Table([[PhotoBox(main, thumb, ph), right]], colWidths=[ph + 22, CONTENT_W - ph - 22])
            top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (0, 0), 22)]))
        else:                                                           # без фото: карточка с золотой полосой, характеристики в две колонки на всю ширину
            cells = [Paragraph(f'<font color="#6B7280">{esc(a)}</font><br/>{esc(b)}', S["val"]) for a, b in pick_specs(it.get("title"), it.get("specs"), it.get("pack_area"))]
            if len(cells) % 2:
                cells.append("")
            grid = Table([cells[i:i + 2] for i in range(0, len(cells), 2)], colWidths=[(CONTENT_W - 40) / 2] * 2,
                         style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 4 * k), ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * k),
                                           ("LEFTPADDING", (0, 0), (-1, -1), 0)])) if cells else ""
            top = Table([[Paragraph(esc(it.get("title", "")), S["prod"])], [grid]], colWidths=[CONTENT_W])
            top.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), HEAD_BG), ("LINEBEFORE", (0, 0), (0, -1), 3, GOLD), ("LEFTPADDING", (0, 0), (-1, -1), 16),
                                     ("RIGHTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, 0), 12 * k), ("BOTTOMPADDING", (0, -1), (-1, -1), 10 * k)]))
        fl += [top, sp(12)]

    n0 = len(fl)
    # таблица позиций
    head = [Paragraph(x, S["head"]) for x in (("№", "Товар", "Характеристики", "Цена за ед.", "Кол-во", "Сумма") if multi else ("№", "Наименование", "Цена за ед.", "Количество", "Сумма"))]
    data, totals, style = [head], [], []
    ph_t = 58 * min(k, 1.2)
    prod_w = 168
    for idx, r in enumerate(rows):
        number, name, _u, _a, _x, price, qty_text, amount = r
        if not name:
            if qty_text:
                totals.append((str(qty_text).rstrip(":") + ":", amount))
            continue
        qty = Paragraph(esc(_qty(qty_text)) if qty_text else "1", S["cellc"])
        if multi and idx in main_idx:
            it = items[idx] if idx < len(items) else {}
            main, thumb = imgs(idx)
            nm = Paragraph(esc(name), S["name"])
            prod = Table([[PhotoBox(main, None, ph_t), nm]], colWidths=[ph_t + 6, prod_w - ph_t - 10]) if main else nm
            if main:
                prod.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 2)]))
            chars = [Paragraph("• " + esc(a) + ": " + esc(b), S["tval"]) for a, b in pick_specs(it.get("title") or name, it.get("specs"), it.get("pack_area"))]
            data.append([Paragraph(str(number), S["cellc"]), prod, chars, _pc(price, discs.get(idx), S, show_pct), qty, _pc(amount, discs.get(idx), S, show_pct)])
        elif multi:                                                      # клей, грунт, доставка, подъём — обычной строкой без картинки
            data.append([Paragraph(str(number), S["cellc"]), Paragraph(esc(name), S["cell"]), "", _pc(price, discs.get(idx), S, show_pct), qty, _pc(amount, discs.get(idx), S, show_pct)])
            style.append(("SPAN", (1, len(data) - 1), (2, len(data) - 1)))
        else:
            data.append([Paragraph(str(number), S["cellc"]), Paragraph(esc(name), S["cell"]), _pc(price, discs.get(idx), S, show_pct), qty, _pc(amount, discs.get(idx), S, show_pct)])
    if multi:
        cw = [22, prod_w, CONTENT_W - 22 - prod_w - 80 - 54 - 88, 80, 54, 88]
    else:
        cw = [26, CONTENT_W - 26 - 84 - 78 - 96, 84, 78, 96]
    pad = 5 * k + (k - 1) * 14 if k > 1 else 5 * k
    tbl = Table(data, colWidths=cw, repeatRows=1)
    tbl.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), HEAD_BG), ("GRID", (0, 0), (-1, -1), 0.6, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                             ("TOPPADDING", (0, 0), (-1, -1), pad), ("BOTTOMPADDING", (0, 0), (-1, -1), pad)] + style))
    fl.append(tbl)
    if ctx.get("pos_text"):
        fl += [sp(3), Paragraph(esc(ctx["pos_text"]), S["note"])]
    fl.append(sp(6))
    if totals:
        cells = [[Paragraph(f"{esc(lbl)} {money(a)}", S["total"] if i == len(totals) - 1 else S["total2"])] for i, (lbl, a) in enumerate(totals)]
        tb = Table(cells, colWidths=[CONTENT_W])
        tb.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), HEAD_BG), ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 3 * k),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * k)]))
        fl.append(tb)
    if ctx.get("delivery_text"):
        fl += [sp(5), Paragraph(esc(ctx["delivery_text"]), S["text"])]
    for ln in ctx.get("extra_lines") or []:
        fl.append(Paragraph(esc(ln), S["text"]))
    if nt:
        del fl[n0:]
        fl += _blocks(ctx, S, k, items, rows, discs, show_pct, imgs, main_idx)
    fl.append(sp(10))

    cstyle = ctx.get("cstyle", "plain")
    vstyle = ParagraphStyle("cv", parent=S["val"], fontName="KP-B") if cstyle == "bold" else S["val"]

    def link(url, text):
        if cstyle:                                                      # спокойная подача: тёмный текст, без синего и подчёркивания; ссылка остаётся кликабельной
            return Paragraph(f'<link href="{url}" color="#1F2328">{esc(text)}</link>', vstyle)
        return Paragraph(f'<link href="{url}" color="#1F4E8C"><u>{esc(text)}</u></link>', S["val"])
    icons = ctx.get("icons", True)
    shown = BRAND["phone"]
    contacts = [("", "Телефон", Paragraph(esc(ctx.get("phone") or ""), S["val"])), ("", "Почта", Paragraph(BRAND["email"], vstyle)),
                ("tg", "Telegram", link(f"https://t.me/{BRAND['telegram'].lstrip('@')}", BRAND["telegram"])), ("wa", "WhatsApp", link(BRAND["whatsapp_url"], shown)),
                ("max", "Max", link(BRAND["max_url"], shown)),
                ("web", "Сайт", link("https://" + BRAND["site"], BRAND["site"]))]
    lbl_r = ParagraphStyle("lblr", parent=S["lbl"], alignment=TA_RIGHT)
    if icons:                                                           # у мессенджеров и сайта вместо слова значок; подписи и значки — по правому краю, значения — по левому
        rows_c = [[Icon(ic, 12 * k, 46) if ic else Paragraph(a, lbl_r), b] for ic, a, b in contacts]
        cw_c = [52, 178]
    else:
        rows_c = [[Paragraph(a, S["lbl"]), b] for _ic, a, b in contacts]
        cw_c = [58, 170]
    left = [Paragraph("Менеджер", S["man"]), Paragraph(esc(ctx.get("manager") or ""), S["text"]), sp(4),
            Table(rows_c, colWidths=cw_c, style=TableStyle([("TOPPADDING", (0, 0), (-1, -1), 1.5 * k), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5 * k),
                                                           ("LEFTPADDING", (0, 0), (-1, -1), 0), ("LEFTPADDING", (1, 0), (1, -1), 10), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
                                                          + ([("TOPPADDING", (0, 0), (-1, -1), 3 * k), ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * k)] + ([("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE)] if cstyle == "lines" else []) if cstyle else [])))]
    uk = ctx.get("uk", "frame")
    if uk == "card" and not os.path.exists(os.path.join(ASSETS, "seal_box.png")):   # картинка-маскот компании в витрину не входит
        uk = "frame"
    hello = Paragraph(f"Будем рады ответить на все ваши вопросы! С уважением, команда {BRAND['team']}", S["note"])
    if uk:
        head_txt = ctx.get("uk_head") or UK_HEAD
        fs, avail = 11 * k, CONTENT_W * 0.54 - 10 - 24                  # заголовок всегда в одну строку: шрифт уменьшается до ширины рамки
        while fs > 8 * k and pdfmetrics.stringWidth(head_txt, "KP-B", fs) > avail:
            fs -= 0.25
        head = Paragraph(esc(head_txt), ParagraphStyle("hk", parent=S["man"], fontSize=fs, leading=fs * 1.3))
        body = Paragraph(esc(ctx.get("uk_body") or UK_BODY), S["tval"])
        rw = CONTENT_W * 0.54
        if uk == "card":                                                # серая карточка и котик с ящиком
            sh = 118 * k
            seal = RLImage(os.path.join(ASSETS, "seal_box.png"), width=sh * 1376 / 1806, height=sh)
            card = Table([[[head, sp(3), body], seal]], colWidths=[rw - sh * 1376 / 1806 - 26, sh * 1376 / 1806 + 8])
            card.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), HEAD_BG), ("LINEBEFORE", (0, 0), (0, -1), 3, GOLD), ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
                                      ("VALIGN", (1, 0), (1, 0), "BOTTOM"), ("LEFTPADDING", (0, 0), (0, 0), 12), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                                      ("RIGHTPADDING", (1, 0), (1, 0), 4)]))
        elif uk == "plain":                                             # без фона и котика: золотая линия слева, крупный заголовок
            card = Table([[[head, sp(3), body]]], colWidths=[rw])
            card.setStyle(TableStyle([("LINEBEFORE", (0, 0), (0, -1), 3, GOLD), ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                                      ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        else:                                                           # «frame»: тонкая золотая рамка со скруглением, без заливки
            card = Table([[[head, sp(3), body]]], colWidths=[rw])
            card.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1.2, GOLD), ("ROUNDEDCORNERS", [8, 8, 8, 8]), ("LEFTPADDING", (0, 0), (-1, -1), 12),
                                      ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
        right = [card]
    else:
        right = [sp(14), Paragraph("Будем рады ответить<br/>на все ваши вопросы!", S["text"]), sp(16), Paragraph(f"С уважением,<br/>команда {BRAND['team']}", S["text"])]
    foot = Table([[left, right]], colWidths=[CONTENT_W * 0.46, CONTENT_W * 0.54])
    foot.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("LINEABOVE", (0, 0), (-1, 0), 0.6, LINE),
                              ("TOPPADDING", (0, 0), (-1, 0), 8 * k), ("RIGHTPADDING", (-1, 0), (-1, 0), 0)]))      # правый край рамки вровень с таблицей
    if uk:
        foot = KeepTogether([foot, sp(6), hello])
    fl.append(foot if uk else KeepTogether(foot))
    return fl


def _page(c, _d):
    c.saveState()
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(M, 36, W - M, 36)
    c.setFont("KP", 7)
    c.setFillColor(GREY)
    c.drawCentredString(W / 2, 24, "Н А П О Л Ь Н Ы Е   П О К Р Ы Т И Я   Д Л Я   В А Ш Е Г О   К О М Ф О Р Т А")
    c.restoreState()


def render(ctx, ks=(1.10, 1.05, 1.0, 0.92, 0.85, 0.78, 0.71, 0.65, 0.59, 0.54, 0.5)):
    """ctx: number, date, company, items [{title, specs, pack_area, images [bytes]}] (по позициям таблицы), main (номера основных позиций), rows (matrix из build_model), pos_text, delivery_text,
    extra_lines, manager, phone. Всё должно уместиться на одной странице: масштаб шапки, фото и шрифтов уменьшается ступенями. Возвращает PDF (bytes)."""
    from pypdf import PdfReader
    out = None
    for k in ks:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=M, rightMargin=M, topMargin=26, bottomMargin=44, title=f"КП {ctx['number']}")
        doc.build(_flow(ctx, k), onFirstPage=_page, onLaterPages=_page)
        out = buf.getvalue()
        if len(PdfReader(io.BytesIO(out)).pages) == 1:
            break
    return out
