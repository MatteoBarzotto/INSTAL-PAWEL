# -*- coding: utf-8 -*-
"""
INSTAL-PAWEŁ — aktualizator programu.

Zasada działania (bez gita na komputerze Pawła):
  1. Matteo pracuje na branchu `main`; sprawdzoną wersję wypycha na branch `stable`
     i podbija numer w pliku `wersja.txt`.
  2. Aplikacja porównuje lokalny `wersja.txt` z tym na branchu `stable`
     (raw.githubusercontent.com — zwykłe HTTPS).
  3. „Zainstaluj aktualizację": pobiera ZIP repo (codeload.github.com), robi kopię
     zapasową `dane.db`, podmienia pliki programu (NIGDY bazy ani .venv),
     doinstalowuje zależności pip i restartuje program.

Baza `dane.db` nie jest w repo (.gitignore) — aktualizacja jej nie dotyka.
"""
import io
import os
import sys
import shutil
import zipfile
import datetime
import subprocess
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))

REPO   = "MatteoBarzotto/INSTAL-PAWEL"
BRANCH = "stable"   # tylko sprawdzone wersje trafiają na ten branch

# tych rzeczy aktualizacja nigdy nie nadpisuje ani nie usuwa
CHRONIONE = {"dane.db", ".venv", ".git", "__pycache__", "github_token.txt"}


def _token():
    """Token GitHuba (tylko-odczyt) — potrzebny, gdy repo jest prywatne.
    Plik `github_token.txt` obok app.py, poza repo (.gitignore)."""
    try:
        with open(os.path.join(HERE, "github_token.txt"), encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def _pobierz(url, timeout, naglowki=None):
    req = urllib.request.Request(url, headers={"User-Agent": "instal-pawel-app",
                                               **(naglowki or {})})
    tok = _token()
    if tok:
        req.add_header("Authorization", "Bearer " + tok)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _url_wersja():
    if _token():  # prywatne repo -> GitHub API
        return f"https://api.github.com/repos/{REPO}/contents/wersja.txt?ref={BRANCH}"
    return f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/wersja.txt"


def _url_zip():
    if _token():
        return f"https://api.github.com/repos/{REPO}/zipball/{BRANCH}"
    return f"https://codeload.github.com/{REPO}/zip/refs/heads/{BRANCH}"


def wersja_lokalna():
    try:
        with open(os.path.join(HERE, "wersja.txt"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "0.0.0"


def wersja_zdalna(timeout=10):
    """Numer wersji z brancha `stable` na GitHubie. Rzuca wyjątek przy braku internetu."""
    naglowki = {"Accept": "application/vnd.github.raw+json"} if _token() else None
    return _pobierz(_url_wersja(), timeout, naglowki).decode("utf-8").strip()


def _jako_liczby(w):
    """'1.2.10' -> (1, 2, 10); śmieci traktujemy jako 0."""
    out = []
    for czesc in str(w).strip().split("."):
        try:
            out.append(int("".join(ch for ch in czesc if ch.isdigit()) or 0))
        except ValueError:
            out.append(0)
    return tuple(out)


def jest_nowsza(zdalna, lokalna):
    return _jako_liczby(zdalna) > _jako_liczby(lokalna)


def _kopia_bazy(folder_kopii):
    """Kopia dane.db przed aktualizacją (przez sqlite backup — spójna)."""
    import sqlite3
    src_path = os.path.join(HERE, "dane.db")
    if not os.path.exists(src_path):
        return None
    os.makedirs(folder_kopii, exist_ok=True)
    cel = os.path.join(folder_kopii,
                       "dane_przed-aktualizacja_" +
                       datetime.datetime.now().strftime("%Y-%m-%d_%H%M") + ".db")
    src = sqlite3.connect(src_path)
    dst = sqlite3.connect(cel)
    src.backup(dst)
    dst.close()
    src.close()
    return cel


def aktualizuj(folder_kopii, timeout=60):
    """Pobiera i instaluje najnowszą wersję z brancha `stable`.

    Zwraca (nowa_wersja, sciezka_kopii_bazy). Rzuca wyjątek przy błędzie —
    pliki podmieniamy dopiero PO udanym pobraniu i rozpakowaniu całości.
    """
    # 1. pobierz ZIP repo do pamięci
    blob = _pobierz(_url_zip(), timeout)

    # 2. rozpakuj do folderu tymczasowego
    tmp = os.path.join(HERE, ".aktualizacja_tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        z.extractall(tmp)
    # ZIP GitHuba ma jeden katalog główny "INSTAL-PAWEL-stable/"
    korzenie = [d for d in os.listdir(tmp) if os.path.isdir(os.path.join(tmp, d))]
    if not korzenie:
        raise RuntimeError("Pobrany plik aktualizacji jest pusty.")
    zrodlo = os.path.join(tmp, korzenie[0])
    if not os.path.exists(os.path.join(zrodlo, "app.py")):
        raise RuntimeError("Pobrany plik aktualizacji wygląda na uszkodzony (brak app.py).")

    # 3. kopia bazy — na wszelki wypadek (aktualizacja bazy nie rusza)
    kopia = _kopia_bazy(folder_kopii)

    # 4. podmień pliki programu (bez plików chronionych)
    for nazwa in os.listdir(zrodlo):
        if nazwa in CHRONIONE:
            continue
        src = os.path.join(zrodlo, nazwa)
        dst = os.path.join(HERE, nazwa)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
    shutil.rmtree(tmp, ignore_errors=True)

    # 5. doinstaluj ewentualne nowe zależności (cicho; brak internetu już nie grozi —
    #    paczka pobrana; a przy restarcie start.command/start.bat też robi pip install)
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet",
                        "-r", os.path.join(HERE, "requirements.txt"),
                        "-r", os.path.join(HERE, "pdf_engine", "requirements.txt")],
                       check=False, timeout=300)
    except Exception:
        pass

    return wersja_lokalna(), kopia


def restart_programu(opoznienie=1.5):
    """Restart aplikacji po aktualizacji (nowy kod wstaje pod tym samym adresem)."""
    import threading

    def _exec():
        os.chdir(HERE)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    threading.Timer(opoznienie, _exec).start()
