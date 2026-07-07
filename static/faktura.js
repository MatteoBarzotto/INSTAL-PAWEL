/* =============================================================================
   Faktura INSTAL-PAWEŁ — logika edytora (operuje na `items` + DOM).
   Czyste funkcje kwot (parseNum, fmt, kwotaSlownie) pochodzą z lib/kwoty.js.
   Persistencja: API serwera (/api/faktura/zapisz) zamiast localStorage.
   ========================================================================== */
"use strict";

let items = [];
let currentId = (typeof FAKTURA_ID !== "undefined") ? FAKTURA_ID : null;

/* ---------------------------------------------------- render pozycji */
function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function autoGrow(el) { el.style.height = "auto"; el.style.height = el.scrollHeight + "px"; }

function itemRowHTML(it, i) {
  return `<tr>
    <td class="lp" data-label="Poz.">${i + 1}</td>
    <td data-label="Nazwa usługi / towaru"><input class="f" style="width:100%" placeholder="np. Montaż instalacji elektrycznej" value="${esc(it.nazwa)}" oninput="upd(${i},'nazwa',this.value)"></td>
    <td class="ctr" data-label="Ilość"><input class="f w-ilosc" inputmode="decimal" value="${esc(it.ilosc)}" oninput="upd(${i},'ilosc',this.value)"></td>
    <td class="ctr" data-label="J.m."><input class="f w-jm" placeholder="szt." value="${esc(it.jm)}" oninput="upd(${i},'jm',this.value)"></td>
    <td class="num" data-label="Cena"><input class="f w-cena" inputmode="decimal" value="${esc(it.cena)}" oninput="upd(${i},'cena',this.value)"></td>
    <td class="num wartcell" id="wart_${i}" data-label="Wartość" style="color:#16263D;font-weight:600;">0,00</td>
    <td class="colactions no-print"><button class="delbtn" title="Usuń pozycję" onclick="usunPozycje(${i})">✕</button></td>
  </tr>`;
}
function renderItems() {
  document.getElementById("itemsBody").innerHTML = items.map(itemRowHTML).join("");
  oblicz();
}
function upd(i, key, val) { items[i][key] = val; oblicz(); }
function dodajPozycje() { items.push({ nazwa: "", ilosc: "1", jm: "usł.", cena: "" }); renderItems(); }
function usunPozycje(i) { items.splice(i, 1); if (items.length === 0) dodajPozycje(); else renderItems(); }

/* ---------------------------------------------------- obliczenia (bez VAT) */
function oblicz() {
  let suma = 0;
  items.forEach((it, i) => {
    const wart = parseNum(it.ilosc) * parseNum(it.cena);
    const we = document.getElementById("wart_" + i);
    if (we) we.textContent = fmt(wart);
    suma += wart;
  });
  document.getElementById("doZaplaty").textContent = fmt(suma) + " PLN";
  document.getElementById("slownie").textContent = kwotaSlownie(suma);
}

/* ---------------------------------------------------- przełączniki widoczności */
function render() {
  document.getElementById("blueprint").style.display = document.getElementById("t_blueprint").checked ? "block" : "none";
  document.getElementById("s_regon_row").style.display = document.getElementById("t_regon").checked ? "" : "none";
  document.getElementById("n_regon_row").style.display = document.getElementById("t_regon").checked ? "" : "none";
  document.getElementById("p_bank_row").style.display = document.getElementById("t_bank").checked ? "" : "none";
  document.getElementById("klauzulaBox").style.display = document.getElementById("t_klauzula").checked ? "" : "none";
  autoGrow(document.getElementById("klauzula"));
}

/* ---------------------------------------------------- stan (kontrakt zbierzStan/wczytajStan) */
const FIELD_IDS = ["m_numer", "m_wyst", "m_sprz", "m_term", "s_nazwa", "s_adres", "s_nip", "s_regon",
  "n_nazwa", "n_adres", "n_nip", "n_regon", "p_sposob", "p_bank", "p_konto", "klauzula", "f_tel", "f_mail"];

function zbierzStan() {
  const o = {
    id: currentId,
    fields: {},
    items: items,
    toggles: {
      blueprint: document.getElementById("t_blueprint").checked,
      regon: document.getElementById("t_regon").checked,
      bank: document.getElementById("t_bank").checked,
      klauzula: document.getElementById("t_klauzula").checked,
    },
  };
  FIELD_IDS.forEach((id) => (o.fields[id] = document.getElementById(id).value));
  return o;
}
function wczytajStan(o) {
  FIELD_IDS.forEach((id) => { if (o.fields && o.fields[id] != null) document.getElementById(id).value = o.fields[id]; });
  items = (o.items && o.items.length) ? JSON.parse(JSON.stringify(o.items)) : [{ nazwa: "", ilosc: "1", jm: "usł.", cena: "" }];
  if (o.toggles) {
    document.getElementById("t_blueprint").checked = !!o.toggles.blueprint;
    document.getElementById("t_regon").checked = !!o.toggles.regon;
    document.getElementById("t_bank").checked = !!o.toggles.bank;
    document.getElementById("t_klauzula").checked = !!o.toggles.klauzula;
  }
  renderItems(); render();
}

/* ---------------------------------------------------- zapis na serwer */
function zapiszFakture(cicho) {
  return fetch("/api/faktura/zapisz", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(zbierzStan()),
  }).then((r) => r.json()).then((d) => {
    if (!d.ok) throw new Error("Zapis nie powiódł się");
    currentId = d.id;
    if (typeof zmianyZapisane === "function") zmianyZapisane();
    // po pierwszym zapisie podmień URL na /faktura/<id>/edytuj (bez przeładowania)
    if (history.replaceState) history.replaceState(null, "", "/faktura/" + d.id + "/edytuj");
    if (!cicho) flashInfo("Zapisano fakturę.");
    return d.id;
  }).catch((e) => { alert("Błąd zapisu: " + e.message); throw e; });
}

function drukujPDF() {
  // najpierw zapis (pewność, że lista/baza są aktualne), potem druk do PDF
  zapiszFakture(true).then(() => setTimeout(() => window.print(), 150)).catch(() => {});
}

/* krótki komunikat w pasku narzędzi (bez alertu) */
function flashInfo(txt) {
  const hint = document.getElementById("hint");
  const prev = hint.textContent;
  hint.textContent = "✅ " + txt;
  setTimeout(() => (hint.textContent = prev), 2500);
}

/* ---------------------------------------------------- nabywca z bazy klientów */
function wybierzNabywce(id) {
  if (!id) return;
  const c = (CLIENTS || []).find((x) => String(x.id) === String(id));
  if (!c) return;
  document.getElementById("n_nazwa").value = c.nazwa || "";
  // adres_html może zawierać <br/> — zamień na przecinki w jednym wierszu
  document.getElementById("n_adres").value = (c.adres_html || "").replace(/<br\s*\/?>/gi, ", ").replace(/\s*,\s*$/, "");
  oblicz();
  document.getElementById("clientPicker").value = "";
}

/* ---------------------------------------------------- eksport / import JSON */
function eksportJSON() {
  const data = JSON.stringify(zbierzStan(), null, 2);
  const blob = new Blob([data], { type: "application/json" });
  const a = document.createElement("a");
  const nazwa = (document.getElementById("m_numer").value.trim() || "faktura").replace(/[\\/:*?"<>|]/g, "-");
  a.href = URL.createObjectURL(blob); a.download = nazwa + ".json"; a.click(); URL.revokeObjectURL(a.href);
}
function importJSON(ev) {
  const file = ev.target.files[0]; if (!file) return;
  const r = new FileReader();
  r.onload = () => { try { wczytajStan(JSON.parse(r.result)); } catch (e) { alert("Nieprawidłowy plik JSON."); } };
  r.readAsText(file); ev.target.value = "";
}

/* ---------------------------------------------------- start */
function stosujDefaults() {
  document.getElementById("s_nazwa").value = DEFAULTS.seller.nazwa || "";
  document.getElementById("s_adres").value = DEFAULTS.seller.adres || "";
  document.getElementById("s_nip").value = DEFAULTS.seller.nip || "";
  document.getElementById("p_sposob").value = "Przelew";
  document.getElementById("klauzula").value = DEFAULTS.klauzula || "";
  document.getElementById("f_tel").value = DEFAULTS.tel || "";
  document.getElementById("f_mail").value = DEFAULTS.mail || "";
  document.getElementById("m_numer").value = DOMYSLNY_NUMER || "";
  document.getElementById("m_wyst").value = DZIS_ISO;
  document.getElementById("m_sprz").value = DZIS_ISO;
}

function init() {
  if (STAN) {
    wczytajStan(STAN);
  } else {
    stosujDefaults();
    items = [{ nazwa: "", ilosc: "1", jm: "usł.", cena: "" }];
    renderItems(); render();
  }
}
init();
