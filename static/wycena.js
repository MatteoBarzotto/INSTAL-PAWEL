/* Edytor wyceny INSTAL-PAWEŁ — czysty JS (bez frameworków). */

const $ = (id) => document.getElementById(id);
const byId = (arr, id) => arr.find((x) => String(x.id) === String(id));

function money(v) {
  v = Number(v) || 0;
  return v.toLocaleString("pl-PL", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " zł";
}

/* ---------------------------------------------------- pozycje (wiersze) */
function dodajWiersz(dane) {
  const tpl = $("row-tpl").content.cloneNode(true);
  const tr = tpl.querySelector("tr");
  $("pozycje-body").appendChild(tr);
  if (dane) {
    tr.querySelector(".p-nazwa").value = dane.nazwa || "";
    tr.querySelector(".p-ilosc").value = dane.ilosc || "";
    tr.querySelector(".p-brutto").value = dane.brutto != null ? dane.brutto : 0;
    if (dane.spec && dane.spec.length) {
      tr._spec = dane.spec;
      tr._specTytul = dane.spec_tytul || dane.nazwa;
      pokazSpec(tr, true);
      tr.querySelector(".p-spec").checked = dane.include_spec !== false;
    }
    if (dane.product_id) tr.querySelector(".p-prod").value = dane.product_id;
  }
  przeliczSume();
  return tr;
}

function usunWiersz(btn) {
  btn.closest("tr").remove();
  przeliczSume();
}

function pokazSpec(tr, ma) {
  tr.querySelector(".spec-wrap").classList.toggle("hidden", !ma);
  tr.querySelector(".spec-none").classList.toggle("hidden", ma);
}

function wybierzProdukt(sel) {
  const tr = sel.closest("tr");
  const p = byId(PRODUCTS, sel.value);
  if (!p) { // wpis ręczny
    tr._spec = null; pokazSpec(tr, false);
    return;
  }
  tr.querySelector(".p-nazwa").value = p.nazwa;
  tr.querySelector(".p-brutto").value = p.cena_brutto;
  if (!tr.querySelector(".p-ilosc").value) {
    tr.querySelector(".p-ilosc").value = p.jm ? ("1 " + p.jm) : "";
  }
  const spec = p.spec_json ? JSON.parse(p.spec_json) : null;
  if (spec && spec.length) {
    tr._spec = spec; tr._specTytul = p.nazwa;
    pokazSpec(tr, true); tr.querySelector(".p-spec").checked = true;
  } else {
    tr._spec = null; pokazSpec(tr, false);
  }
  przeliczSume();
}

/* ---------------------------------------------------- suma na żywo */
function przeliczSume() {
  let mat = 0;
  document.querySelectorAll("#pozycje-body tr").forEach((tr) => {
    mat += Number(tr.querySelector(".p-brutto").value) || 0;
  });
  const rob = Number($("rob_kwota").value) || 0;
  $("sum-mat").textContent = money(mat);
  $("sum-rob").textContent = money(rob);
  $("sum-total").textContent = money(mat + rob);
}

/* ---------------------------------------------------- cennik robocizny */
function dodajZCennika() {
  const sel = $("rob_cennik");
  const r = byId(ROBOCIZNA_CENNIK, sel.value);
  if (!r) return;
  const il = Math.max(1, Number($("rob_ilosc").value) || 1);
  // dolicz kwotę do robocizny i dopisz pozycję do opisu (np. "10× punkt oświetleniowy")
  $("rob_kwota").value = ((Number($("rob_kwota").value) || 0) + il * r.cena_brutto).toFixed(2);
  const bez = r.nazwa.replace(/\s*\(montaż\)\s*$/i, "");
  const wpis = il + "× " + bez.charAt(0).toLowerCase() + bez.slice(1); // mała litera tylko na początku
  const opis = $("rob_opis").value.trim();
  $("rob_opis").value = opis ? opis + ", " + wpis : "Robocizna: " + wpis;
  $("rob_ilosc").value = 1;
  przeliczSume();
}

/* ---------------------------------------------------- pokazywanie sekcji */
function toggle(id, chk) { $(id).classList.toggle("hidden", !chk.checked); }
function toggleNowyKlient() { $("nowy-klient").classList.toggle("hidden"); }

function zapiszNowegoKlienta() {
  const nazwa = $("nk_nazwa").value.trim();
  if (!nazwa) { alert("Podaj nazwę klienta."); return; }
  const body = {
    nazwa,
    adres_html: $("nk_adres").value.trim().replace(/\n/g, "<br/>"),
    kontakt_html: $("nk_kontakt").value.trim().replace(/\n/g, "<br/>"),
  };
  fetch("/klienci/zapisz", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  }).then((r) => r.json()).then((d) => {
    const opt = new Option(d.nazwa, d.id, true, true);
    $("client_id").add(opt);
    toggleNowyKlient();
    $("nk_nazwa").value = $("nk_adres").value = $("nk_kontakt").value = "";
  }).catch((e) => alert("Błąd zapisu klienta: " + e));
}

/* ---------------------------------------------------- zbieranie payloadu */
function zbierzPayload() {
  const pozycje = [];
  document.querySelectorAll("#pozycje-body tr").forEach((tr) => {
    const nazwa = tr.querySelector(".p-nazwa").value.trim();
    if (!nazwa) return;
    const item = {
      product_id: tr.querySelector(".p-prod").value || null,
      nazwa,
      ilosc: tr.querySelector(".p-ilosc").value.trim(),
      brutto: Number(tr.querySelector(".p-brutto").value) || 0,
    };
    if (tr._spec && tr._spec.length) {
      item.spec = tr._spec;
      item.spec_tytul = tr._specTytul || nazwa;
      item.include_spec = tr.querySelector(".p-spec").checked;
    }
    pozycje.push(item);
  });

  return {
    id: $("quote-id").value || null,
    numer: $("numer").value.trim(),
    data: $("data").value.trim(),
    tytul: $("tytul").value.trim() || "WYCENA",
    przedmiot: $("przedmiot").value.trim(),
    client_id: $("client_id").value || null,
    pozycje,
    robocizna: {
      opis: $("rob_opis").value.trim() || "Robocizna",
      kwota: Number($("rob_kwota").value) || 0,
      vat_zwolniona: $("rob_vat").checked,
    },
    include_konstrukcja: $("inc_konstrukcja").checked,
    bom_id: $("bom_id") ? $("bom_id").value || null : null,
    mnoznik: Number($("mnoznik") ? $("mnoznik").value : 1) || 1,
    include_materialy: $("inc_materialy").checked,
    materialy: $("materialy").value.split("\n").map((s) => s.trim()).filter(Boolean),
    warunki: $("warunki").value.split("\n").map((s) => s.trim()).filter(Boolean),
  };
}

/* ---------------------------------------------------- zapis + PDF */
function zapisz(zGenerowaniem) {
  const payload = zbierzPayload();
  if (!payload.pozycje.length) { alert("Dodaj przynajmniej jedną pozycję."); return; }
  fetch("/api/wycena/zapisz", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  }).then((r) => r.json()).then((d) => {
    if (!d.ok) { alert("Nie udało się zapisać."); return; }
    $("quote-id").value = d.id;
    if (!zGenerowaniem) { zmianyZapisane(); window.location = "/wyceny"; return; }
    fetch(`/api/wycena/${d.id}/pdf`, { method: "POST" })
      .then((r) => r.json()).then((p) => {
        if (!p.ok) { alert(p.blad || "Błąd PDF."); return; }
        zmianyZapisane(); window.location = "/wyceny";
      });
  }).catch((e) => alert("Błąd: " + e));
}

/* ---------------------------------------------------- wypełnianie formularza */
function hydrate() {
  // domyślne warunki / materiały (nowa wycena)
  $("warunki").value = (DOMYSLNE_WARUNKI || []).join("\n");
  $("materialy").value = (DOMYSLNE_MATERIALY || []).join("\n");

  const f = QUOTE_DATA && QUOTE_DATA._form ? QUOTE_DATA._form : null;
  if (!f) { dodajWiersz(); przeliczSume(); return; }

  if (f.numer) $("numer").value = f.numer;
  if (f.data) $("data").value = f.data;
  if (f.tytul) $("tytul").value = f.tytul;
  if (f.przedmiot) $("przedmiot").value = f.przedmiot;
  if (f.client_id) $("client_id").value = f.client_id;

  (f.pozycje || []).forEach(dodajWiersz);
  if (!(f.pozycje || []).length) dodajWiersz();

  if (f.robocizna) {
    $("rob_opis").value = f.robocizna.opis || "";
    $("rob_kwota").value = f.robocizna.kwota || 0;
    $("rob_vat").checked = f.robocizna.vat_zwolniona !== false;
  }
  if (f.include_konstrukcja) {
    $("inc_konstrukcja").checked = true; $("konstr-box").classList.remove("hidden");
    if (f.bom_id && $("bom_id")) $("bom_id").value = f.bom_id;
    if ($("mnoznik")) $("mnoznik").value = f.mnoznik || 1;
  }
  if (f.include_materialy) {
    $("inc_materialy").checked = true; $("mat-box").classList.remove("hidden");
    if (f.materialy && f.materialy.length) $("materialy").value = f.materialy.join("\n");
  }
  if (f.warunki && f.warunki.length) $("warunki").value = f.warunki.join("\n");
  przeliczSume();
}

document.addEventListener("DOMContentLoaded", hydrate);
