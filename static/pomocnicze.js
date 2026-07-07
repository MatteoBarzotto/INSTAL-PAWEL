/* INSTAL-PAWEŁ — wspólne drobiazgi UI (ładowane w base.html) */

/* Szukajka na listach: filtruje wiersze tabeli .grid po wpisanym tekście. */
function filtrujTabele(input) {
  const q = input.value.toLowerCase().trim();
  document.querySelectorAll("table.grid tbody tr").forEach((tr) => {
    tr.style.display = tr.textContent.toLowerCase().includes(q) ? "" : "none";
  });
}

/* Ostrzeżenie przed utratą niezapisanych zmian.
   Formularz/kontener z klasą .pilnuj włącza pilnowanie; zapis (submit lub
   wywołanie zmianyZapisane() z JS) wyłącza ostrzeżenie. */
let _brudny = false;
function zmianyZapisane() { _brudny = false; }
document.addEventListener("DOMContentLoaded", () => {
  const el = document.querySelector(".pilnuj");
  if (!el) return;
  el.addEventListener("input", () => { _brudny = true; });
  el.addEventListener("change", () => { _brudny = true; });
  if (el.tagName === "FORM") el.addEventListener("submit", zmianyZapisane);
  window.addEventListener("beforeunload", (e) => {
    if (_brudny) { e.preventDefault(); e.returnValue = ""; }
  });
});
