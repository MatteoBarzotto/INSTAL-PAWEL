# -*- coding: utf-8 -*-
"""
Warstwa łącząca aplikację z silnikiem PDF.

`build_data(...)` składa słownik `data` dokładnie wg schematu z CLAUDE.md
(NIE liczy sumy ani "słownie" — robi to silnik). `generate(...)` wywołuje
`generate_offer_pdf`.
"""
import os
import json
import datetime

from pdf_engine.generator import generate_offer_pdf
from pdf_engine.umowa import generate_umowa_pdf

HERE = os.path.dirname(os.path.abspath(__file__))


def dzis():
    return datetime.date.today().strftime("%d.%m.%Y")


def build_data(settings, client, meta, przedmiot, pozycje, robocizna,
               spec_techniczna=None, konstrukcja=None, materialy=None,
               warunki=None, klauzula="", uslugi_dodatkowe=None):
    """Buduje słownik `data` dla silnika PDF. Puste sekcje są pomijane."""
    data = {
        "wystawca": {
            "nazwa": settings["nazwa"], "podtytul": settings["podtytul"],
            "wordmark": settings["wordmark"], "wordmark_sub": settings["wordmark_sub"],
            "nip": settings["nip"], "adres": settings["adres"],
            "tel": settings["tel"], "email": settings["email"],
        },
        "zamawiajacy": {
            "nazwa": client.get("nazwa", ""),
            "adres_html": client.get("adres_html", ""),
            "kontakt_html": client.get("kontakt_html", ""),
        },
        "meta": {
            "tytul": meta.get("tytul", "WYCENA"),
            "numer": meta.get("numer", ""),
            "data": meta.get("data", dzis()),
        },
        "pozycje": pozycje,
    }
    if przedmiot:
        data["przedmiot"] = przedmiot
    if robocizna and float(robocizna.get("kwota", 0)) > 0:
        data["robocizna"] = robocizna
    if uslugi_dodatkowe:
        data["uslugi_dodatkowe"] = uslugi_dodatkowe
    if spec_techniczna:
        data["spec_techniczna"] = spec_techniczna
    if konstrukcja:
        data["konstrukcja"] = konstrukcja
    if materialy:
        data["materialy_pomocnicze"] = materialy
    if warunki:
        data["warunki"] = warunki
    if klauzula:
        data["klauzula_vat"] = klauzula
    return data


def generate(data, out_path):
    """Generuje PDF; tworzy folder docelowy jeśli nie istnieje."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    return generate_offer_pdf(data, out_path)


def bezpieczna_nazwa(tekst):
    """Nazwa pliku bez znaków problematycznych (numer wyceny NN/MM/RRRR -> NN-MM-RRRR)."""
    out = "".join(c if c.isalnum() or c in " -_." else "-" for c in tekst).strip()
    return out or "wycena"


def out_path_for(settings, numer):
    folder = settings["pdf_folder"] or os.path.join(os.path.expanduser("~"), "Wyceny-InstalPawel")
    return os.path.join(folder, f"Wycena_{bezpieczna_nazwa(numer)}.pdf")


def generate_umowa(data, out_path):
    """Generuje PDF umowy; tworzy folder docelowy jeśli nie istnieje."""
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    return generate_umowa_pdf(data, out_path)


def out_path_umowa(settings, numer):
    folder = settings["pdf_folder"] or os.path.join(os.path.expanduser("~"), "Wyceny-InstalPawel")
    return os.path.join(folder, f"Umowa_{bezpieczna_nazwa(numer) or 'umowa'}.pdf")
