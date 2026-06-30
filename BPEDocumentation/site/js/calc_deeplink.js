/* BPE Emerald — damage-calculator deep link.
 *
 * The interactive map links a trainer's Pokémon to the calculator with
 *     calc.html#mon=<encoded JSON {s,l,c,tn,m}>
 * where s=species, l=level, c=trainer class, tn=trainer name, m=moves[].
 * (calc.html forwards location.hash on to calc/index.html.)
 *
 * This loads that exact set onto the DEFENDER (#p2) side by selecting it in the
 * opposing set-selector, reusing the calculator's own set-loading code path
 * (the `.set-selector` change handler in shared_controls.js). The trainer sets
 * live in SETDEX_BW (built from formatted_sets by showdown_hooks.js), keyed
 * by Showdown species name then a set name like "Lvl 66 Dragon Tamer AARON ".
 */
(function () {
  "use strict";

  function parseHash() {
    var m = (location.hash || "").match(/[#&]mon=([^&]+)/);
    if (!m) return null;
    try { return JSON.parse(decodeURIComponent(m[1])); } catch (e) { return null; }
  }

  function norm(x) {
    return String(x == null ? "" : x).toLowerCase().replace(/[^a-z0-9]/g, "");
  }

  // Resolve the trainer mon to a `"<Species> (<setName>)"` value present in
  // SETDEX_BW. The set name is "Lvl <level> <class> <name> ", but duplicate
  // trainer labels get a counter, so fall back to matching on moves + level.
  function resolveSet(d, DEX) {
    var sp = DEX[d.s] ? d.s
      : Object.keys(DEX).find(function (k) { return norm(k) === norm(d.s); });
    if (!sp) return null;
    var sets = DEX[sp];
    var label = ((d.c || "") + " " + (d.tn || "")).trim();
    var lvl = d.l;
    var wantMoves = JSON.stringify((d.m || []).map(norm).filter(Boolean).sort());

    var exact = "Lvl " + lvl + " " + label + " ";
    if (sets[exact]) return sp + " (" + exact + ")";

    var labelMoves = null, levelMoves = null, labelOnly = null;
    var prefix = "Lvl " + lvl + " " + label;
    for (var sn in sets) {
      if (!Object.prototype.hasOwnProperty.call(sets, sn)) continue;
      var sd = sets[sn];
      var movesEq =
        JSON.stringify((sd.moves || []).map(norm).filter(Boolean).sort()) === wantMoves;
      var labelPre = sn.indexOf(prefix) === 0;
      if (labelPre && movesEq) { labelMoves = sn; break; }
      if (sd.level === lvl && movesEq && !levelMoves) levelMoves = sn;
      if (labelPre && !labelOnly) labelOnly = sn;
    }
    var pick = labelMoves || levelMoves || labelOnly;
    return pick ? sp + " (" + pick + ")" : null;
  }

  // Has the defender (#p2) ended up with this mon's moves?
  function isStuck(desc) {
    if (!window.jQuery) return false;
    var got = jQuery("#p2 .move-selector").map(function () { return this.value; })
      .get().map(norm).filter(function (x) { return x && x !== "nomove"; }).sort();
    var want = (desc.m || []).map(norm).filter(Boolean).sort();
    return got.length > 0 && JSON.stringify(got) === JSON.stringify(want);
  }

  // The calculator clears #p2 during its own start-up (gen change + default
  // list load), which can wipe an early apply. So apply, then verify it stuck
  // and re-apply until it does (init settles within a second or two).
  function tryApply(desc, value, attempt) {
    attempt = attempt || 0;
    var ready = typeof SETDEX_BW !== "undefined" && SETDEX_BW &&
                Object.keys(SETDEX_BW).length;
    var $inp = window.jQuery && jQuery("input.set-selector.opposing");
    if (!ready || !$inp || !$inp.length) {
      if (attempt < 200) setTimeout(function () { tryApply(desc, value, attempt + 1); }, 80);
      return;
    }
    if (!value) {
      value = resolveSet(desc, SETDEX_BW);
      if (!value) { console.warn("[bpe calc] no matching set for", desc); return; }
    }
    if (isStuck(desc)) return;
    // The change handler reads $(this).val() directly, so set the value and fire
    // change — this drives the same path as a user picking the set.
    $inp.val(value).trigger("change");
    // The calc leaves the select2 label blank when set this way; fill it in.
    var chosen = document.querySelector(
      ".set-selector.opposing.select2-container .select2-chosen");
    if (chosen) chosen.textContent = value;
    if (attempt < 80) {
      setTimeout(function () {
        if (!isStuck(desc)) tryApply(desc, value, attempt + 1);
      }, 150);
    }
  }

  function init() {
    var desc = parseHash();
    if (desc && desc.s) tryApply(desc, null, 0);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
