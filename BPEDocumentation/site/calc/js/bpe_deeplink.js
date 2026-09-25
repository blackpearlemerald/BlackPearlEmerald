/* Black Pearl Emerald — damage-calculator deep link.
 *
 * The interactive map and the Trainers page link a trainer's Pokémon with
 *     calc.html#mon=<encoded JSON {s,l,c,tn,m}>
 * where s=species, l=level, c=trainer class, tn=trainer name, m=moves[].
 * (calc.html forwards location.hash on to the calculator.)
 *
 * That set is loaded on the opposing side, which also brings up the rest of
 * that trainer's team.
 */
(function (root) {
  "use strict";

  var BPE = root.BPE = root.BPE || {};

  function parseHash() {
    var match = (location.hash || "").match(/[#&]mon=([^&]+)/);
    if (!match) return null;
    try { return JSON.parse(decodeURIComponent(match[1])); } catch (error) { return null; }
  }

  function norm(value) {
    return String(value == null ? "" : value).toLowerCase().replace(/[^a-z0-9]/g, "");
  }

  // The species the Pokémon can be entered under. The map names the species the
  // game shows ("Toxtricity"), while the calculator enters a form under its own
  // name ("Toxtricity-Amped"), so a base name with no entry of its own falls
  // back to the forms whose name starts with it.
  function speciesCandidates(want, sets) {
    var target = norm(want);
    var exact = sets[want] ? want
      : Object.keys(sets).find(function (name) { return norm(name) === target; });
    var forms = Object.keys(sets).filter(function (name) {
      return name !== exact && norm(name).indexOf(target) === 0;
    });
    return exact ? [exact].concat(forms) : forms;
  }

  // Resolve to "<Species> (<set name>)". Set names are "Lvl <level> <class>
  // <name> ", but duplicate trainer labels get a counter, so fall back to
  // matching on level and moves.
  function resolveSet(mon, sets) {
    var label = ((mon.c || "") + " " + (mon.tn || "")).trim();
    var level = mon.l;
    var wantMoves = JSON.stringify((mon.m || []).map(norm).filter(Boolean).sort());
    var exactName = "Lvl " + level + " " + label + " ";
    var prefix = "Lvl " + level + " " + label;
    var fallback = null;

    var candidates = speciesCandidates(mon.s, sets);
    for (var i = 0; i < candidates.length; i++) {
      var species = candidates[i];
      var speciesSets = sets[species];
      if (speciesSets[exactName]) return species + " (" + exactName + ")";

      var labelAndMoves = null, levelAndMoves = null, labelOnly = null;
      for (var setName in speciesSets) {
        if (!Object.prototype.hasOwnProperty.call(speciesSets, setName)) continue;
        var set = speciesSets[setName];
        var movesMatch =
          JSON.stringify((set.moves || []).map(norm).filter(Boolean).sort()) === wantMoves;
        var labelMatch = setName.indexOf(prefix) === 0;
        if (labelMatch && movesMatch) { labelAndMoves = setName; break; }
        if (set.level === level && movesMatch && !levelAndMoves) levelAndMoves = setName;
        if (labelMatch && !labelOnly) labelOnly = setName;
      }
      if (labelAndMoves) return species + " (" + labelAndMoves + ")";
      var pick = levelAndMoves || labelOnly;
      if (pick && !fallback) fallback = species + " (" + pick + ")";
    }
    return fallback;
  }

  // Read the link before anything else runs: the calculator rewrites the URL
  // when it sets its generation, which drops the hash.
  var requested = parseHash();

  BPE.ready(function (data) {
    var mon = requested;
    if (!mon || !mon.s) return;
    // Links name the Nuzlocke level, so they are matched against the data as
    // written, then loaded as the chosen mode has that set. A link to a
    // rematch asks for it, so rematches are shown.
    var id = resolveSet(mon, data.formatted_sets);
    if (!id) {
      console.warn("[bpe] no matching set for", mon);
      return;
    }
    if (!BPE.shownId(id)) BPE.setOptions({ rematches: true });
    if (BPE.shownId(id)) BPE.loadOpposingSet(BPE.shownId(id));
  });
}(typeof window !== "undefined" ? window : globalThis));
