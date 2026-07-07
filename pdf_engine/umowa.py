# -*- coding: utf-8 -*-
"""
INSTAL-PAWEŁ — silnik umów (data -> PDF).

Jedna funkcja publiczna:  generate_umowa_pdf(data: dict, out_path: str)

Wygląd 1:1 z silnikiem wycen (pdf_engine/generator.py): ten sam granatowy
nagłówek "blueprint" z pomarańczową błyskawicą i wordmarkiem, ta sama paleta,
fonty DejaVu. Elementy graficzne są IMPORTOWANE z generator.py — niczego tam
nie zmieniamy.

Schemat `data`:
{
  "wystawca":    { jak w wycenie },
  "zamawiajacy": { "nazwa", "adres_html", "kontakt_html" },
  "meta":        { "tytul": "UMOWA", "numer": "01/07/2026",
                   "data": "07.07.2026", "miejscowosc": "Września" },
  "przedmiot":   "wykonanie instalacji elektrycznej ...",
  "zakres":      [ "punkt zakresu", ... ],                     // opcjonalne
  "termin_rozpoczecia": "15.07.2026",
  "termin_zakonczenia": "31.07.2026",
  "wynagrodzenie": { "kwota": 26820.0, "zaliczka": 5000.0,     // zaliczka opcjonalna
                     "platnosc": "przelewem ... w terminie 7 dni ..." },
  "gwarancja":   "24 miesiące",
  "dodatkowe":   [ "punkt", ... ],                             // opcjonalne
  "klauzula_vat": "tekst"                                      // opcjonalna (jest default)
}
Silnik sam liczy kwotę słownie (liczba_slownie z generator.py).
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Table, TableStyle,
                                Paragraph, Spacer, KeepTogether, NextPageTemplate)
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_JUSTIFY

# elementy wspólne marki — z gotowego silnika wycen (nie modyfikujemy go)
from pdf_engine.generator import (_ensure_fonts, _styles, _grid, _bolt,
                                  money, liczba_slownie,
                                  NAVY, ORANGE, BLUE, CREAM, LIGHT, ZEBRA,
                                  LINE, DARK, GREY, CW)


def generate_umowa_pdf(data, out_path):
    _ensure_fonts()
    S = _styles()
    # style tekstu umowy (justowane punkty z wiszącym numerem)
    S["pkt"] = ParagraphStyle("pkt", fontName="DJS", fontSize=9.2, leading=13.2,
                              textColor=DARK, alignment=TA_JUSTIFY,
                              leftIndent=16, firstLineIndent=-16, spaceAfter=4)
    S["pre"] = ParagraphStyle("pre", fontName="DJS", fontSize=9.4, leading=13.5,
                              textColor=DARK, alignment=TA_CENTER)

    wy   = data.get("wystawca", {})
    zam  = data.get("zamawiajacy", {})
    meta = data.get("meta", {})
    brand_word = wy.get("wordmark", "INSTAL-PAWEL")
    brand_sub  = wy.get("wordmark_sub", "USŁUGI ELEKTRYCZNE")
    tytul  = meta.get("tytul", "UMOWA")
    numer  = meta.get("numer", "")
    data_w = meta.get("data", "")
    miejsc = meta.get("miejscowosc", "")
    stopka = f'{wy.get("nazwa","INSTAL-PAWEŁ")} — Umowa {numer}'.strip(" —")

    wyn      = data.get("wynagrodzenie", {}) or {}
    kwota    = float(wyn.get("kwota") or 0)
    zaliczka = float(wyn.get("zaliczka") or 0)

    # ---------- helpers ----------
    def par_head(nr, title):
        """Nagłówek paragrafu: '§ 1. PRZEDMIOT UMOWY' z pomarańczową linią (jak sekcje wyceny)."""
        t = Table([[Paragraph(f"§ {nr}.&nbsp;&nbsp;{title}", S["sect"])]], colWidths=[CW])
        t.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 1.4, ORANGE),
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        return [t, Spacer(1, 6)]

    def punkty(teksty):
        """Numerowane punkty paragrafu (1., 2., ...)."""
        return [Paragraph(f"{i}.&nbsp;&nbsp;{t}", S["pkt"]) for i, t in enumerate(teksty, 1)]

    def bullet(t):
        return Paragraph('<font color="#F39200">▪</font>&nbsp; ' + t,
                         ParagraphStyle("bulU", parent=S["bul"], leftIndent=26, firstLineIndent=-9))

    # ---------- STORY ----------
    story = [NextPageTemplate("later")]

    # -- preambuła --
    # "w" / "we": "we" przed W/F + spółgłoska (we Wrześni, we Wrocławiu; ale: w Warszawie)
    przyimek = "we" if (len(miejsc) > 1 and miejsc[0].lower() in "wf"
                        and miejsc[1].lower() not in "aeiouyąę") else "w"
    gdzie = f' {przyimek} <b>{miejsc}</b>' if miejsc else ""
    story.append(Paragraph(f"zawarta w dniu <b>{data_w}</b>{gdzie} pomiędzy:", S["pre"]))
    story.append(Spacer(1, 8))

    # -- strony (identyczne karty jak w wycenie) --
    wyk = [Paragraph("WYKONAWCA", S["label"]), Spacer(1, 3),
           Paragraph(wy.get("nazwa", ""), S["partyName"])]
    if wy.get("podtytul"):
        wyk.append(Paragraph(f'<font size=7.5 color="#5B6B7B">{wy["podtytul"]}</font>', S["small"]))
    wyk.append(Spacer(1, 3))
    for ln in [f'NIP: {wy.get("nip","")}', f'Adres: {wy.get("adres","")}',
               f'Tel.: {wy.get("tel","")}', f'E-mail: {wy.get("email","")}']:
        wyk.append(Paragraph(ln, S["party"]))
    wyk += [Spacer(1, 4),
            Paragraph('<font size=8 color="#5B6B7B">zwanym dalej „Wykonawcą”</font>', S["small"])]

    zmk = [Paragraph("ZAMAWIAJĄCY", S["label"]), Spacer(1, 3),
           Paragraph(zam.get("nazwa", ""), S["partyName"]), Spacer(1, 2),
           Paragraph(zam.get("adres_html", ""), S["party"])]
    if zam.get("kontakt_html"):
        zmk += [Spacer(1, 4), Paragraph(zam["kontakt_html"], S["party"])]
    zmk += [Spacer(1, 4),
            Paragraph('<font size=8 color="#5B6B7B">zwanym dalej „Zamawiającym”</font>', S["small"])]

    parties = Table([[wyk, zmk]], colWidths=[CW * 0.5, CW * 0.5])
    parties.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, 0), ZEBRA), ("BACKGROUND", (1, 0), (1, 0), ZEBRA),
        ("BOX", (0, 0), (0, 0), 0.6, LINE), ("BOX", (1, 0), (1, 0), 0.6, LINE),
        ("LINEBEFORE", (0, 0), (0, 0), 2.5, ORANGE), ("LINEBEFORE", (1, 0), (1, 0), 2.5, BLUE),
        ("LEFTPADDING", (0, 0), (-1, -1), 11), ("RIGHTPADDING", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LINEAFTER", (0, 0), (0, 0), 6, colors.white)]))
    story += [parties, Spacer(1, 6),
              Paragraph('zwanymi dalej łącznie „Stronami”, o następującej treści:', S["pre"]),
              Spacer(1, 12)]

    nr = 1  # licznik paragrafów (część sekcji jest opcjonalna)

    # -- § Przedmiot umowy --
    story += par_head(nr, "PRZEDMIOT UMOWY"); nr += 1
    pkt = 1
    story.append(Paragraph(f'{pkt}.&nbsp;&nbsp;Zamawiający zleca, a Wykonawca przyjmuje do '
                           f'wykonania: <b>{data.get("przedmiot","")}</b>.', S["pkt"]))
    zakres = [z for z in (data.get("zakres") or []) if str(z).strip()]
    if zakres:
        pkt += 1
        story.append(Paragraph(f"{pkt}.&nbsp;&nbsp;Zakres prac obejmuje w szczególności:", S["pkt"]))
        story += [bullet(z) for z in zakres]
        story.append(Spacer(1, 2))
    pkt += 1
    story.append(Paragraph(f"{pkt}.&nbsp;&nbsp;Wykonawca wykona przedmiot umowy zgodnie z "
                           "obowiązującymi przepisami, normami oraz zasadami wiedzy technicznej "
                           "i sztuki budowlanej.", S["pkt"]))
    story.append(Spacer(1, 8))

    # -- § Termin realizacji --
    story += par_head(nr, "TERMIN REALIZACJI"); nr += 1
    story += punkty([
        f'Rozpoczęcie prac: <b>{data.get("termin_rozpoczecia") or "do uzgodnienia"}</b>.',
        f'Zakończenie prac: <b>{data.get("termin_zakonczenia") or "do uzgodnienia"}</b>.',
        "Zmiana terminów wymaga zgody obu Stron. Termin ulega przedłużeniu o czas trwania "
        "przeszkód niezależnych od Wykonawcy (w szczególności warunki atmosferyczne "
        "uniemożliwiające prace, opóźnienia dostaw materiałów, brak udostępnienia frontu robót)."])
    story.append(Spacer(1, 8))

    # -- § Wynagrodzenie --
    story += par_head(nr, "WYNAGRODZENIE I PŁATNOŚĆ"); nr += 1
    pw = [f'Za wykonanie przedmiotu umowy Strony ustalają wynagrodzenie w kwocie '
          f'<b>{money(kwota)}</b> (słownie: {liczba_slownie(kwota)}).']
    if zaliczka > 0:
        pw.append(f'Zamawiający wpłaci Wykonawcy zaliczkę w kwocie <b>{money(zaliczka)}</b> '
                  f'(słownie: {liczba_slownie(zaliczka)}) przed rozpoczęciem prac. '
                  f'Zaliczka zostanie rozliczona w płatności końcowej.')
    pw.append('Płatność: ' + (wyn.get("platnosc") or
              "przelewem na rachunek bankowy Wykonawcy lub gotówką, w terminie 7 dni od dnia "
              "odbioru prac i wystawienia faktury."))
    klauzula = data.get("klauzula_vat",
        "Robocizna (usługa montażu i uruchomienia) jest zwolniona z podatku VAT na podstawie "
        "<b>art. 113 ust. 1 (i ust. 9) ustawy z dnia 11 marca 2004 r. o podatku od towarów "
        "i usług</b> (zwolnienie podmiotowe) — do wartości robocizny nie dolicza się podatku VAT. "
        "Ceny materiałów podano w kwotach brutto (zawierają podatek VAT).")
    if klauzula:
        pw.append(klauzula)
    story += punkty(pw)
    # wyróżniona ramka z kwotą (jak "RAZEM DO ZAPŁATY" w wycenie)
    kt = Table([[Paragraph('<font color="#F5F1E6"><b>WYNAGRODZENIE ŁĄCZNIE:</b></font>',
                   ParagraphStyle("kw", fontName="DJS-B", fontSize=9.6, leading=12, textColor=CREAM)),
                 Paragraph('<font color="#F39200"><b>' + money(kwota) + '</b></font>',
                   ParagraphStyle("kwr", fontName="DJS-B", fontSize=11.5, leading=14,
                                  textColor=ORANGE, alignment=TA_RIGHT))]],
               colWidths=[52 * mm, 38 * mm])
    kt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("LINEBEFORE", (0, 0), (0, 0), 3, ORANGE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10)]))
    story.append(Spacer(1, 3))
    story.append(Table([["", kt]], colWidths=[CW - 90 * mm, 90 * mm],
        style=TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                          ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)])))
    story.append(Spacer(1, 8))

    # -- § Obowiązki stron --
    story += par_head(nr, "OBOWIĄZKI STRON"); nr += 1
    story += punkty([
        "Wykonawca zobowiązuje się do: wykonania prac z należytą starannością, zabezpieczenia "
        "miejsca prac, uporządkowania terenu po ich zakończeniu oraz przekazania Zamawiającemu "
        "niezbędnych protokołów i dokumentacji (w tym pomiarów elektrycznych, jeśli dotyczą).",
        "Zamawiający zobowiązuje się do: udostępnienia miejsca prac i dostępu do energii "
        "elektrycznej, współdziałania przy realizacji umowy oraz terminowej zapłaty wynagrodzenia.",
        "Odbiór prac zostanie potwierdzony przez Strony (protokół odbioru lub potwierdzenie "
        "na fakturze). Zgłoszone przy odbiorze usterki Wykonawca usunie w uzgodnionym terminie."])
    story.append(Spacer(1, 8))

    # -- § Gwarancja --
    story += par_head(nr, "GWARANCJA I RĘKOJMIA"); nr += 1
    story += punkty([
        f'Wykonawca udziela gwarancji na wykonane prace na okres '
        f'<b>{data.get("gwarancja") or "24 miesiące"}</b> od dnia odbioru.',
        "Gwarancja nie obejmuje uszkodzeń wynikających z niewłaściwej eksploatacji, ingerencji "
        "osób trzecich ani zdarzeń losowych. Na materiały i urządzenia obowiązuje gwarancja "
        "ich producentów.",
        "Wady ujawnione w okresie gwarancji Wykonawca usunie bezpłatnie w terminie uzgodnionym "
        "z Zamawiającym."])
    story.append(Spacer(1, 8))

    # -- § Postanowienia dodatkowe (opcjonalne) --
    dodatkowe = [d for d in (data.get("dodatkowe") or []) if str(d).strip()]
    if dodatkowe:
        story += par_head(nr, "POSTANOWIENIA DODATKOWE"); nr += 1
        story += punkty(dodatkowe)
        story.append(Spacer(1, 8))

    # -- § Postanowienia końcowe + podpisy (trzymane razem) --
    koncowe = par_head(nr, "POSTANOWIENIA KOŃCOWE")
    koncowe += punkty([
        "Wszelkie zmiany niniejszej umowy wymagają formy pisemnej pod rygorem nieważności.",
        "W sprawach nieuregulowanych umową zastosowanie mają przepisy Kodeksu cywilnego.",
        "Umowę sporządzono w dwóch jednobrzmiących egzemplarzach, po jednym dla każdej ze Stron."])
    koncowe.append(Spacer(1, 26))
    sig = Table([[Paragraph("……………………………………………", S["base"]),
                  Paragraph("……………………………………………", S["base"])],
                 [Paragraph('<font size=8 color="#5B6B7B"><b>WYKONAWCA</b></font>', S["small"]),
                  Paragraph('<font size=8 color="#5B6B7B"><b>ZAMAWIAJĄCY</b></font>', S["small"])]],
                colWidths=[CW * 0.5, CW * 0.5])
    sig.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, 0), 4), ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
        ("TOPPADDING", (0, 1), (-1, 1), 0)]))
    koncowe.append(sig)
    story.append(KeepTogether(koncowe))

    # ---------- NAGŁÓWKI / STOPKA (identyczna grafika jak w wycenie) ----------
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
        if data_w: c.drawRightString(x1 - 3 * mm, top - 19 * mm, f"Data zawarcia:  {data_w}")
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
        c.drawRightString(x1 - 3 * mm, bot + hh * 0.36, f"Umowa {numer}")
        _footer(c, doc)

    doc = BaseDocTemplate(out_path, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                          topMargin=12 * mm, bottomMargin=11 * mm,
                          title=f"Umowa {numer} - {wy.get('nazwa','')}", author=wy.get("nazwa", ""))
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
    # Podgląd przykładowej umowy:  python -m pdf_engine.umowa
    import os
    przyklad = {
        "wystawca": {"nazwa": "INSTAL-PAWEL — Usługi Elektryczne", "podtytul": "Paweł Kowalski",
                     "wordmark": "INSTAL-PAWEL", "wordmark_sub": "USŁUGI ELEKTRYCZNE",
                     "nip": "000-000-00-00", "adres": "ul. Przykładowa 1, 62-300 Września",
                     "tel": "500 100 200", "email": "instal.pawel@example.com"},
        "zamawiajacy": {"nazwa": "Jan Nowak", "adres_html": "ul. Ogrodowa 12<br/>62-300 Września",
                        "kontakt_html": "tel. 600 100 200"},
        "meta": {"tytul": "UMOWA", "numer": "01/07/2026", "data": "07.07.2026",
                 "miejscowosc": "Wrześni"},
        "przedmiot": "wykonanie instalacji elektrycznej w budynku mieszkalnym jednorodzinnym "
                     "przy ul. Ogrodowej 12 we Wrześni",
        "zakres": ["ułożenie okablowania i osprzętu wg ustaleń z Zamawiającym",
                   "montaż rozdzielnicy wraz z zabezpieczeniami",
                   "montaż gniazd, łączników i punktów oświetleniowych",
                   "pomiary elektryczne i protokół pomiarowy"],
        "termin_rozpoczecia": "15.07.2026", "termin_zakonczenia": "31.07.2026",
        "wynagrodzenie": {"kwota": 18500, "zaliczka": 5000},
        "gwarancja": "24 miesiące",
        "dodatkowe": ["Materiały dostarcza Wykonawca w ramach wynagrodzenia."],
    }
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "przyklad_umowa.pdf")
    generate_umowa_pdf(przyklad, out)
    print("OK ->", out)
