/* =============================================================================
   Wspólna biblioteka logiki kwot (INSTAL-PAWEŁ) — czyste funkcje, bez DOM.
   Wyniesiona z modułu faktury (handoff sekcja 5B). Nadaje się do użycia
   w każdym typie dokumentu (faktury, oferty, paragony…).

   Publiczne:  parseNum(v), fmt(n), kwotaSlownie(amount)
   Dostępne jako globalne funkcje oraz przez obiekt window.Kwoty.
   ========================================================================== */
(function (root) {
  "use strict";

  /** "12,50" / "1 200" -> Number (akceptuje przecinek i spacje). */
  function parseNum(v) {
    if (v == null) return 0;
    return parseFloat(String(v).replace(/\s/g, "").replace(",", ".")) || 0;
  }

  /** Number -> format PL "1 234,56". */
  function fmt(n) {
    return (Math.round(n * 100) / 100).toLocaleString("pl-PL", {
      minimumFractionDigits: 2, maximumFractionDigits: 2,
    });
  }

  // ---- kwota słownie (PL) ----
  var _jed = ["zero", "jeden", "dwa", "trzy", "cztery", "pięć", "sześć", "siedem", "osiem", "dziewięć"];
  var _nast = ["dziesięć", "jedenaście", "dwanaście", "trzynaście", "czternaście", "piętnaście",
               "szesnaście", "siedemnaście", "osiemnaście", "dziewiętnaście"];
  var _dzies = ["", "", "dwadzieścia", "trzydzieści", "czterdzieści", "pięćdziesiąt",
                "sześćdziesiąt", "siedemdziesiąt", "osiemdziesiąt", "dziewięćdziesiąt"];
  var _setki = ["", "sto", "dwieście", "trzysta", "czterysta", "pięćset",
                "sześćset", "siedemset", "osiemset", "dziewięćset"];
  var _grupy = [["", "", ""], ["tysiąc", "tysiące", "tysięcy"],
                ["milion", "miliony", "milionów"], ["miliard", "miliardy", "miliardów"]];

  /** Wybór formy odmiany rzeczownika wg liczby. */
  function _odm(n, f) {
    n = Math.abs(n);
    if (n === 1) return f[0];
    var d = n % 10, s = n % 100;
    if (d >= 2 && d <= 4 && !(s >= 12 && s <= 14)) return f[1];
    return f[2];
  }

  /** Liczba 0–999 słownie. */
  function _setkiSl(n) {
    var o = [], h = Math.floor(n / 100), r = n % 100, d = Math.floor(r / 10), u = r % 10;
    if (h) o.push(_setki[h]);
    if (r >= 10 && r < 20) o.push(_nast[r - 10]);
    else { if (d) o.push(_dzies[d]); if (u) o.push(_jed[u]); }
    return o.join(" ");
  }

  /** Liczba całkowita słownie (obsługa do miliardów). */
  function _liczbaSl(n) {
    n = Math.floor(n);
    if (n === 0) return "zero";
    var parts = [], g = 0;
    while (n > 0) {
      var t = n % 1000;
      if (t > 0) {
        var s;
        if (t === 1 && g === 1) { s = "tysiąc"; }        // "tysiąc" zamiast "jeden tysiąc"
        else { s = _setkiSl(t); if (g > 0) s += " " + _odm(t, _grupy[g]); }
        parts.unshift(s);
      }
      n = Math.floor(n / 1000); g++;
    }
    return parts.join(" ").replace(/\s+/g, " ").trim();
  }

  /** Kwota -> słownie PL, np. "dwa tysiące … złotych 50/100". */
  function kwotaSlownie(amount) {
    var zl = Math.floor(amount), gr = Math.round((amount - zl) * 100);
    if (gr === 100) { zl += 1; gr = 0; }
    var grStr = String(gr).padStart(2, "0");
    return _liczbaSl(zl) + " " + _odm(zl, ["złoty", "złote", "złotych"]) + " " + grStr + "/100";
  }

  var API = { parseNum: parseNum, fmt: fmt, kwotaSlownie: kwotaSlownie };
  root.Kwoty = API;
  // zgodność wsteczna: udostępnij też jako globalne funkcje
  root.parseNum = parseNum;
  root.fmt = fmt;
  root.kwotaSlownie = kwotaSlownie;
})(typeof window !== "undefined" ? window : this);
