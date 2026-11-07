"""Рисует нейтральные демо-ресурсы (логотип и значки) — в рабочей версии здесь лежат файлы компании."""
import os

from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(__file__), "..", "src", "deepseal", "assets")
FONT = os.path.join(OUT, "DejaVuSans-Bold.ttf")


def badge(name, text, color, size=96):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((2, 2, size - 2, size - 2), fill=color)
    f = ImageFont.truetype(FONT, int(size * 0.45))
    w, h = d.textbbox((0, 0), text, font=f)[2:]
    d.text(((size - w) / 2, (size - h) / 2 - size * 0.05), text, font=f, fill="white")
    im.save(os.path.join(OUT, f"ic_{name}.png"))


for n, t, c in (("tg", "T", "#2AABEE"), ("wa", "W", "#25D366"), ("max", "M", "#7B5CFA"), ("web", "@", "#444444")):
    badge(n, t, c)

logo = Image.new("RGB", (600, 360), "white")
d = ImageDraw.Draw(logo)
d.rectangle((250, 70, 350, 170), fill="#E3B724")
f1, f2 = ImageFont.truetype(FONT, 56), ImageFont.truetype(FONT, 26)
d.text((300, 250), "DEMO FLOORS", font=f1, fill="#1F2328", anchor="mm")
d.text((300, 310), "demo-company.example", font=f2, fill="#6B7280", anchor="mm")
logo.save(os.path.join(OUT, "logo.png"))
