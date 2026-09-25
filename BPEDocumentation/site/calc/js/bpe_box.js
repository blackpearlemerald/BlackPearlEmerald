/* Black Pearl Emerald — the player's box.
 *
 * A save import turns every Pokémon in the party, the PC and the Day Care into
 * a set named "My Box" (then "My Box 2", ... for another of the same species).
 * The calculator already knows how to hold imported sets; this shows them as a
 * row under the player's side so one can be loaded with a click, with the
 * party first.
 */
(function (root) {
  "use strict";

  var BPE = root.BPE = root.BPE || {};
  var box = BPE.box = {};

  var party = [];   // set ids, in party order

  function setId(species, setName) { return species + " (" + setName + ")"; }

  function spriteName(species) {
    return species.toLowerCase()
      .replace(" ", "-").replace(".", "").replace("’", "").replace(":", "-");
  }

  function storedSets() {
    try {
      return localStorage.customsets ? JSON.parse(localStorage.customsets) : {};
    } catch (error) {
      return {};
    }
  }

  // Party first, in party order, then everything else by species name.
  function entries() {
    var sets = storedSets();
    var all = [];
    for (var species in sets) {
      for (var setName in sets[species]) {
        all.push({ species: species, setName: setName, set: sets[species][setName] });
      }
    }
    all.sort(function (a, b) {
      var ai = party.indexOf(setId(a.species, a.setName));
      var bi = party.indexOf(setId(b.species, b.setName));
      if (ai !== bi) return (ai < 0 ? 1e6 : ai) - (bi < 0 ? 1e6 : bi);
      return a.species.localeCompare(b.species) || a.setName.localeCompare(b.setName);
    });
    return all;
  }

  function currentSetId() {
    var selector = $("#p1 .set-selector");
    var selected = selector.data("select2") ? selector.select2("data") : null;
    return (selected && selected.id) || selector.val() || "";
  }

  function render() {
    var container = document.getElementById("bpe-box");
    if (!container) return;
    var members = entries();
    if (!members.length) { container.innerHTML = ""; container.hidden = true; return; }

    var current = currentSetId();
    var html = '<div class="bpe-team-label">Your Pokémon' +
      ' <button type="button" id="bpe-box-clear" class="bpe-box-clear">Clear</button></div>' +
      '<div class="bpe-team-list">';
    members.forEach(function (member) {
      var id = setId(member.species, member.setName);
      var inParty = party.indexOf(id) >= 0 ? " is-party" : "";
      var name = member.set.nickname || member.species;
      html += '<div class="bpe-team-mon' + (id === current ? " is-current" : "") + inParty +
        '" data-set-id="' + id.replace(/"/g, "&quot;") + '" title="' + member.species + '">' +
        '<img class="bpe-team-sprite" src="./img/newhd/' + spriteName(member.species) + '.png"' +
        ' alt="' + member.species + '" loading="lazy" onerror="this.style.visibility=\'hidden\'">' +
        '<div class="bpe-team-name">' + name + "</div>" +
        '<div class="bpe-team-level">Lv ' + (member.set.level || "?") + "</div></div>";
    });
    container.innerHTML = html + "</div>";
    container.hidden = false;
  }

  // Load one of the player's Pokémon on the left side.
  function loadPlayerSet(id) {
    var selector = $("#p1 .set-selector");
    var split = id.indexOf(" (");
    var option = {
      id: id,
      text: id,
      pokemon: split > 0 ? id.slice(0, split) : id,
      set: split > 0 ? id.slice(split + 2, id.lastIndexOf(")")) : ""
    };
    if (selector.data("select2")) selector.select2("data", option, true);
    else selector.val(id).change();
  }

  function mount() {
    if (document.getElementById("bpe-box")) return;
    var container = document.createElement("div");
    container.id = "bpe-box";
    container.className = "bpe-team bpe-box";
    container.hidden = true;
    BPE.strip().appendChild(container);

    $(container).on("click", ".bpe-team-mon", function () {
      var id = this.getAttribute("data-set-id");
      if (id && id !== currentSetId()) loadPlayerSet(id);
    });
    $(container).on("click", "#bpe-box-clear", function (event) {
      event.stopPropagation();
      box.clear();
    });
    $("#p1 .set-selector").on("change", render);
  }

  // Replace the box with a freshly imported save.
  box.show = function (built) {
    box.clear(true);
    updateDex(built.sets);            // the calculator's own imported-set store
    party = built.party.slice();
    $(allPokemon("#importedSetsOptions")).css("display", "inline");
    render();
    if (party.length) loadPlayerSet(party[0]);
  };

  box.clear = function (keepUI) {
    var sets = storedSets();
    for (var species in sets) {
      for (var setName in sets[species]) {
        for (var gen = 0; gen < SETDEX.length; gen++) {
          if (SETDEX[gen] && SETDEX[gen][species]) delete SETDEX[gen][species][setName];
        }
      }
    }
    try { localStorage.removeItem("customsets"); } catch (error) { /* private mode */ }
    party = [];
    if (!keepUI) {
      render();
      $(".set-selector").change();
    }
  };

  box.render = render;
  box.party = function () { return party.slice(); };

  BPE.ready(function () {
    mount();
    // The calculator restores localStorage.customsets on load, so a box from an
    // earlier visit is already in its sets; show it.
    render();
  });

  // "Clear Imported Sets" is the calculator's own button for the same store.
  $(document).on("click", "#clearSets", function () { setTimeout(render, 0); });
}(typeof window !== "undefined" ? window : globalThis));
