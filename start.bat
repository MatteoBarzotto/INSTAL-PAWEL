@echo off
REM INSTAL-PAWEL — uruchomienie aplikacji na Windows.
REM Kliknij dwukrotnie ten plik. Za pierwszym razem instalacja potrwa chwile.
cd /d "%~dp0"

echo == INSTAL-PAWEL — przygotowanie ==

REM Znajdz Pythona (py launcher lub python)
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY (
  echo Nie znaleziono Pythona. Zainstaluj Python 3 ze strony https://www.python.org/downloads/
  echo Wazne: przy instalacji zaznacz "Add Python to PATH".
  pause
  exit /b 1
)

REM Utworz srodowisko przy pierwszym uruchomieniu.
REM Sprawdzamy plik activate.bat (nie sam folder) — gdyby folder .venv przyszedl
REM omylkowo z innego komputera (np. macOS), tworzymy srodowisko od nowa.
if not exist ".venv\Scripts\activate.bat" (
  if exist ".venv" rmdir /s /q ".venv"
  echo Pierwsze uruchomienie — tworze srodowisko ^(to potrwa okolo minuty^)...
  %PY% -m venv .venv || ( echo Blad tworzenia srodowiska. & pause & exit /b 1 )
)

call .venv\Scripts\activate.bat
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt -r pdf_engine\requirements.txt

echo Uruchamiam aplikacje — przegladarka otworzy sie sama.
python app.py
pause
