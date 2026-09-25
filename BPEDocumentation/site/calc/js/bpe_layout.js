/* Black Pearl Emerald — the calculator's page layout.
 *
 * css/bpe-layout.css lays the calculator out the way BPE's earlier calculator
 * did: Pokémon 1, the field and Pokémon 2 side by side, each side with its
 * Pokémon's sprite. This keeps each sprite on the Pokémon that is loaded,
 * including a forme picked by hand or a Mega Evolution.
 */
(function (root) {
  "use strict";

  // The same file names build_calc_data.py writes, where JS replaces only the
  // first occurrence.
  function spriteName(species) {
    return species.toLowerCase()
      .replace(" ", "-").replace(".", "").replace("’", "").replace(":", "-");
  }

  // What the calculator itself reads: a species with formes takes the one in
  // the Forme menu, anything else the species picked in the set selector.
  function speciesOf(panel) {
    var forme = panel.find(".forme");
    if (forme.parent().css("display") !== "none" && forme.val()) return forme.val();
    var selector = panel.find("input.set-selector");
    var selected = selector.data("select2") ? selector.select2("data") : null;
    if (selected && selected.pokemon) return selected.pokemon;
    var value = selector.val() || "";
    var split = value.indexOf(" (");
    return split > 0 ? value.slice(0, split) : value;
  }

  function update(panel) {
    var sprite = panel.find(".poke-sprite");
    var species = speciesOf(panel);
    if (!species) { sprite.prop("hidden", true); return; }
    var src = "./img/newhd/" + encodeURIComponent(spriteName(species)) + ".png";
    if (sprite.attr("src") !== src) {
      sprite.attr({ src: src, alt: species, title: species });
      sprite.prop("hidden", false);
    }
  }

  function updateAll() {
    update($("#p1"));
    update($("#p2"));
  }

  $(".poke-sprite").on("error", function () { $(this).prop("hidden", true); });
  // Delegated, so it runs after the calculator's own handlers have filled in
  // the new set's forme.
  $(document).on("change", "#p1, #p2", function () { setTimeout(updateAll, 0); });
  $(updateAll);
  if (root.BPE && root.BPE.ready) root.BPE.ready(function () { setTimeout(updateAll, 0); });
}(typeof window !== "undefined" ? window : globalThis));
