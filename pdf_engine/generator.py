# -*- coding: utf-8 -*-
"""
INSTAL-PAWEŁ — silnik szablonu wycen/ofert (data -> PDF).

Jedna funkcja publiczna:  generate_offer_pdf(data: dict, out_path: str)

Wygląd (marka INSTAL-PAWEŁ): granatowy nagłówek "blueprint" z pomarańczową
błyskawicą i wordmarkiem, tabele z granatowym nagłówkiem i pomarańczowym
akcentem, klauzula VAT art. 113, automatyczne sumy i kwota słownie.

Sekcje II (specyfikacja techniczna) i III są opcjonalne — jeśli brak danych,
powstaje krótka wycena; z danymi — pełna oferta wielostronicowa.

Zależności:  reportlab   (pip install reportlab)
Fonty:       DejaVu Sans (bundlowane w assets/fonts, z fallbackiem na system).
"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Table, TableStyle,
                                Paragraph, Spacer, KeepTogether, NextPageTemplate, HRFlowable)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER

# =========================================================== FONTY
_HERE = os.path.dirname(os.path.abspath(__file__))
_FONT_DIRS = [os.path.join(_HERE, "assets", "fonts"),
              "/usr/share/fonts/truetype/dejavu",
              "/Library/Fonts", "C:\\Windows\\Fonts"]

def _font_path(name):
    for d in _FONT_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    raise FileNotFoundError(f"Brak fontu {name}. Wrzuć pliki DejaVu do assets/fonts/.")

_FONTS_READY = False
def _ensure_fonts():
    global _FONTS_READY
    if _FONTS_READY:
        return
    pdfmetrics.registerFont(TTFont("DJS",    _font_path("DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DJS-B",  _font_path("DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("DJS-O",  _font_path("DejaVuSans-Oblique.ttf")))
    pdfmetrics.registerFont(TTFont("DJS-BO", _font_path("DejaVuSans-BoldOblique.ttf")))
    pdfmetrics.registerFontFamily("DJS", normal="DJS", bold="DJS-B", italic="DJS-O", boldItalic="DJS-BO")
    _FONTS_READY = True

# =========================================================== PALETA MARKI
NAVY    = HexColor("#0E2233")
NAVY_LN = HexColor("#21455F")
ORANGE  = HexColor("#F39200")
ORANGE_D= HexColor("#C56E00")
BLUE    = HexColor("#2F7FB8")
CREAM   = HexColor("#F5F1E6")
LIGHT   = HexColor("#E9F0F6")
ZEBRA   = HexColor("#F4F7FA")
KEYBG   = HexColor("#F1F5F9")
LINE    = HexColor("#C8D3DE")
DARK    = HexColor("#1F2933")
GREY    = HexColor("#5B6B7B")
CW = 174 * mm

# =========================================================== POMOCNICZE
def money(v):
    return f"{float(v):,.2f}".replace(",", " ").replace(".", ",") + " zł"

# --- liczba słownie (PLN) ---
_JEDN = ["", "jeden", "dwa", "trzy", "cztery", "pięć", "sześć", "siedem", "osiem", "dziewięć"]
_NAST = ["dziesięć", "jedenaście", "dwanaście", "trzynaście", "czternaście", "piętnaście",
         "szesnaście", "siedemnaście", "osiemnaście", "dziewiętnaście"]
_DZIES = ["", "", "dwadzieścia", "trzydzieści", "czterdzieści", "pięćdziesiąt",
          "sześćdziesiąt", "siedemdziesiąt", "osiemdziesiąt", "dziewięćdziesiąt"]
_SETKI = ["", "sto", "dwieście", "trzysta", "czterysta", "pięćset",
          "sześćset", "siedemset", "osiemset", "dziewięćset"]

def _trzycyfrowa(n):
    s = []
    setki, reszta = n // 100, n % 100
    dz, jd = reszta // 10, reszta % 10
    if setki: s.append(_SETKI[setki])
    if dz == 1:
        s.append(_NAST[jd])
    else:
        if dz: s.append(_DZIES[dz])
        if jd: s.append(_JEDN[jd])
    return " ".join(s)

def _forma(n, f):
    n = abs(n)
    if n == 1: return f[0]
    d2, d1 = n % 100, n % 10
    if 2 <= d1 <= 4 and not (12 <= d2 <= 14): return f[1]
    return f[2]

def liczba_slownie(kwota):
    """26820.0 -> 'dwadzieścia sześć tysięcy osiemset dwadzieścia złotych 00/100'"""
    zl = int(round(float(kwota) * 100)) // 100
    gr = int(round(float(kwota) * 100)) % 100
    if zl == 0:
        slowa = "zero"
    else:
        parts = []
        mil = zl // 1_000_000
        tys = (zl // 1000) % 1000
        reszta = zl % 1000
        if mil:
            parts += ([] if mil == 1 else [_trzycyfrowa(mil)]) + \
                     (["milion"] if mil == 1 else [_forma(mil, ("milion", "miliony", "milionów"))])
        if tys:
            parts += ([] if tys == 1 else [_trzycyfrowa(tys)]) + \
                     (["tysiąc"] if tys == 1 else [_forma(tys, ("tysiąc", "tysiące", "tysięcy"))])
        if reszta:
            parts.append(_trzycyfrowa(reszta))
        slowa = " ".join(p for p in parts if p)
    return f"{slowa} {_forma(zl, ('złoty', 'złote', 'złotych'))} {gr:02d}/100"

# =========================================================== STYLE
def _styles():
    S = {}
    S["base"]  = ParagraphStyle("base", fontName="DJS", fontSize=9, leading=12, textColor=DARK)
    S["small"] = ParagraphStyle("small", parent=S["base"], fontSize=8, leading=10.5, textColor=GREY)
    S["label"] = ParagraphStyle("label", fontName="DJS-B", fontSize=7.5, leading=10, textColor=BLUE)
    S["party"] = ParagraphStyle("party", parent=S["base"], fontSize=9, leading=12.5)
    S["partyName"] = ParagraphStyle("partyName", fontName="DJS-B", fontSize=10.5, leading=13.5, textColor=NAVY)
    S["cell"]  = ParagraphStyle("cell", fontName="DJS", fontSize=8.8, leading=11.5, textColor=DARK)
    S["cellR"] = ParagraphStyle("cellR", parent=S["cell"], alignment=TA_RIGHT)
    S["cellC"] = ParagraphStyle("cellC", parent=S["cell"], alignment=TA_CENTER)
    S["th"]    = ParagraphStyle("th", fontName="DJS-B", fontSize=8.3, leading=10.5, textColor=colors.white)
    S["thR"]   = ParagraphStyle("thR", parent=S["th"], alignment=TA_RIGHT)
    S["thC"]   = ParagraphStyle("thC", parent=S["th"], alignment=TA_CENTER)
    S["sect"]  = ParagraphStyle("sect", fontName="DJS-B", fontSize=11.5, leading=14, textColor=NAVY)
    S["sub"]   = ParagraphStyle("sub", fontName="DJS-B", fontSize=9.5, leading=12, textColor=NAVY)
    S["specK"] = ParagraphStyle("specK", fontName="DJS-B", fontSize=8.4, leading=11, textColor=NAVY)
    S["specV"] = ParagraphStyle("specV", fontName="DJS", fontSize=8.6, leading=11.5, textColor=DARK)
    S["clause"]= ParagraphStyle("clause", parent=S["base"], fontSize=8.5, leading=12)
    S["bul"]   = ParagraphStyle("bul", parent=S["base"], fontSize=8.6, leading=11.2,
                                leftIndent=12, firstLineIndent=-9, spaceAfter=1.5)
    return S

# =========================================================== RYSUNKI NAGŁÓWKA
def _grid(c, x0, x1, bot, top):
    c.saveState()
    p = c.beginPath(); p.rect(x0, bot, x1 - x0, top - bot); c.clipPath(p, stroke=0, fill=0)
    c.setStrokeColor(NAVY_LN); c.setLineWidth(0.4); step = 10 * mm
    yy = bot
    while yy <= top + 0.1:
        c.line(x0, yy, x1, yy); yy += step
    xx = x0
    while xx <= x1 + 0.1:
        c.line(xx, bot, xx, top); xx += step
    c.restoreState()

def _bolt(c, bx, by, bw, bh):
    pts = [(0.60, 1.00), (0.04, 0.46), (0.38, 0.46), (0.16, 0.00), (0.96, 0.60), (0.54, 0.60)]
    pa = c.beginPath()
    for i, (px, py) in enumerate(pts):
        X, Y = bx + px * bw, by + py * bh
        (pa.moveTo if i == 0 else pa.lineTo)(X, Y)
    pa.close()
    c.setFillColor(ORANGE); c.setStrokeColor(ORANGE_D); c.setLineWidth(0.8)
    c.drawPath(pa, fill=1, stroke=1)

# =========================================================== GENERATOR
def generate_offer_pdf(data, out_path):
    _ensure_fonts()
    S = _styles()

    wy   = data.get("wystawca", {})
    zam  = data.get("zamawiajacy", {})
    meta = data.get("meta", {})
    brand_word = wy.get("wordmark", "INSTAL-PAWEL")
    brand_sub  = wy.get("wordmark_sub", "USŁUGI ELEKTRYCZNE")
    tytul  = meta.get("tytul", "WYCENA")
    numer  = meta.get("numer", "")
    data_w = meta.get("data", "")
    stopka = f'{wy.get("nazwa","INSTAL-PAWEŁ")} — {tytul.capitalize()} {numer}'.strip(" —")

    # ---------- helpers zależne od stylu ----------
    def section(title):
        return [Paragraph(title, S["sect"]),
                HRFlowable(width=CW, thickness=1.4, color=ORANGE, spaceBefore=3, spaceAfter=8)]

    def subhead(t):
        return Table([[Paragraph(t, S["sub"])]], colWidths=[CW], style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("LINEBEFORE", (0, 0), (0, 0), 3, ORANGE),
            ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))

    def spec_table(rows):
        d = [[Paragraph(k, S["specK"]), Paragraph(v, S["specV"])] for k, v in rows]
        t = Table(d, colWidths=[55 * mm, 119 * mm])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BACKGROUND", (0, 0), (0, -1), KEYBG), ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
            ("BOX", (0, 0), (-1, -1), 0.6, LINE),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5)]))
        return t

    def bullet(t):
        return Paragraph('<font color="#F39200">▪</font>&nbsp; ' + t, S["bul"])

    # ---------- STORY ----------
    story = [NextPageTemplate("later")]

    # -- strony (wystawca / zamawiający) --
    wyk = [Paragraph("WYKONAWCA", S["label"]), Spacer(1, 3),
           Paragraph(wy.get("nazwa", ""), S["partyName"])]
    if wy.get("podtytul"):
        wyk.append(Paragraph(f'<font size=7.5 color="#5B6B7B">{wy["podtytul"]}</font>', S["small"]))
    wyk.append(Spacer(1, 3))
    for ln in [f'NIP: {wy.get("nip","")}', f'Adres: {wy.get("adres","")}',
               f'Tel.: {wy.get("tel","")}', f'E-mail: {wy.get("email","")}']:
        wyk.append(Paragraph(ln, S["party"]))

    zmk = [Paragraph("ZAMAWIAJĄCY", S["label"]), Spacer(1, 3),
           Paragraph(zam.get("nazwa", ""), S["partyName"]), Spacer(1, 2),
           Paragraph(zam.get("adres_html", ""), S["party"])]
    if zam.get("kontakt_html"):
        zmk += [Spacer(1, 4), Paragraph("Osoba kontaktowa:", S["small"]),
                Paragraph(zam["kontakt_html"], S["party"])]

    parties = Table([[wyk, zmk]], colWidths=[CW * 0.5, CW * 0.5])
    parties.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, 0), ZEBRA), ("BACKGROUND", (1, 0), (1, 0), ZEBRA),
        ("BOX", (0, 0), (0, 0), 0.6, LINE), ("BOX", (1, 0), (1, 0), 0.6, LINE),
        ("LINEBEFORE", (0, 0), (0, 0), 2.5, ORANGE), ("LINEBEFORE", (1, 0), (1, 0), 2.5, BLUE),
        ("LEFTPADDING", (0, 0), (-1, -1), 11), ("RIGHTPADDING", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LINEAFTER", (0, 0), (0, 0), 6, colors.white)]))
    story += [parties, Spacer(1, 8)]

    # -- przedmiot --
    if data.get("przedmiot"):
        subj = Table([[Paragraph(f'<b>Przedmiot oferty:</b>&nbsp;&nbsp;{data["przedmiot"]}', S["base"])]],
                     colWidths=[CW])
        subj.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), LIGHT),
            ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LINEBEFORE", (0, 0), (0, 0), 3, ORANGE)]))
        story += [subj, Spacer(1, 12)]

    # -- I. ZESTAWIENIE --
    story += section("I.&nbsp;&nbsp;ZESTAWIENIE OFERTOWE")
    poz = data.get("pozycje", [])
    suma_mat = sum(float(p["brutto"]) for p in poz)
    rows = [[Paragraph("Lp.", S["thC"]), Paragraph("Pozycja", S["th"]),
             Paragraph("Ilość", S["thC"]), Paragraph("Wartość brutto", S["thR"])]]
    for i, p in enumerate(poz, 1):
        rows.append([Paragraph(str(i), S["cellC"]), Paragraph(p["nazwa"], S["cell"]),
                     Paragraph(str(p.get("ilosc", "")), S["cellC"]), Paragraph(money(p["brutto"]), S["cellR"])])
    rows.append([Paragraph("", S["cell"]), Paragraph("<b>RAZEM MATERIAŁY (brutto)</b>", S["cell"]),
                 Paragraph("", S["cell"]), Paragraph("<b>" + money(suma_mat) + "</b>", S["cellR"])])
    tm = Table(rows, colWidths=[12 * mm, 108 * mm, 21 * mm, 33 * mm], repeatRows=1)
    ms = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
          ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
          ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE), ("BOX", (0, 0), (-1, -1), 0.6, LINE),
          ("BACKGROUND", (0, -1), (-1, -1), LIGHT), ("LINEABOVE", (0, -1), (-1, -1), 1.2, ORANGE),
          ("SPAN", (0, -1), (1, -1))]
    for r in range(1, len(poz) + 1):
        if r % 2 == 0:
            ms.append(("BACKGROUND", (0, r), (-1, r), ZEBRA))
    tm.setStyle(TableStyle(ms))
    story += [tm, Spacer(1, 7)]

    rob = data.get("robocizna")
    suma = suma_mat
    if rob:
        etapy_rob = [e for e in (rob.get("etapy") or []) if float(e.get("kwota") or 0) > 0]
        if etapy_rob:
            # wykaz etapów prac — klient widzi, co wchodzi w cenę robocizny
            rr = [[Paragraph("Lp.", S["thC"]), Paragraph("Robocizna — wykaz prac", S["th"]),
                   Paragraph("Wartość", S["thR"])]]
            for i, e in enumerate(etapy_rob, 1):
                rr.append([Paragraph(str(i), S["cellC"]), Paragraph(e.get("nazwa", ""), S["cell"]),
                           Paragraph(money(e["kwota"]), S["cellR"])])
            rr.append([Paragraph("<b>RAZEM ROBOCIZNA" +
                                 (" (zw. z VAT)" if rob.get("vat_zwolniona", True) else "") + "</b>", S["cell"]),
                       Paragraph("", S["cell"]),
                       Paragraph("<b>" + money(rob["kwota"]) + "</b>", S["cellR"])])
            tr_ = Table(rr, colWidths=[12 * mm, 129 * mm, 33 * mm], repeatRows=1)
            rs = [("BACKGROUND", (0, 0), (-1, 0), BLUE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                  ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                  ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                  ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE), ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                  ("BACKGROUND", (0, -1), (-1, -1), LIGHT), ("LINEABOVE", (0, -1), (-1, -1), 1.2, BLUE),
                  ("SPAN", (0, -1), (1, -1))]
            for r_ in range(1, len(etapy_rob) + 1):
                if r_ % 2 == 0:
                    rs.append(("BACKGROUND", (0, r_), (-1, r_), ZEBRA))
            tr_.setStyle(TableStyle(rs))
            story.append(tr_)
        else:
            lab = Table([[Paragraph(rob.get("opis", "Robocizna"), S["cell"]),
                          Paragraph("<b>" + money(rob["kwota"]) + "</b>", S["cellR"])]],
                        colWidths=[141 * mm, 33 * mm])
            lab.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, LINE), ("BACKGROUND", (0, 0), (-1, -1), ZEBRA),
                ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBEFORE", (0, 0), (0, 0), 3, BLUE)]))
            story.append(lab)
        if rob.get("vat_zwolniona", True):
            story.append(Paragraph('<font size=7.3 color="#5B6B7B">Robocizna zwolniona z VAT – patrz klauzula.</font>',
                                    ParagraphStyle("x", parent=S["small"], spaceBefore=2)))
        story.append(Spacer(1, 7))
        suma += float(rob["kwota"])

    # -- dodatkowe usługi (opcjonalne — np. transport, wynajem podnośnika) --
    uslugi = [u for u in (data.get("uslugi_dodatkowe") or []) if float(u.get("kwota") or 0) > 0]
    suma_uslug = sum(float(u["kwota"]) for u in uslugi)
    if uslugi:
        ur = [[Paragraph(u.get("opis") or "Usługa dodatkowa", S["cell"]),
               Paragraph("<b>" + money(u["kwota"]) + "</b>", S["cellR"])] for u in uslugi]
        ut = Table(ur, colWidths=[141 * mm, 33 * mm])
        ut.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, LINE), ("BACKGROUND", (0, 0), (-1, -1), ZEBRA),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINE),
            ("LINEBEFORE", (0, 0), (0, -1), 3, ORANGE)]))
        story += [ut, Spacer(1, 7)]
        suma += suma_uslug

    # -- podsumowanie --
    sd = [[Paragraph("Materiały (brutto):", S["base"]), Paragraph(money(suma_mat), S["cellR"])]]
    if rob:
        sd.append([Paragraph("Robocizna (zw. z VAT):" if rob.get("vat_zwolniona", True) else "Robocizna (brutto):",
                             S["base"]), Paragraph(money(rob["kwota"]), S["cellR"])])
    if uslugi:
        sd.append([Paragraph("Dodatkowe usługi:", S["base"]), Paragraph(money(suma_uslug), S["cellR"])])
    sd.append([Paragraph('<font color="#F5F1E6"><b>RAZEM DO ZAPŁATY:</b></font>',
                 ParagraphStyle("tw", fontName="DJS-B", fontSize=9.6, leading=12, textColor=CREAM)),
               Paragraph('<font color="#F39200"><b>' + money(suma) + '</b></font>',
                 ParagraphStyle("twr", fontName="DJS-B", fontSize=11.5, leading=14, textColor=ORANGE, alignment=TA_RIGHT))])
    st = Table(sd, colWidths=[48 * mm, 38 * mm])
    st.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("LINEBELOW", (0, 0), (-1, len(sd) - 2), 0.5, LINE), ("BACKGROUND", (0, len(sd) - 1), (-1, len(sd) - 1), NAVY),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE), ("LINEBEFORE", (0, len(sd) - 1), (0, len(sd) - 1), 3, ORANGE)]))
    story.append(Table([["", st]], colWidths=[CW - 86 * mm, 86 * mm],
        style=TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                          ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)])))
    story.append(Spacer(1, 3))
    story.append(Table([["", Paragraph(f'<font size=8 color="#5B6B7B"><b>Słownie:</b> {liczba_slownie(suma)}.</font>',
                        S["small"])]], colWidths=[CW - 86 * mm, 86 * mm],
        style=TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (1, 0), (1, 0), 0),
                          ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)])))
    story.append(Spacer(1, 9))

    # -- II. SPECYFIKACJA TECHNICZNA (opcjonalnie) --
    spec = data.get("spec_techniczna", [])
    konstr = data.get("konstrukcja")
    mat_pom = data.get("materialy_pomocnicze", [])
    if spec or konstr or mat_pom:
        story += section("II.&nbsp;&nbsp;SZCZEGÓŁOWA SPECYFIKACJA TECHNICZNA")
        for blok in spec:
            story.append(KeepTogether([subhead(blok["tytul"]), Spacer(1, 4), spec_table(blok["parametry"])]))
            story.append(Spacer(1, 6))
        if konstr:
            story.append(subhead(konstr.get("tytul", "Konstrukcja wsporcza")))
            story.append(Spacer(1, 4))
            for b in konstr.get("opis", []):
                story.append(bullet(b))
            if konstr.get("elementy"):
                story.append(Spacer(1, 6))
                story.append(Paragraph(f'<font size=8.2 color="#0E2233"><b>{konstr.get("naglowek_wykazu","Wykaz elementów konstrukcji")}:</b></font>', S["base"]))
                story.append(Spacer(1, 3))
                ch = [Paragraph("Lp.", S["thC"]), Paragraph("Symbol/indeks", S["th"]),
                      Paragraph("Nazwa elementu", S["th"]), Paragraph("Ilość", S["thC"]), Paragraph("j.m.", S["thC"])]
                cr = [ch]
                for i, e in enumerate(konstr["elementy"], 1):
                    sym, nz, il, jm = e
                    cr.append([Paragraph(str(i), S["cellC"]), Paragraph(sym, S["cell"]),
                               Paragraph(nz, S["cell"]), Paragraph(str(il), S["cellC"]), Paragraph(jm, S["cellC"])])
                tc = Table(cr, colWidths=[11 * mm, 28 * mm, 98 * mm, 16 * mm, 21 * mm], repeatRows=1)
                cs = [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                      ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                      ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                      ("INNERGRID", (0, 1), (-1, -1), 0.4, LINE), ("BOX", (0, 0), (-1, -1), 0.6, LINE)]
                for r in range(1, len(konstr["elementy"]) + 1):
                    if r % 2 == 0:
                        cs.append(("BACKGROUND", (0, r), (-1, r), ZEBRA))
                tc.setStyle(TableStyle(cs))
                story.append(tc)
            if konstr.get("nota"):
                story.append(Paragraph(f'<font size=7.3 color="#5B6B7B">{konstr["nota"]}</font>',
                                       ParagraphStyle("x2", parent=S["small"], spaceBefore=3)))
            story.append(Spacer(1, 6))
        if mat_pom:
            story.append(subhead("Materiały pomocnicze"))
            story.append(Spacer(1, 4))
            for b in mat_pom:
                story.append(bullet(b))
            story.append(Spacer(1, 6))
        story.append(Spacer(1, 3))

    # -- III. WARUNKI (cała sekcja trzymana razem, aby podpisy nie zostały same) --
    klauzula = data.get("klauzula_vat",
        'Usługa montażu i uruchomienia instalacji (robocizna) korzysta ze zwolnienia z podatku od '
        'towarów i usług na podstawie <b>art.&nbsp;113 ust.&nbsp;1 ustawy z dnia 11&nbsp;marca&nbsp;2004&nbsp;r. '
        'o podatku od towarów i usług</b> (zwolnienie podmiotowe). Do wartości robocizny nie dolicza się '
        'podatku VAT. Ceny materiałów podano w kwotach brutto (zawierają podatek VAT).')
    cl = Table([[Paragraph('<b>Klauzula VAT:</b>&nbsp; ' + klauzula, S["clause"])]], colWidths=[CW])
    cl.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), HexColor("#EFF4F8")),
        ("BOX", (0, 0), (-1, -1), 0.6, HexColor("#C7D5E0")), ("LINEBEFORE", (0, 0), (0, 0), 3, ORANGE),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    sec3 = [Paragraph("III.&nbsp;&nbsp;WARUNKI I INFORMACJE", S["sect"]),
            HRFlowable(width=CW, thickness=1.4, color=ORANGE, spaceBefore=3, spaceAfter=8),
            cl, Spacer(1, 8)]
    for w in data.get("warunki", ["Oferta ważna 30 dni od daty wystawienia.",
                                  "Termin realizacji do uzgodnienia z Zamawiającym.",
                                  "Forma i termin płatności do ustalenia stron."]):
        sec3.append(bullet(w))
    sec3.append(Spacer(1, 10))
    sig = Table([[Paragraph("……………………………………………", S["base"]), Paragraph("……………………………………………", S["base"])],
                 [Paragraph('<font size=8 color="#5B6B7B">Wystawił / Wykonawca</font>', S["small"]),
                  Paragraph('<font size=8 color="#5B6B7B">Zatwierdził / Zamawiający</font>', S["small"])]],
                colWidths=[CW * 0.5, CW * 0.5])
    sig.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, 0), 4), ("BOTTOMPADDING", (0, 0), (-1, 0), 2), ("TOPPADDING", (0, 1), (-1, 1), 0)]))
    sec3.append(sig)
    story.append(KeepTogether(sec3))

    # ---------- NAGŁÓWKI / STOPKA ----------
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
        c.setFillColor(CREAM); c.setFont("DJS-B", 22); c.drawRightString(x1 - 3 * mm, top - 8.5 * mm, tytul)
        c.setFillColor(HexColor("#C9D6E2")); c.setFont("DJS", 8.6)
        if numer:  c.drawRightString(x1 - 3 * mm, top - 14.5 * mm, f"Nr  {numer}")
        if data_w: c.drawRightString(x1 - 3 * mm, top - 19 * mm, f"Data wystawienia:  {data_w}")
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
        c.drawRightString(x1 - 3 * mm, bot + hh * 0.36, f"{tytul.capitalize()} {numer}  —  specyfikacja techniczna")
        _footer(c, doc)

    doc = BaseDocTemplate(out_path, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                          topMargin=12 * mm, bottomMargin=11 * mm,
                          title=f"{tytul} {numer} - {wy.get('nazwa','')}", author=wy.get("nazwa", ""))
    W, H = A4
    ff = Frame(18 * mm, 16 * mm, CW, H - 40 * mm - 16 * mm, id="ff",
               leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    fl = Frame(18 * mm, 16 * mm, CW, H - 26 * mm - 16 * mm, id="fl",
               leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="first", frames=[ff], onPage=draw_first),
                          PageTemplate(id="later", frames=[fl], onPage=draw_later)])
    doc.build(story)
    return out_path


if __name__ == "__main__":
    import json, sys
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(_HERE, "przyklad_dane.json")
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(_HERE, "przyklad_oferta.pdf")
    with open(src, encoding="utf-8") as f:
        generate_offer_pdf(json.load(f), out)
    print("OK ->", out)
