from deepseal.payment_purpose import categories, purpose


def test_first_named_category_wins():
    name = "Кварцевый ламинат Fargo Штучный паркет 44-653-76 Дуб Окленд 400*100*4.5мм"
    assert categories([name]) == ["кварцевый ламинат"]


def test_distinct_parquet_types():
    assert categories(["Штучный паркет Дуб"]) == ["штучный паркет"]
    assert categories(["Модульный паркет Ёлка"]) == ["модульный паркет"]


def test_accessories_after_main_and_underlay_last():
    names = ["Подложка под SPC 1,5мм", "Клей для паркета 14 кг", "SPC ламинат Aquamax"]
    assert categories(names) == ["виниловое покрытие", "клей", "подложку"]


def test_purpose_text():
    text = purpose("123", "01.01.2026", ["Ламинат 33 класс", "Подложка"], vat=1000, vat_rate=22)
    assert text == "Оплата по счету № 123 от 01.01.2026 за ламинат и подложку. В т.ч. НДС 22% - 1000.00 руб."


def test_unknown_goods_no_category():
    assert "за" not in purpose("5", "", ["Услуга консультации"])
