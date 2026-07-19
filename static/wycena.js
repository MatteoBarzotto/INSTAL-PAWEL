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

/* ---------------------------------------------------- dodatkowe usługi */
function dodajUsluge(dane) {
  const div = document.createElement("div");
  div.className = "row-rob usluga-row";
  div.innerHTML =
    '<label class="grow">Opis usługi ' +
    '<input class="u-opis" placeholder="np. Transport materiałów / wynajem podnośnika"></label>' +
    '<label>Kwota (zł) ' +
    '<input class="u-kwota" type="number" step="0.01" min="0" value="0" oninput="przeliczSume()"></label>' +
    '<button type="button" class="btn btn-sm btn-danger" onclick="usunUsluge(this)">✕</button>';
  $("uslugi-body").appendChild(div);
  if (dane) {
    div.querySelector(".u-opis").value = dane.opis || "";
    div.querySelector(".u-kwota").value = dane.kwota != null ? dane.kwota : 0;
  }
  przeliczSume();
}

function usunUsluge(btn) {
  btn.closest(".usluga-row").remove();
  przeliczSume();
}

function sumaUslug() {
  let s = 0;
  document.querySelectorAll("#uslugi-body .u-kwota").forEach((el) => {
    s += Number(el.value) || 0;
  });
  return s;
}

/* ---------------------------------------------------- etapy robocizny */
function dodajEtap(dane) {
  const tpl = $("rob-tpl").content.cloneNode(true);
  const tr = tpl.querySelector("tr");
  $("rob-body").appendChild(tr);
  if (dane) {
    tr.querySelector(".r-nazwa").value = dane.nazwa || "";
    // starsze wyceny miały ilość × cena jedn. — przelicz na jedną wartość
    const kwota = dane.kwota != null ? Number(dane.kwota)
      : (Number(dane.ilosc) || 0) * (Number(dane.cena) || 0);
    tr.querySelector(".r-kwota").value = kwota || 0;
  }
  przeliczSume();
  return tr;
}

function usunEtap(btn) {
  btn.closest("tr").remove();
  przeliczSume();
}

function wybierzEtapCennika(sel) {
  const tr = sel.closest("tr");
  const r = byId(ROBOCIZNA_CENNIK, sel.value);
  if (!r) return;
  tr.querySelector(".r-nazwa").value = r.nazwa;
  tr.querySelector(".r-kwota").value = r.cena_brutto;
  przeliczSume();
}

function sumaRobocizny() {
  let s = 0;
  document.querySelectorAll("#rob-body .r-kwota").forEach((el) => {
    s += Number(el.value) || 0;
  });
  return s;
}

/* ---------------------------------------------------- suma na żywo */
function przeliczSume() {
  let mat = 0;
  document.querySelectorAll("#pozycje-body tr").forEach((tr) => {
    mat += Number(tr.querySelector(".p-brutto").value) || 0;
  });
  const rob = sumaRobocizny();
  const uslugi = sumaUslug();
  $("sum-mat").textContent = money(mat);
  $("sum-rob").textContent = money(rob);
  $("sum-uslugi").textContent = money(uslugi);
  $("sum-uslugi-box").classList.toggle("hidden", uslugi <= 0);
  $("sum-total").textContent = money(mat + rob + uslugi);
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
      vat_zwolniona: $("rob_vat").checked,
      etapy: Array.from(document.querySelectorAll("#rob-body tr"))
        .map((tr) => ({
          nazwa: tr.querySelector(".r-nazwa").value.trim(),
          kwota: Number(tr.querySelector(".r-kwota").value) || 0,
        }))
        .filter((e) => e.nazwa || e.kwota > 0),
    },
    uslugi_dodatkowe: Array.from(document.querySelectorAll("#uslugi-body .usluga-row"))
      .map((row) => ({
        opis: row.querySelector(".u-opis").value.trim(),
        kwota: Number(row.querySelector(".u-kwota").value) || 0,
      }))
      .filter((u) => u.kwota > 0 || u.opis),
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
  if (!f) { dodajWiersz(); dodajEtap(); przeliczSume(); return; }

  if (f.numer) $("numer").value = f.numer;
  if (f.data) $("data").value = f.data;
  if (f.tytul) $("tytul").value = f.tytul;
  if (f.przedmiot) $("przedmiot").value = f.przedmiot;
  if (f.client_id) $("client_id").value = f.client_id;

  (f.pozycje || []).forEach(dodajWiersz);
  if (!(f.pozycje || []).length) dodajWiersz();

  if (f.robocizna) {
    $("rob_vat").checked = f.robocizna.vat_zwolniona !== false;
    if (f.robocizna.etapy && f.robocizna.etapy.length) {
      f.robocizna.etapy.forEach(dodajEtap);
    } else if (Number(f.robocizna.kwota) > 0) {
      // stara wycena (jeden opis + kwota) -> jeden etap
      dodajEtap({ nazwa: f.robocizna.opis || "Robocizna", kwota: Number(f.robocizna.kwota) });
    }
  }
  (f.uslugi_dodatkowe || []).forEach(dodajUsluge);
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
