/* Black Pearl Emerald — Mega Evolution on a trainer's Pokémon.
 *
 * A trainer Pokémon holding its Mega Stone Mega Evolves as soon as the battle
 * starts, so the calculator should show the Mega's stats, types and ability.
 * build_calc_data.py records the form on the set as `mega`; this switches the
 * forme selector to it whenever such a set is loaded.
 */
(function (root) {
  "use strict";

  var BPE = root.BPE = root.BPE || {};

  function setFor(id) {
    if (!BPE.sets || !id) return null;
    var split = id.indexOf(" (");
    if (split < 0) return null;
    var species = id.slice(0, split);
    var setName = id.slice(split + 2, id.lastIndexOf(")"));
    var sets = BPE.sets[species];
    return (sets && sets[setName]) || null;
  }

  function selectedId(side) {
    var selector = $(side + " .set-selector");
    var selected = selector.data("select2") ? selector.select2("data") : null;
    return (selected && selected.id) || selector.val() || "";
  }

  function applyMega(side) {
    var set = setFor(selectedId(side));
    if (!set || !set.mega) return;
    var forme = $(side + " .forme");
    // showFormes() fills this list from the species; the Mega is only there
    // when the calculator knows that form.
    if (!forme.length || !forme.find("option[value='" + set.mega + "']").length) return;
    if (forme.val() === set.mega) return;
    forme.val(set.mega).change();
  }

  BPE.ready(function () {
    ["#p1", "#p2"].forEach(function (side) {
      $(side + " .set-selector").on("change", function () {
        // The calculator rebuilds the forme list during its own change
        // handler, so apply the Mega once that has run.
        setTimeout(function () { applyMega(side); }, 0);
      });
    });
  });
}(typeof window !== "undefined" ? window : globalThis));
