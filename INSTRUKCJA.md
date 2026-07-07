# INSTAL-PAWEŁ — program do wycen (instrukcja)

Prosty program, w którym tworzysz gotowe oferty PDF: wybierasz klienta, dodajesz pozycje
z katalogu, wpisujesz ilości i ceny, klikasz **„Generuj PDF"**. Wszystko działa na Twoim
komputerze, bez internetu.

---

## 1. Jak uruchomić

### macOS
1. Otwórz folder `INSTAL-PAWEL`.
2. Kliknij dwukrotnie plik **`start.command`**.
   - Za pierwszym razem instalacja potrwa około minuty (program przygotowuje środowisko).
   - Gdyby macOS napisał, że „nie można otworzyć, bo pochodzi od niezidentyfikowanego dewelopera":
     kliknij plik **prawym przyciskiem → Otwórz → Otwórz**.
3. Przeglądarka otworzy się sama pod adresem `http://127.0.0.1:8000`.

### Windows
1. Otwórz folder `INSTAL-PAWEL`.
2. Kliknij dwukrotnie plik **`start.bat`**.
   - Potrzebny jest Python 3 (jeśli go nie ma: pobierz z https://www.python.org/downloads/
     i przy instalacji zaznacz **„Add Python to PATH"**).
3. Przeglądarka otworzy się sama.

> **Wyłączanie programu:** zamknij czarne okno (Terminal / wiersz poleceń), które otworzyło się
> razem z programem.

---

## 2. Pierwsza wycena w 5 krokach

1. Kliknij **„+ Nowa wycena"** (prawy górny róg).
2. **Wybierz klienta** z listy (np. BUDMAX jest już wpisany) lub kliknij „+ Nowy klient".
3. **Dodaj pozycje**: w każdym wierszu wybierz produkt z katalogu — nazwa, cena i (jeśli jest)
   specyfikacja techniczna podpowiedzą się same. Popraw ilość i ewentualnie cenę.
   Przycisk **„+ Dodaj pozycję"** dokłada kolejny wiersz.
4. Wpisz **robociznę** (opis + kwota). Checkbox „zwolniona z VAT" jest domyślnie zaznaczony.
5. Kliknij **„Zapisz i generuj PDF"**. Gotowy plik zapisze się w Twoim folderze wycen
   i otworzy automatycznie.

Numer nadaje się sam (format `NN/MM/RRRR`), ale możesz go zmienić. Suma liczy się na bieżąco na dole.

---

## 3. Pełna oferta techniczna (opcjonalnie)

W sekcji **„Sekcje techniczne"** możesz:
- **dołączyć zestaw konstrukcji (BOM)** — np. konstrukcję BAKS, z mnożnikiem ×N (ilości elementów
  przemnożą się automatycznie),
- **dołączyć „Materiały pomocnicze"** (lista jest podpowiadana z ustawień).

Bez tych sekcji powstaje krótka wycena (1 strona). Z nimi — pełna oferta na kilka stron.

---

## 3a. Faktury

Zakładka **„Faktury"** to osobny typ dokumentu — estetyczna faktura A4 (sprzedawca **zwolniony
z VAT**, art. 113, więc bez kolumn VAT/brutto: jest `Cena` i `Wartość`).

1. Kliknij **„+ Nowa faktura"**. Dane sprzedawcy, numer (`FV / NN / MM / RRRR`) i daty podpowiedzą się same.
2. Klikaj wprost w pola na fakturze, aby je edytować. Nabywcę możesz wstawić z bazy klientów
   (lista **„Wstaw nabywcę z bazy…"** na górze).
3. Dodawaj pozycje przyciskiem **„＋ Dodaj pozycję"** — `Wartość`, `Do zapłaty` i kwota **słownie**
   liczą się automatycznie.
4. **„💾 Zapisz"** zapisuje fakturę na liście. **„🖨️ Zapisz i drukuj / PDF"** zapisuje i otwiera
   okno druku — wybierz tam **„Zapisz jako PDF"**.
5. Przełączniki na górze (Kratka / REGON / Konto bank. / Klauzula) włączają/wyłączają elementy faktury.
   Możesz też wyeksportować/zaimportować fakturę jako plik `.json`.

Na liście faktur masz **Duplikuj** (kopia z nowym numerem) i **Usuń**.

**Najszybsza droga:** zrób wycenę, a gdy klient ją zaakceptuje — na liście wycen kliknij
**„→ Faktura"**. Klient, pozycje i robocizna przeniosą się na fakturę automatycznie
(termin płatności podpowie się +14 dni).

**Statusy:**
- przy wycenie ustawiasz status z listy: *szkic / wysłana / zaakceptowana / odrzucona*,
- przy fakturze klikasz w kolorową etykietę, aby przełączyć *niezapłacona ↔ zapłacona*.
  Gdy minie termin płatności niezapłaconej faktury, etykieta zrobi się **czerwona: „po terminie!"** —
  od razu widać, kto zalega.

**Cennik robocizny:** w Katalogu produkty z kategorią **„Robocizna"** (np. punkt oświetleniowy,
gniazdo, pomiary) tworzą Twój cennik. W wycenie, w sekcji Robocizna, wybierz pozycję z cennika,
podaj ilość i kliknij **„+ Dolicz"** — kwota i opis uzupełnią się same. Ceny startowe popraw pod siebie.

---

## 4. Pozostałe zakładki

- **Katalog** — Twoje produkty (moduły, inwertery, akumulatory…). Możesz dodawać, edytować i usuwać.
  Przy produkcie możesz wpisać specyfikację techniczną (format „Klucz: Wartość", jeden w wierszu) —
  trafi do sekcji technicznej oferty.
- **Klienci** — lista klientów (nazwa, adres, osoba kontaktowa).
- **Zestawy** — gotowe wykazy elementów konstrukcji (BOM). Elementy wpisujesz w formacie
  `symbol | nazwa | ilość | j.m.` (jeden w wierszu).
- **Ustawienia** — Twoje dane (nazwa, NIP, adres, telefon, e-mail), domyślne warunki i materiały,
  oraz **folder zapisu plików PDF**.

---

## 5. Lista wycen

Na stronie głównej masz wszystkie wyceny. Przy każdej:
- **Generuj PDF** — ponownie tworzy i otwiera plik,
- **Edytuj** — poprawiasz i zapisujesz,
- **Duplikuj** — tworzy kopię z nowym numerem (świetne do podobnych zleceń — kolejna oferta w 2 minuty),
- **Usuń** — kasuje wycenę.

---

## 6. Gdzie są moje dane?

- Wszystkie wyceny, klienci i katalog: plik **`dane.db`** w folderze programu.
- Wygenerowane oferty PDF: folder ustawiony w **Ustawieniach** (domyślnie `Wyceny-InstalPawel`
  w Twoim katalogu domowym).

**Kopia zapasowa:** w **Ustawieniach** kliknij „💾 Zrób kopię zapasową teraz" — kopia bazy
z datą w nazwie trafi do folderu „Kopie zapasowe" (obok PDF-ów). Rób to np. raz w tygodniu,
a folder co jakiś czas przegraj na pendrive.
