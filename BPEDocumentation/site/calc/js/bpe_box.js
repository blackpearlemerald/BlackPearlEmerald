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

  // Names reach this from the game's data and from a player's own save, so
  // they are escaped rather than trusted as markup.
  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }


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
        '" data-set-id="' + escapeHtml(id) + '" title="' + escapeHtml(member.species) + '">' +
        '<img class="bpe-team-sprite" src="./img/newhd/' + encodeURIComponent(spriteName(member.species)) + '.png"' +
        ' alt="' + escapeHtml(member.species) + '" loading="lazy" onerror="this.style.visibility=\'hidden\'">' +
        '<div class="bpe-team-name">' + escapeHtml(name) + "</div>" +
        '<div class="bpe-team-level">Lv ' + (member.set.level || "?") + "</div></div>";
    });
    container.innerHTML = html + "</div>";
    container.hidden = false;
    scheduleMatchups();
  }

  // ── Match-ups ─────────────────────────────────────────────────────────────
  // What each Pokémon in the box does to the trainer's Pokémon that is loaded,
  // and what it takes back. This is the question a Nuzlocke run asks of every
  // box Pokémon at once, so it is answered on the tiles.
  function monFromSet(gen, species, set) {
    return new calc.Pokemon(gen, species, {
      level: set.level, nature: set.nature, ability: set.ability, item: set.item,
      evs: set.evs, ivs: set.ivs, moves: set.moves, teraType: set.teraType
    });
  }

  function worstCase(gen, attacker, defender, field) {
    var worst = 0;
    (attacker.moves || []).forEach(function (move) {
      var name = move && move.name ? move.name : move;
      if (!name || name === "(No Move)" || name === "-") return;
      try {
        var result = calc.calculate(gen, attacker, defender, new calc.Move(gen, name), field);
        var range = result.range();
        worst = Math.max(worst, range[1] / defender.maxHP() * 100);
      } catch (error) { /* a move the calculator cannot place */ }
    });
    return worst;
  }

  function matchups() {
    var container = document.getElementById("bpe-box");
    if (!container || container.hidden || !BPE.data) return;
    var tiles = container.querySelectorAll(".bpe-team-mon");
    if (!tiles.length) return;

    var gen = calc.Generations.get(BPE.gen);
    var opponent, field, back;
    try {
      opponent = createPokemon($("#p2"));
      field = createField();
      back = field.clone().swap();
    } catch (error) { return; }

    var sets = storedSets();
    Array.prototype.forEach.call(tiles, function (tile) {
      var id = tile.getAttribute("data-set-id");
      var split = id.indexOf(" (");
      var species = id.slice(0, split);
      var setName = id.slice(split + 2, id.lastIndexOf(")"));
      var set = sets[species] && sets[species][setName];
      tile.classList.remove("can-ko", "can-be-koed");
      var note = tile.querySelector(".bpe-team-matchup");
      if (note) note.remove();
      if (!set) return;

      var mon;
      try { mon = monFromSet(gen, species, set); } catch (error) { return; }
      var dealt = worstCase(gen, mon, opponent, field);
      var taken = worstCase(gen, opponent, mon, back);
      var faster = mon.stats.spe > opponent.stats.spe;

      if (dealt >= 100) tile.classList.add("can-ko");
      if (taken >= 100) tile.classList.add("can-be-koed");
      var line = document.createElement("div");
      line.className = "bpe-team-matchup";
      line.textContent = (dealt >= 100 ? "KO" : Math.round(dealt) + "%") + " / " +
        (taken >= 100 ? "KO'd" : Math.round(taken) + "%") + (faster ? " »" : "");
      line.title = "Deals up to " + Math.round(dealt) + "% and takes up to " + Math.round(taken) + "%" +
        (faster ? ", and moves first" : "");
      tile.appendChild(line);
    });
  }

  var matchupTimer = null;
  function scheduleMatchups() {
    clearTimeout(matchupTimer);
    matchupTimer = setTimeout(matchups, 150);
  }
  box.matchups = scheduleMatchups;

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
    // The opposing side, and any field or spread change, moves every match-up.
    $("#p2 .set-selector").on("change", scheduleMatchups);
    $(document).on("change keyup", ".calc-trigger", scheduleMatchups);
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
