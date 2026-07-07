# Koncepcja: „Wyceniarka INSTAL-PAWEŁ"

## Problem
Każdą wycenę robi się teraz ręcznie od zera — czasochłonne, łatwo o literówkę w sumie,
a klienci (np. BUDMAX) proszą o coraz bardziej szczegółowe oferty z parametrami technicznymi.

## Pomysł
Mały program na komputer, w którym Paweł **klika, a nie pisze od nowa**:

1. Wybiera klienta z listy (albo dodaje nowego).
2. Dodaje pozycje z **katalogu** (moduły, inwertery, akumulatory, rozdzielnice, konstrukcja,
   materiały) — cena i opis techniczny podpowiadają się same.
3. Wpisuje ilości i ewentualnie koryguje ceny, dodaje robociznę.
4. Klika **„Generuj PDF"** — wychodzi gotowa, ładna oferta w stylu firmy (ta sama grafika,
   którą już mamy), z automatyczną sumą, kwotą „słownie" i klauzulą VAT (art. 113).

Wycenę można **zapisać, zduplikować i poprawić** — następna podobna oferta to 2 minuty.

## Dlaczego to działa
- **Silnik PDF już istnieje** i wygląda profesjonalnie (nasz szablon). Program tylko go „karmi" danymi.
- Automaty eliminują błędy: sumy, VAT, numeracja, kwota słownie.
- Katalog = wiedza firmy w jednym miejscu (raz wpiszesz parametry JINKO/VOLT/Schneider/BAKS, używasz zawsze).
- Działa **lokalnie i bez internetu** — dane zostają na komputerze Pawła.

## Co zawiera ten folder
- `pdf_engine/` — **gotowy silnik PDF** (`generator.py`) + przykładowe dane (`przyklad_dane.json`)
  + fonty. Odpalenie `python pdf_engine/generator.py` tworzy przykładową ofertę.
- `CLAUDE.md` — instrukcja projektu dla Claude Code (stack, model danych, zasady).
- `PROMPT_do_Claude_Code.md` — **gotowy prompt**: otwórz Claude Code w tym folderze i wklej go,
  żeby zbudować całą aplikację wokół silnika.

## Jak ruszyć (2 kroki)
1. Zainstaluj **Claude Code** (narzędzie w terminalu).
2. W terminalu wejdź do tego folderu i uruchom Claude Code, a potem wklej treść z
   `PROMPT_do_Claude_Code.md`. Reszta powstanie krok po kroku.

## Możliwe rozszerzenia (później)
- Eksport oferty także do Worda.
- Automatyczna numeracja i archiwum wszystkich wycen z wyszukiwarką.
- Logo firmy jako obrazek w nagłówku zamiast rysowanego wordmarku.
- Pozycje „z VAT / bez VAT" per linia, rabaty, warianty (np. wersja tańsza/droższa).
- Prosta wersja przeglądarkowa (bez instalacji Pythona).
