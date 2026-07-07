#!/bin/bash
# INSTAL-PAWEŁ — uruchomienie aplikacji na macOS.
# Kliknij dwukrotnie ten plik. Za pierwszym razem instalacja potrwa chwilę.
cd "$(dirname "$0")" || exit 1

echo "== INSTAL-PAWEŁ — przygotowanie =="

# Znajdź Pythona 3
PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "Nie znaleziono Pythona. Zainstaluj Python 3 ze strony https://www.python.org/downloads/ i spróbuj ponownie."
  read -r -p "Naciśnij Enter, aby zamknąć."
  exit 1
fi

# Utwórz środowisko przy pierwszym uruchomieniu (sprawdzamy plik activate,
# nie sam folder — gdyby .venv przyszedł z innego systemu, tworzymy od nowa)
if [ ! -f .venv/bin/activate ]; then
  rm -rf .venv
  echo "Pierwsze uruchomienie — tworzę środowisko (to potrwa około minuty)..."
  "$PY" -m venv .venv || { echo "Błąd tworzenia środowiska."; read -r -p "Enter..."; exit 1; }
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt -r pdf_engine/requirements.txt

echo "Uruchamiam aplikację — przeglądarka otworzy się sama."
python app.py
