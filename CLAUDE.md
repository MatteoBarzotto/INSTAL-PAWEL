# CLAUDE.md — Program do wycen INSTAL-PAWEŁ

Ten plik jest pamięcią projektu dla Claude Code. Czytaj go na początku każdej sesji
i trzymaj się ustaleń. Aplikację buduje Claude Code; **silnik PDF już istnieje i jest
gotowy** — nie przerabiaj jego wyglądu.

---

## 1. Cel produktu

Prosta aplikacja, w której **Paweł (elektryk, nie-programista)** sam tworzy profesjonalne
wyceny/oferty PDF w kilka minut: wybiera klienta, dodaje pozycje z katalogu, wpisuje ilości
i ceny, klika „Generuj PDF". Wygląd PDF jest już zaprojektowany (marka INSTAL-PAWEŁ) i **musi
pozostać identyczny**.

Zasada nadrzędna: **maksymalna prostota dla użytkownika**. Żadnego żargonu w UI, duże przyciski,
polskie etykiety, sensowne wartości domyślne, trudno o pomyłkę.

---

## 2. Stack (nie zmieniaj bez powodu)

- **Python 3.10+**, backend **Flask** (lekki, lokalny serwer).
- **SQLite** (plik `dane.db`) — klienci, katalog produktów, zestawy BOM, wyceny, ustawienia.
- **Frontend**: server-side HTML (Jinja2) + minimalny **czysty JavaScript** (dynamiczne dodawanie
  wierszy pozycji). Bez Reacta, bez build-stepu, bez node_modules.
- **PDF**: istniejący silnik `pdf_engine/generator.py` (reportlab). Wołasz `generate_offer_pdf(data, out_path)`.
- Uruchomienie: skrypty `start.command` (macOS) i `start.bat` (Windows) — tworzą venv, instalują
  zależności, startują serwer i otwierają przeglądarkę na `http://127.0.0.1:8000`.
- Wszystko działa **lokalnie i offline**. Bez chmury, bez logowania, bez kont.

---

## 3. Silnik PDF — kontrakt (GOTOWE, nie ruszaj wyglądu)

Plik: `pdf_engine/generator.py`. Funkcja publiczna:

```python
from pdf_engine.generator import generate_offer_pdf
generate_offer_pdf(data: dict, out_path: str) -> str
```

- `data` to jeden słownik (schemat niżej). Silnik sam liczy sumę materiałów, sumę końcową
  i kwotę **słownie** (funkcja `liczba_slownie`). Nie licz tego w aplikacji — przekaż surowe pozycje.
- Sekcje `spec_techniczna`, `konstrukcja`, `materialy_pomocnicze` są **opcjonalne**: bez nich
  powstaje krótka wycena (1 str.), z nimi — pełna oferta techniczna (kilka stron).
- Fonty DejaVu leżą w `pdf_engine/assets/fonts/` — muszą tam zostać (obsługa polskich znaków).
- Podgląd danych przykładowych: `python pdf_engine/generator.py` → tworzy `przyklad_oferta.pdf`.

### Schemat `data` (patrz `pdf_engine/przyklad_dane.json` — pełny przykład BUDMAX)

```jsonc
{
  "wystawca":   { "nazwa","podtytul","wordmark","wordmark_sub","nip","adres","tel","email" },
  "zamawiajacy":{ "nazwa","adres_html","kontakt_html" },      // *_html: dozwolone <br/>
  "meta":       { "tytul":"WYCENA", "numer":"01/06/2026", "data":"24.06.2026" },
  "przedmiot":  "tekst opisu przedmiotu",
  "pozycje":   [ { "nazwa","ilosc":"8 szt.", "brutto": 3150 }, ... ],   // ceny brutto
  "robocizna":  { "opis", "kwota": 4500, "vat_zwolniona": true,          // opcjonalne
                  "etapy": [ { "nazwa","kwota":720 }, ... ] },           // opcjonalny wykaz prac
  "uslugi_dodatkowe": [ { "opis", "kwota": 350 }, ... ],                 // opcjonalne (transport itp.)
  "spec_techniczna": [ { "tytul", "parametry": [["Klucz","Wartość"], ...] }, ... ],  // opcjonalne
  "konstrukcja": { "tytul","opis":[bullet_html,...], "naglowek_wykazu",
                   "elementy":[["symbol","nazwa","ilosc","jm"],...], "nota" },        // opcjonalne
  "materialy_pomocnicze": [ bullet_html, ... ],   // opcjonalne
  "klauzula_vat": "tekst (opcjonalny — jest sensowny default art. 113)",
  "warunki": [ "punkt 1", "punkt 2", ... ]        // opcjonalne (jest default)
}
```

---

## 4. Logika VAT (WAŻNE — nie zmieniać zasad)

- **Materiały**: ceny podawane i pokazywane jako **brutto** (zawierają VAT).
- **Robocizna**: **zwolniona z VAT** na podstawie **art. 113 ust. 1 ustawy o VAT** (zwolnienie
  podmiotowe). Do robocizny **nie dolicza się VAT**. Klauzula jest w sekcji III PDF (default w silniku).
- Suma końcowa = suma materiałów (brutto) + robocizna. Silnik liczy to sam.
- W UI: pole „Robocizna" ma checkbox „zwolniona z VAT" domyślnie zaznaczony.

---

## 5. Model danych (SQLite)

Zaproponowany minimalny schemat (możesz dopracować, zachowaj sens):

- `settings` — jeden wiersz: dane wystawcy (nazwa, podtytul, wordmark, wordmark_sub, nip, adres,
  tel, email), domyślna `klauzula_vat`, domyślne `warunki` (JSON), folder zapisu PDF, licznik numeracji.
- `clients` — klienci: nazwa, adres_html, kontakt_html.
- `products` — katalog: nazwa, kategoria, jm, cena_brutto, vat (bool), `spec_json` (opcjonalna
  specyfikacja techniczna jako lista par klucz–wartość).
- `boms` — zestawy elementów (np. konstrukcja BAKS): nazwa, `elementy_json` (lista [symbol,nazwa,ilosc,jm]),
  opis (bullet-y), nota. Przy dodaniu do wyceny — możliwy mnożnik ×N (np. ×2 zestawy).
- `quotes` — wyceny: numer, data (tekst), client_id, suma (do listy), oraz **`data_json`** =
  kompletny słownik `data` przekazywany do silnika. Dzięki temu edycja/duplikat/regeneracja PDF
  są trywialne (wczytaj `data_json` → `generate_offer_pdf`).

Numeracja: format `NN/MM/RRRR`, auto-inkrement w obrębie miesiąca, **edytowalny** przez użytkownika.

---

## 6. Funkcje (zakres MVP)

1. **Ustawienia wystawcy** — raz uzupełniane, trafiają do każdej wyceny.
2. **Katalog produktów** — dodaj/edytuj/usuń; przy pozycji opcjonalna specyfikacja techniczna.
   Zasilić startowo produktami z `pdf_engine/przyklad_dane.json` (JINKO 510, SinusPro Ultra-M 6500,
   VOLT LiFePO4, Schneider Acti9, konstrukcja BAKS, materiały pomocnicze).
3. **Klienci** — dodaj/edytuj (np. BUDMAX już wpisany jako przykład).
4. **Zestawy BOM** — np. konstrukcja BAKS jako gotowy wykaz z mnożnikiem ×N.
5. **Nowa wycena** — wybór klienta; dodawanie pozycji z katalogu (autouzupełnienie ceny i specyfikacji)
   lub ręcznie; ilość/cena; robocizna; auto numer+data; **na żywo licz podgląd sumy**.
6. **Generuj PDF** — przez silnik; zapis do wybranego folderu; przycisk „Otwórz PDF".
7. **Lista wycen** — szukaj, otwórz, **duplikuj** (świetne do podobnych zleceń), edytuj, usuń.
8. (miło mieć) Eksport/import `data_json` wyceny.

---

## 7. Zasady wyglądu (marka INSTAL-PAWEŁ) — NIE ZMIENIAĆ

Wygląd PDF jest zamknięty w silniku. UI aplikacji może używać tych samych kolorów dla spójności:

- Granat `#0E2233`, pomarańcz `#F39200`, niebieski `#2F7FB8`, krem `#F5F1E6`, jasne tło `#E9F0F6`.
- Nagłówek PDF: granatowa „siatka" + pomarańczowa błyskawica + wordmark `INSTAL-PAWEL` /
  `USŁUGI ELEKTRYCZNE`, po prawej tytuł (WYCENA), numer i data.
- **Nie** dodawaj do PDF elementów, które psują układ (np. długie napisy wyjeżdżające poza nagłówek).

---

## 8. Konwencje i granice

- Cały interfejs i komunikaty **po polsku**.
- Kwoty w zł, format `1 234,56 zł` (spacja jako separator tysięcy, przecinek dziesiętny) — tak jak w silniku.
- Waliduj dane wejściowe (kwoty ≥ 0), ale nie blokuj pracy nadgorliwie.
- **Nie** modyfikuj `pdf_engine/generator.py` w części wizualnej. Jeśli trzeba nowe pole w PDF —
  dodaj je do schematu `data` i do silnika ostrożnie, testując render (patrz punkt 9).
- Trzymaj kod prosty i czytelny; komentarze po polsku mile widziane.

## 9. Testy / weryfikacja (obowiązkowo przed „gotowe")

- Po każdej zmianie generowania: uruchom `python pdf_engine/generator.py` i **obejrzyj PDF**
  (sumy, polskie znaki, podział stron, czy nic nie wyjeżdża poza ramkę).
- Sprawdź ścieżkę: pozycje z katalogu → wycena → PDF → suma i „słownie" zgadzają się.
- Test krótkiej wyceny (bez sekcji technicznych) i pełnej oferty (z sekcjami).

## 10. Wydania i aktualizacje (repo GitHub)

- Repo: `git@github.com:MatteoBarzotto/INSTAL-PAWEL.git`. Praca bieżąca na **`main`**.
- Aplikacja Pawła aktualizuje się sama z brancha **`stable`** (Ustawienia → „Aktualizacje
  programu"): porównuje `wersja.txt`, pobiera ZIP repo przez HTTPS (bez gita u Pawła),
  robi kopię `dane.db`, podmienia pliki programu (nigdy bazy/.venv), robi `pip install`
  i restartuje się. Logika: `updater.py`.
- **Procedura wydania sprawdzonej wersji:**
  1. podbij numer w `wersja.txt` (format X.Y.Z, porównanie numeryczne),
  2. commit na `main`, przetestuj (punkt 9),
  3. `git push origin main && git push origin main:stable`.
- Bez podbicia `wersja.txt` Paweł nie zobaczy aktualizacji. `dane.db` jest w `.gitignore`
  i aktualizacja nigdy jej nie rusza.

## 11. Komendy

```bash
# instalacja
python -m venv .venv && source .venv/bin/activate    # (Windows: .venv\Scripts\activate)
pip install -r pdf_engine/requirements.txt -r requirements.txt

# podgląd samego silnika PDF na danych przykładowych
python pdf_engine/generator.py

# uruchomienie aplikacji (docelowo)
python app.py            # http://127.0.0.1:8000
```
