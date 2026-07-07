# -*- coding: utf-8 -*-
"""
INSTAL-PAWEŁ — miesięczne zestawienie sprzedaży (data -> PDF).

Funkcja publiczna:  generate_zestawienie_pdf(data: dict, out_path: str)

Jednostronicowe (zwykle) podsumowanie miesiąca do rozliczenia z księgową:
lista faktur wg daty sprzedaży, suma, podział firmy/osoby fizyczne oraz
narastająco od początku roku z limitami (VAT 200 000 zł, kasa fiskalna 20 000 zł).
Grafika marki importowana z generator.py — bez zmian w silniku wycen.

Schemat `data`:
{
  "wystawca": { jak w wycenie },
  "meta": { "miesiac": "czerwiec", "mm": "06", "rok": "2026", "wygenerowano": "07.07.2026" },
  "faktury": [ { "numer", "sprz", "nabywca", "osoba_fiz": bool, "status", "kwota" }, ... ],
  "sumy": { "razem", "firmy", "osfiz",
            "rok_razem", "rok_osfiz", "limit_vat", "limit_kasa" }
}
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Table, TableStyle,
                                Paragraph, Spacer, NextPageTemplate, HRFlowable)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT

from pdf_engine.generator import (_ensure_fonts, _styles, _grid, _bolt,
                                  money, liczba_slownie,
                                  NAVY, ORANGE, BLUE, CREAM, LIGHT, ZEBRA,
                                  LINE, GREY, CW)


def generate_zestawienie_pdf(data, out_path):
    _ensure_fonts()
    S = _styles()

    wy = data.get("wystawca", {})
    meta = data.get("meta", {})
    faktury = data.get("faktury", [])
    sumy = data.get("sumy", {})
    brand_word = wy.get("wordmark", "INSTAL-PAWEL")
    brand_sub = wy.get("wordmark_sub", "USŁUGI ELEKTRYCZNE")
    tytul = "ZESTAWIENIE"
    podtytul = f'{meta.get("miesiac","")} {meta.get("rok","")}'.strip()
    stopka = f'{wy.get("nazwa","INSTAL-PAWEŁ")} — Zestawienie sprzedaży: {podtytul}'

    def section(title):
        return [Paragraph(title, S["sect"]),
                HRFlowable(width=CW, thickness=1.4, color=ORANGE, spaceBefore=3, spaceAfter=8)]

    story = [NextPageTemplate("later")]

    # -- nagłówek treści --
    story += section(f"SPRZEDAŻ — {podtytul.upper()} (wg daty sprzedaży)")

    # -- tabela faktur --
    rows = [[Paragraph("Lp.", S["thC"]), Paragraph("Numer", S["th"]),
             Paragraph("Data sprzedaży", S["thC"]), Paragraph("Nabywca", S["th"]),
             Paragraph("Rodzaj", S["thC"]), Paragraph("Status", S["thC"]),
             Paragraph("Kwota", S["thR"])]]
    for i, f in enumerate(faktury, 1):
        rows.append([Paragraph(str(i), S["cellC"]),
                     Paragraph(f.get("numer", ""), S["cell"]),
                     Paragraph(f.get("sprz", ""), S["cellC"]),
                     Paragraph(f.get("nabywca", "") or "—", S["cell"]),
                     Paragraph("os. fizyczna" if f.get("osoba_fiz") else "firma", S["cellC"]),
                     Paragraph(f.get("status", ""), S["cellC"]),
                     Paragraph(money(f.get("kwota", 0)), S["cellR"])])
    rows.append([Paragraph("", S["cell"]), Paragraph("<b>RAZEM</b>", S["cell"]),
                 Paragraph("", S["cell"]), Paragraph("", S["cell"]), Paragraph("", S["cell"]),
                 Paragraph("", S["cell"]),
                 Paragraph("<b>" + money(sumy.get("razem", 0)) + "</b>", S["cellR"])])
    t = Table(rows, colWidths=[10 * mm, 20 * mm, 24 * mm, 42 * mm, 24 * mm, 28 * mm, 26 * mm],
              repeatRows=1)
    ts = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
          ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
          ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE), ("BOX", (0, 0), (-1, -1), 0.6, LINE),
          ("BACKGROUND", (0, -1), (-1, -1), LIGHT), ("LINEABOVE", (0, -1), (-1, -1), 1.2, ORANGE),
          ("SPAN", (1, -1), (5, -1))]
    for r in range(1, len(faktury) + 1):
        if r % 2 == 0:
            ts.append(("BACKGROUND", (0, r), (-1, r), ZEBRA))
    t.setStyle(TableStyle(ts))
    story += [t, Spacer(1, 6)]
    story.append(Paragraph(f'<font size=8 color="#5B6B7B"><b>Słownie:</b> '
                           f'{liczba_slownie(sumy.get("razem", 0))}.</font>', S["small"]))
    story.append(Spacer(1, 12))

    # -- podział firmy / osoby fizyczne --
    story += section("PODZIAŁ SPRZEDAŻY W MIESIĄCU")
    pod = [[Paragraph("Sprzedaż dla firm:", S["base"]),
            Paragraph(money(sumy.get("firmy", 0)), S["cellR"])],
           [Paragraph("Sprzedaż dla osób fizycznych (bez NIP):", S["base"]),
            Paragraph(money(sumy.get("osfiz", 0)), S["cellR"])],
           [Paragraph("<b>Razem:</b>", S["base"]),
            Paragraph("<b>" + money(sumy.get("razem", 0)) + "</b>", S["cellR"])]]
    tp = Table(pod, colWidths=[100 * mm, 40 * mm])
    tp.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -2), 0.5, LINE),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE), ("BACKGROUND", (0, -1), (-1, -1), LIGHT),
        ("LINEBEFORE", (0, 0), (0, -1), 3, ORANGE),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10)]))
    story += [tp, Spacer(1, 12)]

    # -- narastająco od początku roku + limity --
    story += section(f'NARASTAJĄCO OD POCZĄTKU ROKU {meta.get("rok","")}')
    lv, lk = float(sumy.get("limit_vat", 200000)), float(sumy.get("limit_kasa", 20000))
    rr, ro = float(sumy.get("rok_razem", 0)), float(sumy.get("rok_osfiz", 0))
    nar = [[Paragraph("Obrót od 1 stycznia (limit zwolnienia z VAT, art. 113):", S["base"]),
            Paragraph(f"<b>{money(rr)}</b> / {money(lv)}  ({rr / lv * 100:.0f}%)", S["cellR"])],
           [Paragraph("Sprzedaż osobom fizycznym od 1 stycznia (limit kasy fiskalnej):", S["base"]),
            Paragraph(f"<b>{money(ro)}</b> / {money(lk)}  ({ro / lk * 100:.0f}%)", S["cellR"])]]
    tn = Table(nar, colWidths=[104 * mm, 70 * mm])
    tn.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -2), 0.5, LINE),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE), ("LINEBEFORE", (0, 0), (0, -1), 3, BLUE),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10)]))
    story += [tn, Spacer(1, 8)]
    story.append(Paragraph(
        '<font size=7.5 color="#5B6B7B">Zestawienie pomocnicze wygenerowane z programu '
        f'INSTAL-PAWEŁ dnia {meta.get("wygenerowano","")} — kwoty wg daty sprzedaży '
        '(gdy brak — daty wystawienia). Sprzedawca zwolniony z VAT na podstawie art. 113 '
        'ust. 1 ustawy o VAT.</font>', S["small"]))

    # -- nagłówki stron (grafika marki jak w wycenie/umowie) --
    def _footer(c, doc):
        W, _ = A4; x0, x1 = 18 * mm, W - 18 * mm
        c.setFont("DJS", 7.5); c.setFillColor(GREY)
        c.drawString(x0, 11 * mm, stopka)
        c.drawRightString(x1, 11 * mm, "Strona %d" % doc.page)
        c.setStrokeColor(ORANGE); c.setLineWidth(1.0); c.line(x0, 14.5 * mm, x0 + 22 * mm, 14.5 * mm)
        c.setStrokeColor(LINE); c.setLineWidth(0.5); c.line(x0 + 24 * mm, 14.5 * mm, x1, 14.5 * mm)

    def draw_first(c, doc):
        W, H = A4; x0, x1 = 18 * mm, W - 18 * mm
        top = H - 8 * mm; hh = 24 * mm; bot = top - hh
        c.setFillColor(NAVY); c.rect(x0, bot, x1 - x0, hh, fill=1, stroke=0)
        _grid(c, x0, x1, bot, top)
        c.setFillColor(ORANGE); c.rect(x0, bot - 2.5 * mm, x1 - x0, 2.5 * mm, fill=1, stroke=0)
        _bolt(c, x0 + 6 * mm, bot + 4 * mm, 10.5 * mm, 16 * mm)
        tx = x0 + 6 * mm + 10.5 * mm + 7 * mm
        c.setFillColor(CREAM); c.setFont("DJS-BO", 19); c.drawString(tx, bot + hh * 0.50, brand_word)
        c.saveState(); c.setFillColor(BLUE); c.setFont("DJS-B", 7.4)
        to = c.beginText(); to.setTextOrigin(tx + 2, bot + hh * 0.28); to.setCharSpace(2.0)
        to.textLine(brand_sub); c.drawText(to); c.restoreState()
        c.setFillColor(CREAM); c.setFont("DJS-B", 20); c.drawRightString(x1 - 3 * mm, top - 8.5 * mm, tytul)
        c.setFillColor(HexColor("#C9D6E2")); c.setFont("DJS", 8.6)
        c.drawRightString(x1 - 3 * mm, top - 14.5 * mm, podtytul)
        c.drawRightString(x1 - 3 * mm, top - 19 * mm, f'Wygenerowano:  {meta.get("wygenerowano","")}')
        _footer(c, doc)

    def draw_later(c, doc):
        W, H = A4; x0, x1 = 18 * mm, W - 18 * mm
        top = H - 7 * mm; hh = 12 * mm; bot = top - hh
        c.setFillColor(NAVY); c.rect(x0, bot, x1 - x0, hh, fill=1, stroke=0)
        _grid(c, x0, x1, bot, top)
        c.setFillColor(ORANGE); c.rect(x0, bot - 2 * mm, x1 - x0, 2 * mm, fill=1, stroke=0)
        _bolt(c, x0 + 5 * mm, bot + 2.4 * mm, 5 * mm, 7.6 * mm)
        c.setFillColor(CREAM); c.setFont("DJS-BO", 11); c.drawString(x0 + 13 * mm, bot + hh * 0.34, brand_word)
        c.setFillColor(HexColor("#C9D6E2")); c.setFont("DJS", 8)
        c.drawRightString(x1 - 3 * mm, bot + hh * 0.36, f"Zestawienie {podtytul}")
        _footer(c, doc)

    doc = BaseDocTemplate(out_path, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                          topMargin=12 * mm, bottomMargin=11 * mm,
                          title=f"Zestawienie {podtytul} - {wy.get('nazwa','')}",
                          author=wy.get("nazwa", ""))
    W, H = A4
    ff = Frame(18 * mm, 16 * mm, CW, H - 40 * mm - 16 * mm, id="ff",
               leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    fl = Frame(18 * mm, 16 * mm, CW, H - 26 * mm - 16 * mm, id="fl",
               leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="first", frames=[ff], onPage=draw_first),
                          PageTemplate(id="later", frames=[fl], onPage=draw_later)])
    doc.build(story)
    return out_path
