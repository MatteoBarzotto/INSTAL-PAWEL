# -*- coding: utf-8 -*-
"""
Model danych aplikacji INSTAL-PAWEŁ (SQLite).

Jeden plik: `dane.db`. Tabele: settings, clients, products, boms, quotes.
Przy pierwszym uruchomieniu baza jest tworzona i zasilana danymi z
`pdf_engine/przyklad_dane.json`, żeby Paweł od razu mógł odtworzyć ofertę BUDMAX.
"""
import os
import re
import json
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "dane.db")
PRZYKLAD = os.path.join(HERE, "pdf_engine", "przyklad_dane.json")


def get_db():
    """Połączenie z bazą; wiersze jako słowniki (sqlite3.Row)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    nazwa TEXT, podtytul TEXT, wordmark TEXT, wordmark_sub TEXT,
    nip TEXT, adres TEXT, tel TEXT, email TEXT,
    klauzula_vat TEXT,
    warunki_json TEXT,                 -- lista domyślnych punktów "Warunki"
    materialy_json TEXT,               -- domyślne "materiały pomocnicze" (lista bullet_html)
    pdf_folder TEXT
);

CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nazwa TEXT NOT NULL,
    adres_html TEXT,
    kontakt_html TEXT
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nazwa TEXT NOT NULL,
    kategoria TEXT,
    jm TEXT,                           -- jednostka miary (szt., zest., kpl. ...)
    cena_brutto REAL DEFAULT 0,
    vat INTEGER DEFAULT 1,             -- 1 = cena zawiera VAT (brutto)
    spec_json TEXT                     -- opcjonalna specyfikacja: lista [klucz, wartosc]
);

CREATE TABLE IF NOT EXISTS boms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nazwa TEXT NOT NULL,               -- nazwa robocza zestawu (do listy)
    tytul TEXT,                        -- tytuł sekcji w PDF
    opis_json TEXT,                    -- lista bullet_html
    naglowek_wykazu TEXT,
    elementy_json TEXT,                -- lista [symbol, nazwa, ilosc, jm]
    nota TEXT
);

CREATE TABLE IF NOT EXISTS quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numer TEXT,
    data TEXT,
    client_id INTEGER,
    client_nazwa TEXT,
    suma REAL DEFAULT 0,
    data_json TEXT,                    -- kompletny słownik `data` dla silnika PDF
    status TEXT DEFAULT 'szkic',       -- szkic / wysłana / zaakceptowana / odrzucona
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numer TEXT,                        -- np. "01/07/2026" (własna numeracja umów)
    data TEXT,                         -- data zawarcia (tekst dd.mm.rrrr)
    client_id INTEGER,
    client_nazwa TEXT,
    kwota REAL DEFAULT 0,              -- wynagrodzenie łączne (do listy)
    data_json TEXT,                    -- kompletny słownik `data` dla pdf_engine/umowa.py
    status TEXT DEFAULT 'szkic',       -- szkic / podpisana / zakończona
    created_at TEXT DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numer TEXT,                        -- np. "30/2026" (numeracja ciągła w roku)
    wyst_date TEXT,                    -- data wystawienia (ISO)
    sprz_date TEXT,                    -- data sprzedaży (ISO) — o miesiącu rozliczenia decyduje ta data
    term_date TEXT,                    -- termin płatności (ISO) — do wykrywania "po terminie"
    nabywca TEXT,                      -- nazwa nabywcy (do listy)
    suma REAL DEFAULT 0,
    data_json TEXT,                    -- pełny stan faktury (kontrakt zbierzStan(): fields/items/toggles)
    status TEXT DEFAULT 'niezapłacona',-- niezapłacona / zapłacona
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
"""


def _migrate(conn):
    """Dodaje brakujące kolumny w istniejących bazach (starsze wersje programu)."""
    def addcol(table, col, ddl):
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        if col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
            return True
        return False
    addcol("quotes", "status", "status TEXT DEFAULT 'szkic'")
    addcol("invoices", "status", "status TEXT DEFAULT 'niezapłacona'")
    addcol("invoices", "term_date", "term_date TEXT")
    # sprz_date: data sprzedaży (decyduje o miesiącu rozliczenia; puste = jak wystawienia)
    if addcol("invoices", "sprz_date", "sprz_date TEXT"):
        for r in conn.execute("SELECT id, wyst_date, data_json FROM invoices").fetchall():
            try:
                sprz = (json.loads(r[2] or "{}").get("fields", {}).get("m_sprz") or "").strip()
            except (ValueError, TypeError):
                sprz = ""
            conn.execute("UPDATE invoices SET sprz_date=? WHERE id=?", (sprz or r[1] or "", r[0]))
    # osoba_fiz: 1 = nabywca to osoba fizyczna bez NIP (limit kasy fiskalnej 20 000 zł/rok)
    if addcol("invoices", "osoba_fiz", "osoba_fiz INTEGER DEFAULT 0"):
        # uzupełnij istniejące faktury: brak NIP nabywcy = osoba fizyczna
        for r in conn.execute("SELECT id, data_json FROM invoices").fetchall():
            try:
                stan = json.loads(r[1] or "{}")
                nip = (stan.get("fields", {}).get("n_nip") or "").strip()
            except (ValueError, TypeError):
                nip = "x"  # nie da się ocenić — zostaw 0
            if not nip:
                conn.execute("UPDATE invoices SET osoba_fiz=1 WHERE id=?", (r[0],))
    conn.commit()


def init_db():
    """Tworzy schemat i (jeśli baza pusta) zasila danymi przykładowymi."""
    conn = get_db()
    conn.executescript(SCHEMA)
    conn.commit()
    _migrate(conn)
    if conn.execute("SELECT COUNT(*) AS c FROM settings").fetchone()["c"] == 0:
        _seed(conn)
    conn.close()


def _seed(conn):
    """Dane startowe z przyklad_dane.json (wystawca, klient BUDMAX, katalog, BOM)."""
    with open(PRZYKLAD, encoding="utf-8") as f:
        d = json.load(f)

    wy = d["wystawca"]
    conn.execute(
        """INSERT INTO settings
           (id, nazwa, podtytul, wordmark, wordmark_sub, nip, adres, tel, email,
            klauzula_vat, warunki_json, materialy_json, pdf_folder)
           VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (wy["nazwa"], wy.get("podtytul", ""), wy.get("wordmark", "INSTAL-PAWEL"),
         wy.get("wordmark_sub", "USŁUGI ELEKTRYCZNE"), wy.get("nip", ""), wy.get("adres", ""),
         wy.get("tel", ""), wy.get("email", ""),
         "",  # pusta klauzula = użyj sensownego domyślnego tekstu z silnika (art. 113)
         json.dumps(d.get("warunki", []), ensure_ascii=False),
         json.dumps(d.get("materialy_pomocnicze", []), ensure_ascii=False),
         os.path.join(os.path.expanduser("~"), "Wyceny-InstalPawel")),
    )

    # Klient BUDMAX
    zam = d["zamawiajacy"]
    conn.execute("INSERT INTO clients (nazwa, adres_html, kontakt_html) VALUES (?,?,?)",
                 (zam["nazwa"], zam.get("adres_html", ""), zam.get("kontakt_html", "")))

    # Katalog produktów: łączymy pozycje z blokami specyfikacji technicznej (po kolejności).
    # Bloki spec_techniczna odpowiadają pierwszym 4 pozycjom (moduły, inwertery, akum., rozdzielnice).
    spec = d.get("spec_techniczna", [])
    for i, poz in enumerate(d.get("pozycje", [])):
        ilosc = str(poz.get("ilosc", ""))
        # jednostka miary z tekstu ilości ("8 szt." -> "szt.")
        jm = ilosc.split(" ", 1)[1] if " " in ilosc else ilosc
        parametry = None
        if i < len(spec):
            # pomijamy wiersze zależne od konkretnego zamówienia (Ilość) — katalog ma być uniwersalny
            params = [kv for kv in spec[i]["parametry"] if kv[0].strip().lower() != "ilość"]
            parametry = json.dumps(params, ensure_ascii=False)
        conn.execute(
            "INSERT INTO products (nazwa, kategoria, jm, cena_brutto, vat, spec_json) VALUES (?,?,?,?,?,?)",
            (poz["nazwa"], "Materiały", jm or "szt.", float(poz["brutto"]), 1, parametry))

    # Cennik robocizny (kategoria "Robocizna" — vat=0, bo robocizna zwolniona z VAT).
    # Ceny startowe do poprawienia przez użytkownika w Katalogu.
    for nazwa, jm, cena in [
        ("Punkt oświetleniowy (montaż)", "szt.", 90),
        ("Gniazdo 230 V (montaż)", "szt.", 60),
        ("Łącznik światła (montaż)", "szt.", 60),
        ("Pomiary elektryczne instalacji", "kpl.", 300),
        ("Roboczogodzina", "godz.", 100),
    ]:
        conn.execute(
            "INSERT INTO products (nazwa, kategoria, jm, cena_brutto, vat, spec_json) VALUES (?,?,?,?,?,?)",
            (nazwa, "Robocizna", jm, cena, 0, None))

    # BOM: konstrukcja BAKS
    k = d.get("konstrukcja")
    if k:
        conn.execute(
            """INSERT INTO boms (nazwa, tytul, opis_json, naglowek_wykazu, elementy_json, nota)
               VALUES (?,?,?,?,?,?)""",
            ("Konstrukcja wsporcza – system BAKS", k.get("tytul", ""),
             json.dumps(k.get("opis", []), ensure_ascii=False),
             # nagłówek bez końcówki "(N zestawy)" — liczba zestawów dokleja się z mnożnika w aplikacji
             re.sub(r"\s*\(.*\)\s*$", "", k.get("naglowek_wykazu", "")) or "Wykaz elementów konstrukcji",
             json.dumps(k.get("elementy", []), ensure_ascii=False),
             k.get("nota", "")))

    conn.commit()


if __name__ == "__main__":
    # Ręczne (re)utworzenie bazy: python db.py
    init_db()
    print("Baza gotowa ->", DB_PATH)
