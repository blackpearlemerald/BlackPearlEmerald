/* Black Pearl Emerald — Mega Evolution on a trainer's Pokémon.
 *
 * A Pokémon holding its Mega Stone Mega Evolves as soon as the battle starts,
 * so the calculator should show the Mega's stats, types and ability.
 * build_calc_data.py records a trainer's form on the set as `mega`; the
 * player's own Pokémon (the imported party and box) carry only the item, so the
 * calculator's Mega Stone table names the form for them. This switches the
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

  // The species a set is for, from its id ("<Species> (<set name>)").
  function speciesOf(id) {
    var split = id.indexOf(" (");
    return split < 0 ? id : id.slice(0, split);
  }

  // The Primal and Ultra Burst items, which the calculator's Mega Stone table
  // leaves out: { item: { species: form } }.
  var BATTLE_FORMS = {
    "Red Orb": { "Groudon": "Groudon-Primal" },
    "Blue Orb": { "Kyogre": "Kyogre-Primal" },
    "Ultranecrozium Z": { "Necrozma-Dusk-Mane": "Necrozma-Ultra", "Necrozma-Dawn-Wings": "Necrozma-Ultra" }
  };

  // The form the set Mega Evolves into, or "". A trainer's set says so itself;
  // anything else holding a Mega Stone that fits its species (the player's own
  // Pokémon) is found in the calculator's table, { species: Mega form }.
  function megaOf(id, side) {
    var set = setFor(id);
    if (set && set.mega) return set.mega;
    var item = $(side + " .item").val();
    var stone = BATTLE_FORMS[item] ||
      ((typeof calc !== "undefined" && calc.MEGA_STONES) ? calc.MEGA_STONES[item] : null);
    return (stone && typeof stone === "object" && stone[speciesOf(id)]) || "";
  }

  function applyMega(side) {
    var mega = megaOf(selectedId(side), side);
    if (!mega) return;
    var forme = $(side + " .forme");
    // showFormes() fills this list from the species; the Mega is only there
    // when the calculator knows that form.
    if (!forme.length || !forme.find("option[value='" + mega + "']").length) return;
    if (forme.val() === mega) return;
    forme.val(mega).change();
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
