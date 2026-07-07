# -*- coding: utf-8 -*-
"""
INSTAL-PAWEŁ — lokalna aplikacja do wycen/ofert PDF.

Uruchomienie:  python app.py  ->  http://127.0.0.1:8000
Wszystko działa lokalnie i offline. Silnik PDF: pdf_engine/generator.py.
"""
import os
import sys
import json
import subprocess
import datetime

from flask import (Flask, request, redirect, url_for, render_template,
                   jsonify, flash, abort)

import db
import pdf_service
import updater

app = Flask(__name__)
app.secret_key = "instal-pawel-local"  # tylko dla flash() – aplikacja lokalna, bez logowania

db.init_db()


def _auto_backup():
    """Automatyczna kopia bazy raz dziennie przy starcie programu.
    Pliki `dane_auto_RRRR-MM-DD.db` w „Kopie zapasowe/auto", trzymamy 10 ostatnich."""
    import sqlite3
    try:
        conn = db.get_db()
        st = conn.execute("SELECT * FROM settings WHERE id=1").fetchone()
        conn.close()
        folder = os.path.join(
            (st["pdf_folder"] if st else "") or os.path.join(os.path.expanduser("~"), "Wyceny-InstalPawel"),
            "Kopie zapasowe", "auto")
        os.makedirs(folder, exist_ok=True)
        cel = os.path.join(folder, "dane_auto_" + datetime.date.today().strftime("%Y-%m-%d") + ".db")
        if os.path.exists(cel):
            return  # dzisiejsza kopia już jest
        src = db.get_db()
        dst = sqlite3.connect(cel)
        src.backup(dst)
        dst.close()
        src.close()
        stare = sorted(f for f in os.listdir(folder) if f.startswith("dane_auto_") and f.endswith(".db"))
        for f in stare[:-10]:
            os.remove(os.path.join(folder, f))
    except Exception:
        pass  # kopia nie może zablokować startu programu


_auto_backup()


def _import_faktur():
    """Jednorazowy import faktur archiwalnych (wystawionych poza programem).

    Plik `import_faktur.json` obok app.py — lista wpisów:
      { "numer", "wyst_date" (RRRR-MM-DD), "sprz_date" (opc., domyślnie=wyst_date),
        "term_date" (opc.), "nabywca", "nip" (opc.), "adres" (opc.),
        "kwota", "osoba_fiz" (0/1), "status" ("zapłacona"/"niezapłacona"),
        "opis" (opcjonalna nazwa pozycji) }
    Import jest bezpieczny przy każdym starcie: faktura o numerze, który już
    jest w bazie, zostaje pominięta. Dzięki temu plik może przyjechać
    z aktualizacją programu i niczego nie zdubluje.
    """
    plik = os.path.join(os.path.dirname(os.path.abspath(__file__)), "import_faktur.json")
    if not os.path.exists(plik):
        return
    try:
        with open(plik, encoding="utf-8") as f:
            wpisy = json.load(f)
    except (OSError, ValueError):
        return
    conn = db.get_db()
    dodane = 0
    for w in wpisy or []:
        numer = (w.get("numer") or "").strip()
        if not numer:
            continue
        if conn.execute("SELECT 1 FROM invoices WHERE numer=?", (numer,)).fetchone():
            continue  # już jest — nie dubluj
        kwota = float(w.get("kwota") or 0)
        opis = w.get("opis") or "Usługa elektryczna (faktura archiwalna, wystawiona poza programem)"
        sprz = w.get("sprz_date") or w.get("wyst_date", "")
        stan = {
            "fields": {"m_numer": numer, "m_wyst": w.get("wyst_date", ""),
                       "m_sprz": sprz, "m_term": w.get("term_date", ""),
                       "n_nazwa": w.get("nabywca", ""), "n_adres": w.get("adres", ""),
                       "n_nip": w.get("nip", ""), "n_regon": ""},
            "items": [{"nazwa": opis, "ilosc": "1", "jm": "usł.",
                       "cena": f"{kwota:.2f}".replace(".", ",")}],
            "toggles": {"blueprint": True, "regon": False, "bank": True, "klauzula": True,
                        "osoba_fiz": bool(w.get("osoba_fiz"))},
        }
        conn.execute(
            """INSERT INTO invoices (numer, wyst_date, sprz_date, term_date, nabywca, suma, osoba_fiz, status, data_json)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (numer, w.get("wyst_date", ""), sprz, w.get("term_date", ""), w.get("nabywca", ""),
             kwota, 1 if w.get("osoba_fiz") else 0, w.get("status") or "zapłacona",
             json.dumps(stan, ensure_ascii=False)))
        dodane += 1
    conn.commit()
    conn.close()
    if dodane:
        print(f"  Zaimportowano {dodane} faktur archiwalnych z import_faktur.json.")


_import_faktur()


# ------------------------------------------------------------------ pomocnicze
def _settings(conn):
    return conn.execute("SELECT * FROM settings WHERE id=1").fetchone()


def _next_numer(conn, when=None):
    """Kolejny numer w formacie NN/MM/RRRR (auto-inkrement w obrębie miesiąca)."""
    when = when or datetime.date.today()
    suffix = when.strftime("/%m/%Y")
    n = 0
    for r in conn.execute("SELECT numer FROM quotes WHERE numer LIKE ?", ("%" + suffix,)):
        try:
            n = max(n, int(str(r["numer"]).split("/", 1)[0]))
        except (ValueError, IndexError):
            pass
    return f"{n + 1:02d}{suffix}"


def _next_faktura_numer(conn, when=None):
    """Kolejny numer faktury 'NN/RRRR' — numeracja ciągła w roku (tak jak w papierowej
    ewidencji Pawła: 01/2026, 02/2026, ...). Patrzy na najwyższy numer z bieżącego roku,
    rozumie też stary format programu 'FV / NN / MM / RRRR'."""
    import re
    when = when or datetime.date.today()
    yyyy = when.strftime("%Y")
    n = 0
    for r in conn.execute("SELECT numer FROM invoices WHERE numer LIKE ?", ("%" + yyyy,)):
        numer = str(r["numer"]).strip()
        m = re.match(r"^(\d+)\s*/\s*" + yyyy + "$", numer)          # 30/2026
        if m:
            n = max(n, int(m.group(1)))
            continue
        m = re.match(r"^FV\s*/\s*(\d+)\s*/\s*\d{2}\s*/\s*" + yyyy + "$", numer)  # FV / 01 / 07 / 2026
        if m:
            n = max(n, int(m.group(1)))
    return f"{n + 1:02d}/{yyyy}"


def _parse_num(v):
    """'12,50' / '1 200' -> float (odpowiednik parseNum z lib/kwoty.js)."""
    s = "".join(str(v).split()).replace(",", ".")  # usuń wszelkie białe znaki (też NBSP)
    try:
        return float(s or 0)
    except (ValueError, TypeError):
        return 0.0


def _suma_items(items):
    """Do zapłaty = Σ (ilość × cena). Bez VAT (sprzedawca zwolniony)."""
    return sum(_parse_num(it.get("ilosc")) * _parse_num(it.get("cena")) for it in (items or []))


def _open_file(path):
    """Otwiera plik domyślnym programem systemu (PDF Pawła na jego komputerze)."""
    if os.environ.get("NO_OPEN"):
        return True
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
        elif os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except Exception:
        return False


def money(v):
    return f"{float(v):,.2f}".replace(",", " ").replace(".", ",") + " zł"


app.jinja_env.filters["money"] = money
app.jinja_env.filters["from_json"] = lambda s: json.loads(s or "[]")


# ------------------------------------------------------------------ budowa data + zapis
def _assemble(conn, payload):
    """Z payloadu formularza buduje słownik `data` dla silnika oraz sumę do listy."""
    st = _settings(conn)

    # klient: istniejący (client_id) lub dane wpisane ręcznie (client)
    client = {}
    cid = payload.get("client_id")
    if cid:
        row = conn.execute("SELECT * FROM clients WHERE id=?", (cid,)).fetchone()
        if row:
            client = dict(row)
    if not client:
        client = payload.get("client", {}) or {}

    # pozycje + specyfikacja techniczna
    pozycje, spec = [], []
    for p in payload.get("pozycje", []):
        nazwa = (p.get("nazwa") or "").strip()
        if not nazwa:
            continue
        brutto = float(p.get("brutto") or 0)
        pozycje.append({"nazwa": nazwa, "ilosc": p.get("ilosc", ""), "brutto": brutto})
        if p.get("spec") and p.get("include_spec", True):
            spec.append({"tytul": p.get("spec_tytul") or nazwa, "parametry": p["spec"]})

    # robocizna
    rob = None
    r = payload.get("robocizna") or {}
    if float(r.get("kwota") or 0) > 0:
        rob = {"opis": r.get("opis", "Robocizna"),
               "kwota": float(r["kwota"]),
               "vat_zwolniona": bool(r.get("vat_zwolniona", True))}

    # konstrukcja (BOM) z mnożnikiem ×N
    konstr = None
    if payload.get("include_konstrukcja") and payload.get("bom_id"):
        b = conn.execute("SELECT * FROM boms WHERE id=?", (payload["bom_id"],)).fetchone()
        if b:
            mult = int(payload.get("mnoznik") or 1)
            elementy = json.loads(b["elementy_json"] or "[]")
            if mult != 1:
                mnozone = []
                for e in elementy:
                    sym, nz, il, jm = (list(e) + ["", "", "", ""])[:4]
                    try:
                        il = str(int(il) * mult)
                    except (ValueError, TypeError):
                        pass
                    mnozone.append([sym, nz, il, jm])
                elementy = mnozone
            konstr = {
                "tytul": b["tytul"] or b["nazwa"],
                "opis": json.loads(b["opis_json"] or "[]"),
                "naglowek_wykazu": (b["naglowek_wykazu"] or "Wykaz elementów konstrukcji")
                                   + (f" (×{mult})" if mult != 1 else ""),
                "elementy": elementy,
                "nota": b["nota"] or "",
            }

    # materiały pomocnicze
    materialy = payload.get("materialy") if payload.get("include_materialy") else None
    materialy = [m for m in (materialy or []) if str(m).strip()]

    warunki = [w for w in (payload.get("warunki") or []) if str(w).strip()] or None

    meta = {"tytul": payload.get("tytul") or "WYCENA",
            "numer": payload.get("numer") or "",
            "data": payload.get("data") or pdf_service.dzis()}

    data = pdf_service.build_data(
        st, client, meta, payload.get("przedmiot", ""), pozycje, rob,
        spec_techniczna=spec or None, konstrukcja=konstr,
        materialy=materialy or None, warunki=warunki)

    suma = sum(p["brutto"] for p in pozycje) + (rob["kwota"] if rob else 0)
    return data, suma, client


# ------------------------------------------------------------------ EKRAN: pulpit
# Limit zwolnienia podmiotowego z VAT (art. 113 ust. 1) — wartość sprzedaży w roku.
LIMIT_VAT = 200_000.0
# Limit zwolnienia z kasy fiskalnej — sprzedaż dla osób fizycznych bez działalności (rok).
LIMIT_KASA = 20_000.0


@app.route("/")
def index():
    """Pulpit: faktury po terminie, obrót roczny vs limit VAT, ostatnie dokumenty."""
    conn = db.get_db()
    dzis_iso = datetime.date.today().strftime("%Y-%m-%d")
    rok = datetime.date.today().strftime("%Y")
    miesiac = datetime.date.today().strftime("%Y-%m")
    po_terminie = conn.execute(
        """SELECT * FROM invoices WHERE status='niezapłacona'
           AND term_date IS NOT NULL AND term_date != '' AND term_date < ?
           ORDER BY term_date""", (dzis_iso,)).fetchall()
    niezaplacone = conn.execute(
        "SELECT COUNT(*) AS c, COALESCE(SUM(suma),0) AS s FROM invoices WHERE status='niezapłacona'"
    ).fetchone()
    # o miesiącu/roku rozliczenia decyduje data sprzedaży (gdy pusta — data wystawienia)
    data_rozl = "COALESCE(NULLIF(sprz_date,''), wyst_date)"
    obrot_rok = conn.execute(
        f"SELECT COALESCE(SUM(suma),0) AS s FROM invoices WHERE {data_rozl} LIKE ?",
        (rok + "-%",)).fetchone()["s"]
    obrot_mies = conn.execute(
        f"SELECT COALESCE(SUM(suma),0) AS s FROM invoices WHERE {data_rozl} LIKE ?",
        (miesiac + "-%",)).fetchone()["s"]
    obrot_osfiz = conn.execute(
        f"SELECT COALESCE(SUM(suma),0) AS s FROM invoices WHERE osoba_fiz=1 AND {data_rozl} LIKE ?",
        (rok + "-%",)).fetchone()["s"]
    # ostatnie dokumenty (wszystkie typy razem, wg czasu utworzenia)
    ostatnie = []
    for typ, sql, edytuj in [
        ("wycena", "SELECT id, numer, client_nazwa AS kto, suma AS kwota, status, created_at FROM quotes", "wycena_edytuj"),
        ("umowa", "SELECT id, numer, client_nazwa AS kto, kwota, status, created_at FROM contracts", "umowa_edytuj"),
        ("faktura", "SELECT id, numer, nabywca AS kto, suma AS kwota, status, created_at FROM invoices", "faktura_edytuj"),
    ]:
        for r in conn.execute(sql + " ORDER BY id DESC LIMIT 8"):
            d = dict(r)
            d["typ"] = typ
            d["edytuj"] = edytuj
            ostatnie.append(d)
    ostatnie.sort(key=lambda d: d.get("created_at") or "", reverse=True)
    conn.close()
    procent_vat = min(100.0, obrot_rok / LIMIT_VAT * 100)
    procent_kasa = min(100.0, obrot_osfiz / LIMIT_KASA * 100)
    return render_template("pulpit.html",
                           po_terminie=po_terminie, niezaplacone=niezaplacone,
                           obrot_rok=obrot_rok, obrot_mies=obrot_mies,
                           obrot_osfiz=obrot_osfiz, limit_kasa=LIMIT_KASA, procent_kasa=procent_kasa,
                           limit_vat=LIMIT_VAT, procent_vat=procent_vat,
                           rok=rok, ostatnie=ostatnie[:8], dzis_iso=dzis_iso)


# ------------------------------------------------------------------ EKRAN: lista wycen
@app.route("/wyceny")
def wyceny():
    conn = db.get_db()
    quotes = conn.execute(
        "SELECT * FROM quotes ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("wyceny.html", quotes=quotes)


# ------------------------------------------------------------------ EKRAN: nowa / edycja wyceny
@app.route("/wycena/nowa")
def wycena_nowa():
    conn = db.get_db()
    ctx = _editor_context(conn, None)
    conn.close()
    return render_template("wycena.html", **ctx)


@app.route("/wycena/<int:qid>/edytuj")
def wycena_edytuj(qid):
    conn = db.get_db()
    q = conn.execute("SELECT * FROM quotes WHERE id=?", (qid,)).fetchone()
    if not q:
        conn.close()
        abort(404)
    ctx = _editor_context(conn, q)
    conn.close()
    return render_template("wycena.html", **ctx)


def _editor_context(conn, q):
    st = _settings(conn)
    clients = conn.execute("SELECT * FROM clients ORDER BY nazwa").fetchall()
    products = conn.execute("SELECT * FROM products ORDER BY kategoria, nazwa").fetchall()
    boms = conn.execute("SELECT * FROM boms ORDER BY nazwa").fetchall()
    # cennik robocizny (kategoria "Robocizna") osobno — trafia do sekcji Robocizna, nie do pozycji
    materialy = [dict(p) for p in products if (p["kategoria"] or "") != "Robocizna"]
    robocizna_cennik = [dict(p) for p in products if (p["kategoria"] or "") == "Robocizna"]
    # istniejąca wycena -> przekazujemy zapisany data_json do wypełnienia formularza
    quote_data = json.loads(q["data_json"]) if q and q["data_json"] else None
    return {
        "q": q,
        "quote_data": quote_data,
        "clients": clients,
        "products": materialy,
        "robocizna_cennik": robocizna_cennik,
        "boms": [dict(b) for b in boms],
        "settings": st,
        "domyslny_numer": q["numer"] if q else _next_numer(conn),
        "dzis": pdf_service.dzis(),
        "domyslne_warunki": json.loads(st["warunki_json"] or "[]"),
        "domyslne_materialy": json.loads(st["materialy_json"] or "[]"),
    }


# ------------------------------------------------------------------ API: zapis wyceny
@app.route("/api/wycena/zapisz", methods=["POST"])
def api_wycena_zapisz():
    payload = request.get_json(force=True)
    conn = db.get_db()
    data, suma, client = _assemble(conn, payload)
    # Zapamiętujemy surowy stan formularza (silnik PDF ignoruje nieznane klucze),
    # dzięki czemu edycja/duplikat odtwarzają formularz dokładnie tak, jak był.
    data["_form"] = payload
    data_json = json.dumps(data, ensure_ascii=False)
    qid = payload.get("id")
    numer = data["meta"]["numer"]
    dt = data["meta"]["data"]
    cid = payload.get("client_id") or None
    cnaz = client.get("nazwa", "")
    if qid:
        conn.execute(
            """UPDATE quotes SET numer=?, data=?, client_id=?, client_nazwa=?, suma=?, data_json=?
               WHERE id=?""",
            (numer, dt, cid, cnaz, suma, data_json, qid))
    else:
        cur = conn.execute(
            """INSERT INTO quotes (numer, data, client_id, client_nazwa, suma, data_json)
               VALUES (?,?,?,?,?,?)""",
            (numer, dt, cid, cnaz, suma, data_json))
        qid = cur.lastrowid
    conn.commit()
    conn.close()
    return jsonify(ok=True, id=qid)


# ------------------------------------------------------------------ API: generuj PDF
@app.route("/api/wycena/<int:qid>/pdf", methods=["POST"])
def api_wycena_pdf(qid):
    conn = db.get_db()
    q = conn.execute("SELECT * FROM quotes WHERE id=?", (qid,)).fetchone()
    st = _settings(conn)
    conn.close()
    if not q or not q["data_json"]:
        return jsonify(ok=False, blad="Brak danych wyceny."), 404
    data = json.loads(q["data_json"])
    out = pdf_service.out_path_for(st, q["numer"] or str(qid))
    try:
        pdf_service.generate(data, out)
    except Exception as e:  # np. brak fontów / błąd danych
        return jsonify(ok=False, blad=f"Błąd generowania PDF: {e}"), 500
    _open_file(out)
    return jsonify(ok=True, sciezka=out)


# ------------------------------------------------------------------ wycena: duplikuj / usuń
@app.route("/wycena/<int:qid>/duplikuj", methods=["POST"])
def wycena_duplikuj(qid):
    conn = db.get_db()
    q = conn.execute("SELECT * FROM quotes WHERE id=?", (qid,)).fetchone()
    if not q:
        conn.close()
        abort(404)
    data = json.loads(q["data_json"]) if q["data_json"] else {}
    numer = _next_numer(conn)
    data.setdefault("meta", {})
    data["meta"]["numer"] = numer
    data["meta"]["data"] = pdf_service.dzis()
    if isinstance(data.get("_form"), dict):
        data["_form"].pop("id", None)
        data["_form"]["numer"] = numer
        data["_form"]["data"] = pdf_service.dzis()
    cur = conn.execute(
        """INSERT INTO quotes (numer, data, client_id, client_nazwa, suma, data_json)
           VALUES (?,?,?,?,?,?)""",
        (numer, pdf_service.dzis(), q["client_id"], q["client_nazwa"], q["suma"],
         json.dumps(data, ensure_ascii=False)))
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    flash("Utworzono kopię wyceny — możesz ją teraz poprawić.", "ok")
    return redirect(url_for("wycena_edytuj", qid=new_id))


QUOTE_STATUSES = ["szkic", "wysłana", "zaakceptowana", "odrzucona"]


@app.route("/wycena/<int:qid>/status", methods=["POST"])
def wycena_status(qid):
    s = request.form.get("status", "")
    if s in QUOTE_STATUSES:
        conn = db.get_db()
        conn.execute("UPDATE quotes SET status=? WHERE id=?", (s, qid))
        conn.commit()
        conn.close()
    return redirect(url_for("wyceny"))


def _ilosc_na_czesci(ilosc_txt, brutto):
    """'8 szt.' + wartość brutto -> (ilość, jm, cena jednostkowa).
    Gdy nie da się rozbić bez groszowych różnic — pozycja jako 1 kpl. za całość."""
    import re
    m = re.match(r"^\s*([\d\s.,]+?)\s*([^\d\s].*)?$", str(ilosc_txt or "").strip())
    try:
        num = _parse_num(m.group(1)) if m else 0
    except Exception:
        num = 0
    jm = (m.group(2) or "").strip() if m else ""
    if num > 0:
        cena = round(float(brutto) / num, 2)
        if abs(cena * num - float(brutto)) < 0.005:  # rozbicie bez różnic zaokrągleń
            il = int(num) if float(num).is_integer() else num
            return str(il), (jm or "szt."), f"{cena:.2f}".replace(".", ",")
    return "1", (jm or "kpl."), f"{float(brutto):.2f}".replace(".", ",")


@app.route("/wycena/<int:qid>/na-fakture", methods=["POST"])
def wycena_na_fakture(qid):
    """Tworzy fakturę z zaakceptowanej wyceny: klient + pozycje + robocizna."""
    conn = db.get_db()
    q = conn.execute("SELECT * FROM quotes WHERE id=?", (qid,)).fetchone()
    if not q or not q["data_json"]:
        conn.close()
        abort(404)
    qd = json.loads(q["data_json"])
    st = _settings(conn)
    today = datetime.date.today()
    termin = (today + datetime.timedelta(days=14)).strftime("%Y-%m-%d")
    zam = qd.get("zamawiajacy", {})
    adres = (zam.get("adres_html", "") or "").replace("<br/>", ", ").replace("<br>", ", ").strip(" ,")

    items = []
    for p in qd.get("pozycje", []):
        il, jm, cena = _ilosc_na_czesci(p.get("ilosc", ""), p.get("brutto", 0))
        items.append({"nazwa": p.get("nazwa", ""), "ilosc": il, "jm": jm, "cena": cena})
    rob = qd.get("robocizna")
    if rob and float(rob.get("kwota", 0)) > 0:
        items.append({"nazwa": rob.get("opis", "Robocizna"), "ilosc": "1", "jm": "usł.",
                      "cena": f"{float(rob['kwota']):.2f}".replace(".", ",")})

    numer = _next_faktura_numer(conn)
    stan = {
        "fields": {
            "m_numer": numer, "m_wyst": today.strftime("%Y-%m-%d"),
            "m_sprz": today.strftime("%Y-%m-%d"), "m_term": termin,
            "s_nazwa": st["nazwa"] or "", "s_adres": st["adres"] or "",
            "s_nip": st["nip"] or "", "s_regon": "",
            "n_nazwa": zam.get("nazwa", ""), "n_adres": adres, "n_nip": "", "n_regon": "",
            "p_sposob": "Przelew", "p_bank": "", "p_konto": "",
            "klauzula": "Robocizna zwolniona z podatku VAT na podstawie art. 113 ust. 1 (i ust. 9) "
                        "ustawy z dnia 11 marca 2004 r. o podatku od towarów i usług.",
            "f_tel": st["tel"] or "", "f_mail": st["email"] or "",
        },
        "items": items,
        "toggles": {"blueprint": True, "regon": False, "bank": True, "klauzula": True},
    }
    cur = conn.execute(
        "INSERT INTO invoices (numer, wyst_date, sprz_date, term_date, nabywca, suma, osoba_fiz, data_json) VALUES (?,?,?,?,?,?,?,?)",
        (numer, today.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"), termin, zam.get("nazwa", ""),
         _suma_items(items), _osoba_fiz(stan), json.dumps(stan, ensure_ascii=False)))
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    flash(f"Utworzono fakturę {numer} z wyceny {q['numer']} — sprawdź i zapisz.", "ok")
    return redirect(url_for("faktura_edytuj", fid=new_id))


@app.route("/wycena/<int:qid>/usun", methods=["POST"])
def wycena_usun(qid):
    conn = db.get_db()
    conn.execute("DELETE FROM quotes WHERE id=?", (qid,))
    conn.commit()
    conn.close()
    flash("Wycena usunięta.", "ok")
    return redirect(url_for("wyceny"))


# ------------------------------------------------------------------ EKRAN: katalog produktów
@app.route("/katalog")
def katalog():
    conn = db.get_db()
    products = conn.execute("SELECT * FROM products ORDER BY nazwa").fetchall()
    conn.close()
    return render_template("katalog.html", products=products)


@app.route("/katalog/zapisz", methods=["POST"])
def katalog_zapisz():
    f = request.form
    spec = _parse_spec(f.get("spec_text", ""))
    spec_json = json.dumps(spec, ensure_ascii=False) if spec else None
    conn = db.get_db()
    pid = f.get("id")
    args = (f.get("nazwa", "").strip(), f.get("kategoria", "").strip(), f.get("jm", "").strip(),
            float(f.get("cena_brutto") or 0), 1 if f.get("vat") else 0, spec_json)
    if pid:
        conn.execute("""UPDATE products SET nazwa=?, kategoria=?, jm=?, cena_brutto=?, vat=?, spec_json=?
                        WHERE id=?""", args + (pid,))
    else:
        conn.execute("""INSERT INTO products (nazwa, kategoria, jm, cena_brutto, vat, spec_json)
                        VALUES (?,?,?,?,?,?)""", args)
    conn.commit()
    conn.close()
    flash("Zapisano produkt.", "ok")
    return redirect(url_for("katalog"))


@app.route("/katalog/<int:pid>/usun", methods=["POST"])
def katalog_usun(pid):
    conn = db.get_db()
    conn.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    flash("Usunięto produkt.", "ok")
    return redirect(url_for("katalog"))


def _parse_spec(text):
    """Tekst 'Klucz: Wartość' (po jednym w wierszu) -> lista [[k, v], ...]."""
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        k, sep, v = line.partition(":")
        if sep:
            out.append([k.strip(), v.strip()])
    return out


# ------------------------------------------------------------------ EKRAN: klienci
@app.route("/klienci")
def klienci():
    conn = db.get_db()
    rows = conn.execute("SELECT * FROM clients ORDER BY nazwa").fetchall()
    conn.close()
    return render_template("klienci.html", clients=rows)


@app.route("/klienci/zapisz", methods=["POST"])
def klienci_zapisz():
    f = request.form if request.form else request.get_json(force=True)
    conn = db.get_db()
    cid = f.get("id")

    def _br(s):  # zamiana nowych linii na <br/> (formularz), JSON już ma <br/>
        return (s or "").strip().replace("\r\n", "\n").replace("\n", "<br/>")

    args = (f.get("nazwa", "").strip(), _br(f.get("adres_html", "")), _br(f.get("kontakt_html", "")))
    if cid:
        conn.execute("UPDATE clients SET nazwa=?, adres_html=?, kontakt_html=? WHERE id=?",
                     args + (cid,))
        new_id = int(cid)
    else:
        cur = conn.execute("INSERT INTO clients (nazwa, adres_html, kontakt_html) VALUES (?,?,?)", args)
        new_id = cur.lastrowid
    conn.commit()
    conn.close()
    if request.is_json:
        return jsonify(ok=True, id=new_id, nazwa=args[0])
    flash("Zapisano klienta.", "ok")
    return redirect(url_for("klienci"))


@app.route("/klienci/<int:cid>/dokumenty")
def klient_dokumenty(cid):
    """Wszystkie dokumenty klienta: wyceny i umowy po client_id, faktury po nazwie nabywcy."""
    conn = db.get_db()
    c = conn.execute("SELECT * FROM clients WHERE id=?", (cid,)).fetchone()
    if not c:
        conn.close()
        abort(404)
    dokumenty = []
    for typ, sql, args, edytuj in [
        ("wycena", "SELECT id, numer, client_nazwa AS kto, suma AS kwota, status, created_at "
                   "FROM quotes WHERE client_id=?", (cid,), "wycena_edytuj"),
        ("umowa", "SELECT id, numer, client_nazwa AS kto, kwota, status, created_at "
                  "FROM contracts WHERE client_id=?", (cid,), "umowa_edytuj"),
        ("faktura", "SELECT id, numer, nabywca AS kto, suma AS kwota, status, created_at "
                    "FROM invoices WHERE nabywca=?", (c["nazwa"],), "faktura_edytuj"),
    ]:
        for r in conn.execute(sql, args):
            d = dict(r)
            d["typ"] = typ
            d["edytuj"] = edytuj
            dokumenty.append(d)
    conn.close()
    dokumenty.sort(key=lambda d: d.get("created_at") or "", reverse=True)
    return render_template("klient_dokumenty.html", c=c, dokumenty=dokumenty)


@app.route("/klienci/<int:cid>/usun", methods=["POST"])
def klienci_usun(cid):
    conn = db.get_db()
    conn.execute("DELETE FROM clients WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    flash("Usunięto klienta.", "ok")
    return redirect(url_for("klienci"))


# ------------------------------------------------------------------ EKRAN: zestawy BOM
@app.route("/bom")
def bom():
    conn = db.get_db()
    rows = conn.execute("SELECT * FROM boms ORDER BY nazwa").fetchall()
    conn.close()
    return render_template("bom.html", boms=rows)


@app.route("/bom/zapisz", methods=["POST"])
def bom_zapisz():
    f = request.form
    opis = [l.strip() for l in f.get("opis_text", "").splitlines() if l.strip()]
    elementy = []
    for line in f.get("elementy_text", "").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [c.strip() for c in line.split("|")]
        parts = (parts + ["", "", "", ""])[:4]
        elementy.append(parts)
    conn = db.get_db()
    bid = f.get("id")
    args = (f.get("nazwa", "").strip(), f.get("tytul", "").strip(),
            json.dumps(opis, ensure_ascii=False), f.get("naglowek_wykazu", "").strip(),
            json.dumps(elementy, ensure_ascii=False), f.get("nota", "").strip())
    if bid:
        conn.execute("""UPDATE boms SET nazwa=?, tytul=?, opis_json=?, naglowek_wykazu=?,
                        elementy_json=?, nota=? WHERE id=?""", args + (bid,))
    else:
        conn.execute("""INSERT INTO boms (nazwa, tytul, opis_json, naglowek_wykazu, elementy_json, nota)
                        VALUES (?,?,?,?,?,?)""", args)
    conn.commit()
    conn.close()
    flash("Zapisano zestaw.", "ok")
    return redirect(url_for("bom"))


@app.route("/bom/<int:bid>/usun", methods=["POST"])
def bom_usun(bid):
    conn = db.get_db()
    conn.execute("DELETE FROM boms WHERE id=?", (bid,))
    conn.commit()
    conn.close()
    flash("Usunięto zestaw.", "ok")
    return redirect(url_for("bom"))


# ------------------------------------------------------------------ EKRAN: ustawienia
@app.route("/ustawienia")
def ustawienia():
    conn = db.get_db()
    st = _settings(conn)
    conn.close()
    return render_template("ustawienia.html", s=st,
                           warunki="\n".join(json.loads(st["warunki_json"] or "[]")),
                           materialy="\n".join(json.loads(st["materialy_json"] or "[]")),
                           wersja=updater.wersja_lokalna())


@app.route("/ustawienia/backup", methods=["POST"])
def ustawienia_backup():
    """Kopia zapasowa bazy: dane_RRRR-MM-DD_GGMM.db do folderu 'Kopie zapasowe' obok PDF-ów."""
    import shutil
    conn = db.get_db()
    st = _settings(conn)
    conn.close()
    folder = os.path.join(st["pdf_folder"] or os.path.join(os.path.expanduser("~"), "Wyceny-InstalPawel"),
                          "Kopie zapasowe")
    os.makedirs(folder, exist_ok=True)
    nazwa = "dane_" + datetime.datetime.now().strftime("%Y-%m-%d_%H%M") + ".db"
    cel = os.path.join(folder, nazwa)
    try:
        # bezpieczna kopia SQLite (spójna nawet przy otwartych połączeniach)
        src = db.get_db()
        dst = __import__("sqlite3").connect(cel)
        src.backup(dst)
        dst.close()
        src.close()
    except Exception as e:
        flash(f"Nie udało się zrobić kopii: {e}", "ok")
        return redirect(url_for("ustawienia"))
    _open_file(folder)
    flash(f"Kopia zapasowa zapisana: {cel}", "ok")
    return redirect(url_for("ustawienia"))


@app.route("/ustawienia/zapisz", methods=["POST"])
def ustawienia_zapisz():
    f = request.form
    warunki = [l.strip() for l in f.get("warunki", "").splitlines() if l.strip()]
    materialy = [l.strip() for l in f.get("materialy", "").splitlines() if l.strip()]
    conn = db.get_db()
    conn.execute(
        """UPDATE settings SET nazwa=?, podtytul=?, wordmark=?, wordmark_sub=?, nip=?, adres=?,
           tel=?, email=?, klauzula_vat=?, warunki_json=?, materialy_json=?, pdf_folder=? WHERE id=1""",
        (f.get("nazwa", "").strip(), f.get("podtytul", "").strip(), f.get("wordmark", "").strip(),
         f.get("wordmark_sub", "").strip(), f.get("nip", "").strip(), f.get("adres", "").strip(),
         f.get("tel", "").strip(), f.get("email", "").strip(), f.get("klauzula_vat", "").strip(),
         json.dumps(warunki, ensure_ascii=False), json.dumps(materialy, ensure_ascii=False),
         f.get("pdf_folder", "").strip()))
    conn.commit()
    conn.close()
    flash("Zapisano ustawienia.", "ok")
    return redirect(url_for("ustawienia"))


# ================================================================== FAKTURY
# Faktura jako osobny typ dokumentu. Kontrakt danych = zbierzStan() z handoffu:
# {"fields": {...}, "items": [...], "toggles": {...}}. Sprzedawca zwolniony z VAT.
@app.route("/faktury")
def faktury():
    conn = db.get_db()
    rows = conn.execute("SELECT * FROM invoices ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("faktury.html", invoices=rows,
                           dzis_iso=datetime.date.today().strftime("%Y-%m-%d"))


@app.route("/faktura/<int:fid>/status", methods=["POST"])
def faktura_status(fid):
    s = request.form.get("status", "")
    if s in ("niezapłacona", "zapłacona"):
        conn = db.get_db()
        conn.execute("UPDATE invoices SET status=? WHERE id=?", (s, fid))
        conn.commit()
        conn.close()
    return redirect(url_for("faktury"))


@app.route("/faktura/nowa")
def faktura_nowa():
    conn = db.get_db()
    ctx = _faktura_context(conn, None)
    conn.close()
    return render_template("faktura.html", **ctx)


@app.route("/faktura/<int:fid>/edytuj")
def faktura_edytuj(fid):
    conn = db.get_db()
    f = conn.execute("SELECT * FROM invoices WHERE id=?", (fid,)).fetchone()
    if not f:
        conn.close()
        abort(404)
    ctx = _faktura_context(conn, f)
    conn.close()
    return render_template("faktura.html", **ctx)


def _faktura_context(conn, f):
    st = _settings(conn)
    clients = conn.execute("SELECT * FROM clients ORDER BY nazwa").fetchall()
    stan = json.loads(f["data_json"]) if f and f["data_json"] else None
    # domyślny stan nowej faktury: sprzedawca z Ustawień, świeży numer, dzisiejsze daty
    defaults = {
        "seller": {"nazwa": st["nazwa"] or "INSTAL-PAWEL — Usługi Elektryczne",
                   "adres": st["adres"] or "", "nip": st["nip"] or "", "regon": ""},
        "tel": st["tel"] or "", "mail": st["email"] or "",
        "klauzula": "Robocizna zwolniona z podatku VAT na podstawie art. 113 ust. 1 (i ust. 9) "
                    "ustawy z dnia 11 marca 2004 r. o podatku od towarów i usług.",
    }
    clients_json = [{"id": c["id"], "nazwa": c["nazwa"],
                     "adres_html": c["adres_html"] or "", "kontakt_html": c["kontakt_html"] or ""}
                    for c in clients]
    return {
        "f": f, "stan": stan, "clients": clients, "clients_json": clients_json, "defaults": defaults,
        "domyslny_numer": (f["numer"] if f else _next_faktura_numer(conn)),
        "dzis_iso": datetime.date.today().strftime("%Y-%m-%d"),
    }


def _osoba_fiz(stan):
    """Osoba fizyczna = przełącznik na fakturze albo pusty NIP nabywcy.
    Liczy się do limitu zwolnienia z kasy fiskalnej (20 000 zł/rok)."""
    fields = stan.get("fields", {}) or {}
    toggles = stan.get("toggles", {}) or {}
    if "osoba_fiz" in toggles:
        return 1 if toggles["osoba_fiz"] else 0
    return 0 if (fields.get("n_nip") or "").strip() else 1


@app.route("/api/faktura/zapisz", methods=["POST"])
def api_faktura_zapisz():
    stan = request.get_json(force=True)
    fields = stan.get("fields", {}) or {}
    items = stan.get("items", []) or []
    conn = db.get_db()
    suma = _suma_items(items)
    numer = fields.get("m_numer", "")
    wyst = fields.get("m_wyst", "")
    sprz = (fields.get("m_sprz") or "").strip() or wyst  # data sprzedaży decyduje o miesiącu
    termin = fields.get("m_term", "")
    nabywca = fields.get("n_nazwa", "")
    osfiz = _osoba_fiz(stan)
    data_json = json.dumps(stan, ensure_ascii=False)
    fid = stan.get("id")
    if fid:
        conn.execute(
            "UPDATE invoices SET numer=?, wyst_date=?, sprz_date=?, term_date=?, nabywca=?, suma=?, osoba_fiz=?, data_json=? WHERE id=?",
            (numer, wyst, sprz, termin, nabywca, suma, osfiz, data_json, fid))
    else:
        cur = conn.execute(
            "INSERT INTO invoices (numer, wyst_date, sprz_date, term_date, nabywca, suma, osoba_fiz, data_json) VALUES (?,?,?,?,?,?,?,?)",
            (numer, wyst, sprz, termin, nabywca, suma, osfiz, data_json))
        fid = cur.lastrowid
    conn.commit()
    conn.close()
    return jsonify(ok=True, id=fid)


@app.route("/faktura/<int:fid>/duplikuj", methods=["POST"])
def faktura_duplikuj(fid):
    conn = db.get_db()
    f = conn.execute("SELECT * FROM invoices WHERE id=?", (fid,)).fetchone()
    if not f:
        conn.close()
        abort(404)
    stan = json.loads(f["data_json"]) if f["data_json"] else {"fields": {}, "items": [], "toggles": {}}
    stan.pop("id", None)
    numer = _next_faktura_numer(conn)
    stan.setdefault("fields", {})
    stan["fields"]["m_numer"] = numer
    today = datetime.date.today().strftime("%Y-%m-%d")
    stan["fields"]["m_wyst"] = today
    stan["fields"]["m_sprz"] = today
    cur = conn.execute(
        "INSERT INTO invoices (numer, wyst_date, sprz_date, nabywca, suma, osoba_fiz, data_json) VALUES (?,?,?,?,?,?,?)",
        (numer, today, today, f["nabywca"], f["suma"], _osoba_fiz(stan), json.dumps(stan, ensure_ascii=False)))
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    flash("Utworzono kopię faktury — możesz ją teraz poprawić.", "ok")
    return redirect(url_for("faktura_edytuj", fid=new_id))


@app.route("/faktura/<int:fid>/usun", methods=["POST"])
def faktura_usun(fid):
    conn = db.get_db()
    conn.execute("DELETE FROM invoices WHERE id=?", (fid,))
    conn.commit()
    conn.close()
    flash("Faktura usunięta.", "ok")
    return redirect(url_for("faktury"))


# ================================================================== AKTUALIZACJE
# Pobieranie sprawdzonej wersji programu z GitHuba (branch `stable`) — patrz updater.py.
def _folder_kopii():
    conn = db.get_db()
    st = _settings(conn)
    conn.close()
    return os.path.join(st["pdf_folder"] or os.path.join(os.path.expanduser("~"), "Wyceny-InstalPawel"),
                        "Kopie zapasowe")


@app.route("/api/aktualizacja/sprawdz")
def api_aktualizacja_sprawdz():
    lokalna = updater.wersja_lokalna()
    try:
        zdalna = updater.wersja_zdalna()
    except Exception:
        return jsonify(ok=False, lokalna=lokalna,
                       blad="Nie udało się sprawdzić aktualizacji. Sprawdź połączenie z internetem.")
    return jsonify(ok=True, lokalna=lokalna, zdalna=zdalna,
                   dostepna=updater.jest_nowsza(zdalna, lokalna))


@app.route("/api/aktualizacja/wykonaj", methods=["POST"])
def api_aktualizacja_wykonaj():
    try:
        wersja, kopia = updater.aktualizuj(_folder_kopii())
    except Exception as e:
        return jsonify(ok=False, blad=f"Aktualizacja nie powiodła się: {e}. "
                                      "Program działa dalej w dotychczasowej wersji."), 500
    updater.restart_programu()
    return jsonify(ok=True, wersja=wersja, kopia=kopia)


# ================================================================== UMOWY
# Umowa jako osobny typ dokumentu. PDF: pdf_engine/umowa.py (ta sama grafika
# marki co wyceny). Stan w contracts.data_json (słownik `data` + "_form").
def _next_umowa_numer(conn, when=None):
    """Kolejny numer umowy NN/MM/RRRR (auto-inkrement w obrębie miesiąca)."""
    when = when or datetime.date.today()
    suffix = when.strftime("/%m/%Y")
    n = 0
    for r in conn.execute("SELECT numer FROM contracts WHERE numer LIKE ?", ("%" + suffix,)):
        try:
            n = max(n, int(str(r["numer"]).split("/", 1)[0]))
        except (ValueError, IndexError):
            pass
    return f"{n + 1:02d}{suffix}"


def _lines(text):
    return [l.strip() for l in (text or "").splitlines() if l.strip()]


def _umowa_assemble(conn, f):
    """Z formularza umowy buduje słownik `data` dla pdf_engine/umowa.py."""
    st = _settings(conn)

    def _br(s):
        return (s or "").strip().replace("\r\n", "\n").replace("\n", "<br/>")

    client = {}
    cid = f.get("client_id") or None
    if cid:
        row = conn.execute("SELECT * FROM clients WHERE id=?", (cid,)).fetchone()
        if row:
            client = dict(row)
    if not client:  # klient wpisany ręcznie
        client = {"nazwa": (f.get("client_nazwa") or "").strip(),
                  "adres_html": _br(f.get("client_adres")),
                  "kontakt_html": _br(f.get("client_kontakt"))}

    data = {
        "wystawca": {
            "nazwa": st["nazwa"], "podtytul": st["podtytul"],
            "wordmark": st["wordmark"], "wordmark_sub": st["wordmark_sub"],
            "nip": st["nip"], "adres": st["adres"], "tel": st["tel"], "email": st["email"],
        },
        "zamawiajacy": {"nazwa": client.get("nazwa", ""),
                        "adres_html": client.get("adres_html", ""),
                        "kontakt_html": client.get("kontakt_html", "")},
        "meta": {"tytul": "UMOWA",
                 "numer": (f.get("numer") or "").strip(),
                 "data": (f.get("data") or pdf_service.dzis()).strip(),
                 "miejscowosc": (f.get("miejscowosc") or "").strip()},
        "przedmiot": (f.get("przedmiot") or "").strip(),
        "zakres": _lines(f.get("zakres")),
        "termin_rozpoczecia": (f.get("termin_od") or "").strip(),
        "termin_zakonczenia": (f.get("termin_do") or "").strip(),
        "wynagrodzenie": {"kwota": _parse_num(f.get("kwota")),
                          "zaliczka": _parse_num(f.get("zaliczka")),
                          "platnosc": (f.get("platnosc") or "").strip()},
        "gwarancja": (f.get("gwarancja") or "").strip(),
        "dodatkowe": _lines(f.get("dodatkowe")),
    }
    return data, client, cid


@app.route("/umowy")
def umowy():
    conn = db.get_db()
    rows = conn.execute("SELECT * FROM contracts ORDER BY id DESC").fetchall()
    conn.close()
    contracts = []
    for r in rows:
        d = dict(r)
        try:
            wyn = (json.loads(r["data_json"] or "{}").get("wynagrodzenie") or {})
            d["ma_zaliczke"] = float(wyn.get("zaliczka") or 0) > 0
        except (ValueError, TypeError):
            d["ma_zaliczke"] = False
        contracts.append(d)
    return render_template("umowy.html", contracts=contracts)


@app.route("/umowa/<int:uid>/na-fakture", methods=["POST"])
def umowa_na_fakture(uid):
    """Faktura z umowy: rodzaj=zaliczkowa (na kwotę zaliczki) lub koncowa
    (wynagrodzenie pomniejszone o zaliczkę)."""
    rodzaj = request.form.get("rodzaj", "koncowa")
    conn = db.get_db()
    u = conn.execute("SELECT * FROM contracts WHERE id=?", (uid,)).fetchone()
    if not u or not u["data_json"]:
        conn.close()
        abort(404)
    ud = json.loads(u["data_json"])
    st = _settings(conn)
    zam = ud.get("zamawiajacy", {})
    adres = (zam.get("adres_html", "") or "").replace("<br/>", ", ").replace("<br>", ", ").strip(" ,")
    wyn = ud.get("wynagrodzenie") or {}
    kwota = float(wyn.get("kwota") or 0)
    zaliczka = float(wyn.get("zaliczka") or 0)
    przedmiot = ud.get("przedmiot", "")
    numer_um = u["numer"] or ""

    if rodzaj == "zaliczkowa":
        if zaliczka <= 0:
            conn.close()
            flash("Ta umowa nie ma zaliczki — wystaw fakturę końcową.", "ok")
            return redirect(url_for("umowy"))
        items = [{"nazwa": f"Zaliczka zgodnie z umową nr {numer_um} — {przedmiot}",
                  "ilosc": "1", "jm": "usł.", "cena": f"{zaliczka:.2f}".replace(".", ",")}]
    else:
        do_zaplaty = max(0.0, kwota - zaliczka)
        nazwa = f"{przedmiot} — zgodnie z umową nr {numer_um}"
        if zaliczka > 0:
            nazwa += f" (po rozliczeniu zaliczki {money(zaliczka)})"
        items = [{"nazwa": nazwa, "ilosc": "1", "jm": "usł.",
                  "cena": f"{do_zaplaty:.2f}".replace(".", ",")}]

    today = datetime.date.today()
    termin = (today + datetime.timedelta(days=14)).strftime("%Y-%m-%d")
    numer = _next_faktura_numer(conn)
    stan = {
        "fields": {
            "m_numer": numer, "m_wyst": today.strftime("%Y-%m-%d"),
            "m_sprz": today.strftime("%Y-%m-%d"), "m_term": termin,
            "s_nazwa": st["nazwa"] or "", "s_adres": st["adres"] or "",
            "s_nip": st["nip"] or "", "s_regon": "",
            "n_nazwa": zam.get("nazwa", ""), "n_adres": adres, "n_nip": "", "n_regon": "",
            "p_sposob": "Przelew", "p_bank": "", "p_konto": "",
            "klauzula": "Robocizna zwolniona z podatku VAT na podstawie art. 113 ust. 1 (i ust. 9) "
                        "ustawy z dnia 11 marca 2004 r. o podatku od towarów i usług.",
            "f_tel": st["tel"] or "", "f_mail": st["email"] or "",
        },
        "items": items,
        "toggles": {"blueprint": True, "regon": False, "bank": True, "klauzula": True},
    }
    cur = conn.execute(
        "INSERT INTO invoices (numer, wyst_date, sprz_date, term_date, nabywca, suma, osoba_fiz, data_json) VALUES (?,?,?,?,?,?,?,?)",
        (numer, today.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"), termin, zam.get("nazwa", ""),
         _suma_items(items), _osoba_fiz(stan), json.dumps(stan, ensure_ascii=False)))
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    opis = "zaliczkową" if rodzaj == "zaliczkowa" else "końcową"
    flash(f"Utworzono fakturę {opis} {numer} z umowy {numer_um} — sprawdź i zapisz.", "ok")
    return redirect(url_for("faktura_edytuj", fid=new_id))


UMOWA_STATUSES = ["szkic", "podpisana", "zakończona"]


@app.route("/umowa/<int:uid>/status", methods=["POST"])
def umowa_status(uid):
    s = request.form.get("status", "")
    if s in UMOWA_STATUSES:
        conn = db.get_db()
        conn.execute("UPDATE contracts SET status=? WHERE id=?", (s, uid))
        conn.commit()
        conn.close()
    return redirect(url_for("umowy"))


def _umowa_context(conn, u, form=None):
    """Kontekst edytora umowy. `form` = słownik pól do wypełnienia formularza."""
    clients = conn.execute("SELECT * FROM clients ORDER BY nazwa").fetchall()
    if form is None and u and u["data_json"]:
        form = (json.loads(u["data_json"]) or {}).get("_form") or {}
    return {
        "u": u,
        "form": form or {},
        "clients": clients,
        "domyslny_numer": (u["numer"] if u else _next_umowa_numer(conn)),
        "dzis": pdf_service.dzis(),
        "domyslna_platnosc": "przelewem na rachunek bankowy Wykonawcy lub gotówką, "
                             "w terminie 7 dni od dnia odbioru prac i wystawienia faktury.",
    }


@app.route("/umowa/nowa")
def umowa_nowa():
    conn = db.get_db()
    ctx = _umowa_context(conn, None)
    conn.close()
    return render_template("umowa.html", **ctx)


@app.route("/umowa/<int:uid>/edytuj")
def umowa_edytuj(uid):
    conn = db.get_db()
    u = conn.execute("SELECT * FROM contracts WHERE id=?", (uid,)).fetchone()
    if not u:
        conn.close()
        abort(404)
    ctx = _umowa_context(conn, u)
    conn.close()
    return render_template("umowa.html", **ctx)


@app.route("/umowa/zapisz", methods=["POST"])
def umowa_zapisz():
    f = request.form
    conn = db.get_db()
    data, client, cid = _umowa_assemble(conn, f)
    data["_form"] = {k: f.get(k, "") for k in
                     ("client_id", "client_nazwa", "client_adres", "client_kontakt",
                      "numer", "data", "miejscowosc", "przedmiot", "zakres",
                      "termin_od", "termin_do", "kwota", "zaliczka", "platnosc",
                      "gwarancja", "dodatkowe")}
    data_json = json.dumps(data, ensure_ascii=False)
    uid = f.get("id")
    args = (data["meta"]["numer"], data["meta"]["data"], cid, client.get("nazwa", ""),
            data["wynagrodzenie"]["kwota"], data_json)
    if uid:
        conn.execute("""UPDATE contracts SET numer=?, data=?, client_id=?, client_nazwa=?,
                        kwota=?, data_json=? WHERE id=?""", args + (uid,))
    else:
        cur = conn.execute("""INSERT INTO contracts (numer, data, client_id, client_nazwa, kwota, data_json)
                              VALUES (?,?,?,?,?,?)""", args)
        uid = cur.lastrowid
    conn.commit()
    conn.close()
    if f.get("po_zapisie") == "pdf":
        return redirect(url_for("umowa_edytuj", uid=uid, pdf=1))
    flash("Zapisano umowę.", "ok")
    return redirect(url_for("umowy"))


@app.route("/api/umowa/<int:uid>/pdf", methods=["POST"])
def api_umowa_pdf(uid):
    conn = db.get_db()
    u = conn.execute("SELECT * FROM contracts WHERE id=?", (uid,)).fetchone()
    st = _settings(conn)
    conn.close()
    if not u or not u["data_json"]:
        return jsonify(ok=False, blad="Brak danych umowy."), 404
    data = json.loads(u["data_json"])
    out = pdf_service.out_path_umowa(st, u["numer"] or str(uid))
    try:
        pdf_service.generate_umowa(data, out)
    except Exception as e:
        return jsonify(ok=False, blad=f"Błąd generowania PDF: {e}"), 500
    _open_file(out)
    return jsonify(ok=True, sciezka=out)


@app.route("/umowa/<int:uid>/duplikuj", methods=["POST"])
def umowa_duplikuj(uid):
    conn = db.get_db()
    u = conn.execute("SELECT * FROM contracts WHERE id=?", (uid,)).fetchone()
    if not u:
        conn.close()
        abort(404)
    data = json.loads(u["data_json"]) if u["data_json"] else {}
    numer = _next_umowa_numer(conn)
    data.setdefault("meta", {})
    data["meta"]["numer"] = numer
    data["meta"]["data"] = pdf_service.dzis()
    if isinstance(data.get("_form"), dict):
        data["_form"]["numer"] = numer
        data["_form"]["data"] = pdf_service.dzis()
    cur = conn.execute(
        """INSERT INTO contracts (numer, data, client_id, client_nazwa, kwota, data_json)
           VALUES (?,?,?,?,?,?)""",
        (numer, pdf_service.dzis(), u["client_id"], u["client_nazwa"], u["kwota"],
         json.dumps(data, ensure_ascii=False)))
    new_id = cur.lastrowid
    conn.commit()
    conn.close()
    flash("Utworzono kopię umowy — możesz ją teraz poprawić.", "ok")
    return redirect(url_for("umowa_edytuj", uid=new_id))


@app.route("/umowa/<int:uid>/usun", methods=["POST"])
def umowa_usun(uid):
    conn = db.get_db()
    conn.execute("DELETE FROM contracts WHERE id=?", (uid,))
    conn.commit()
    conn.close()
    flash("Umowa usunięta.", "ok")
    return redirect(url_for("umowy"))


@app.route("/wycena/<int:qid>/na-umowe", methods=["POST"])
def wycena_na_umowe(qid):
    """Tworzy szkic umowy z wyceny: klient, przedmiot, kwota = suma wyceny."""
    conn = db.get_db()
    q = conn.execute("SELECT * FROM quotes WHERE id=?", (qid,)).fetchone()
    if not q or not q["data_json"]:
        conn.close()
        abort(404)
    qd = json.loads(q["data_json"])
    kwota = float(q["suma"] or 0)
    form = {
        "client_id": str(q["client_id"] or ""),
        "numer": _next_umowa_numer(conn), "data": pdf_service.dzis(), "miejscowosc": "",
        "przedmiot": qd.get("przedmiot", ""),
        "zakres": "\n".join(f'{p.get("nazwa","")} — {p.get("ilosc","")}'.strip(" —")
                            for p in qd.get("pozycje", [])),
        "termin_od": "", "termin_do": "",
        "kwota": f"{kwota:.2f}".replace(".", ","), "zaliczka": "",
        "platnosc": "", "gwarancja": "24 miesiące", "dodatkowe": "",
    }
    ctx = _umowa_context(conn, None, form=form)
    conn.close()
    flash(f"Umowa przygotowana z wyceny {q['numer']} — uzupełnij terminy i zapisz.", "ok")
    return render_template("umowa.html", **ctx)


def _wolny_port(start):
    """Zwraca pierwszy wolny port od `start` w górę (gdy 8000 jest zajęty)."""
    import socket
    for p in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return start


if __name__ == "__main__":
    import threading
    import webbrowser

    port = int(os.environ.get("PORT", "0")) or _wolny_port(8000)
    url = f"http://127.0.0.1:{port}"
    print(f"\n  INSTAL-PAWEŁ — aplikacja wycen działa pod adresem:  {url}")
    print("  Zamknij to okno, aby wyłączyć program.\n")
    # otwórz przeglądarkę po chwili (gdy serwer już wstanie)
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=port, debug=False)
