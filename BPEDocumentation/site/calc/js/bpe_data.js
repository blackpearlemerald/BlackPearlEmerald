/* Black Pearl Emerald — game data for the damage calculator.
 *
 * The calculator ships Smogon's data for the official games. BPE is a ROM hack,
 * so every Pokémon, move, ability, item and trainer team comes from the game's
 * own source instead, exported to data/bpe_calc_data.json by
 * BPEDocumentation/scripts/build_calc_data.py.
 *
 * This lays that data over the calculator's Gen 9 tables and hands it the
 * trainers as Gen 9 sets, then re-runs the calculator's own generation setup so
 * every menu is rebuilt from it. The damage mechanics stay untouched: they are
 * what we take from upstream.
 */
(function (root) {
  "use strict";

  var GEN = 9;                       // BPE plays by the newest mechanics
  var DATA_URL = "./data/bpe_calc_data.json";

  var BPE = root.BPE = root.BPE || {};
  var waiting = [];

  BPE.gen = GEN;

  // Both BPE rows live in one strip under the calculator, so neither has to
  // fit inside the calculator's own floated panels.
  BPE.strip = function () {
    var strip = document.getElementById("bpe-strip");
    if (!strip) {
      strip = document.createElement("div");
      strip.id = "bpe-strip";
      var wrapper = document.querySelector(".wrapper") || document.body;
      wrapper.appendChild(strip);
    }
    return strip;
  };
  BPE.data = null;
  // Run `callback` once the game data is in the calculator's tables.
  BPE.ready = function (callback) {
    if (BPE.data) callback(BPE.data);
    else waiting.push(callback);
  };

  function normalize(name) {
    return String(name == null ? "" : name).toLowerCase().replace(/[^a-z0-9]/g, "");
  }

  // ── Species ───────────────────────────────────────────────────────────────
  // poks[name] = {bs, types, abilities, weightkg, learnset_info}, which is the
  // shape the calculator's own species table uses.
  function loadSpecies(poks) {
    var species = calc.SPECIES[GEN];
    for (var name in poks) {
      var mon = poks[name];
      var entry = species[name] ? Object.create(Object.getPrototypeOf(species[name]) || Object.prototype) : {};
      if (species[name]) for (var key in species[name]) entry[key] = species[name][key];
      entry.types = mon.types;
      entry.bs = mon.bs;
      if (mon.weightkg != null) entry.weightkg = mon.weightkg;
      if (mon.abilities) entry.abilities = mon.abilities;
      species[name] = entry;
    }
  }

  // ── Moves ─────────────────────────────────────────────────────────────────
  // BPE exports a move's type, category and base power. Everything else about a
  // move (priority, sound, multi-hit, drain, the Gen 9 rules) stays upstream's.
  //
  // A base power of 1 is the game's marker for "worked out during the battle":
  // Low Kick from the target's weight, Gyro Ball from Speed, Seismic Toss from
  // level, Return from friendship, and so on. The calculator works those out
  // too, so its own value has to stand.
  var COMPUTED_IN_BATTLE = 1;

  function loadMoves(gameMoves) {
    var moves = calc.MOVES[GEN];
    for (var name in gameMoves) {
      var move = gameMoves[name];
      var entry = {};
      if (moves[name]) for (var key in moves[name]) entry[key] = moves[name][key];
      if (move.type) entry.type = move.type;
      if (move.category) entry.category = move.category;
      if (move.basePower != null && move.basePower !== COMPUTED_IN_BATTLE) entry.bp = move.basePower;
      if (entry.bp == null) entry.bp = move.basePower === COMPUTED_IN_BATTLE ? 0 : (move.basePower || 0);
      moves[name] = entry;
    }
  }

  // ── The engine's own tables ───────────────────────────────────────────────
  // The menus read calc.SPECIES and calc.MOVES, but the damage engine looks
  // Pokémon and moves up in tables of its own, built from those when the page
  // loaded. The two panels hand stats, types and move power over as overrides,
  // so they were right; anything else was not. A species the calculator never
  // had (the game's "Aegislash" is its Shield Forme) reached the engine with no
  // weight, so Low Kick did nothing to it, and the box match-ups, which build
  // their Pokémon and moves from names alone, used Smogon's stats and moves.
  // Generation 9 lookups therefore answer from the game's data.
  var engineSpecies = {}, engineMoves = {};
  var upstreamSpecies = calc.Species.prototype.get;
  var upstreamMoves = calc.Moves.prototype.get;

  calc.Species.prototype.get = function (id) {
    return (this.gen === GEN && engineSpecies[id]) || upstreamSpecies.call(this, id);
  };
  calc.Moves.prototype.get = function (id) {
    return (this.gen === GEN && engineMoves[id]) || upstreamMoves.call(this, id);
  };

  function copy(from, to) {
    for (var key in from) if (Object.prototype.hasOwnProperty.call(from, key)) to[key] = from[key];
    return to;
  }

  function loadEngineSpecies(names) {
    var table = { gen: GEN };
    names.forEach(function (name) {
      var id = calc.toID(name), entry = calc.SPECIES[GEN][name];
      var specie = copy(upstreamSpecies.call(table, id) || {}, { kind: "Species", id: id, name: name });
      for (var key in entry) if (key !== "bs") specie[key] = entry[key];
      specie.baseStats = { hp: entry.bs.hp, atk: entry.bs.at, def: entry.bs.df,
        spa: entry.bs.sa, spd: entry.bs.sd, spe: entry.bs.sp };
      engineSpecies[id] = specie;
    });
  }

  function loadEngineMoves(names) {
    var table = { gen: GEN };
    names.forEach(function (name) {
      var id = calc.toID(name), entry = calc.MOVES[GEN][name];
      var move = copy(upstreamMoves.call(table, id) || { flags: {}, category: "Status" },
        { kind: "Move", id: id, name: name });
      move.basePower = entry.bp;
      if (entry.type) move.type = entry.type;
      if (entry.category) move.category = entry.category;
      engineMoves[id] = move;
    });
  }

  // ── Ability and item menus ────────────────────────────────────────────────
  // The menus are lists of names. A name the calculator does not know still
  // belongs in them: the set is what the player faces in game, and a missing
  // name would silently read as "(other)" or "(none)".
  function addNames(list, names) {
    var known = {};
    list.forEach(function (name) { known[normalize(name)] = true; });
    var added = [];
    names.forEach(function (name) {
      if (!name || name === "-" || known[normalize(name)]) return;
      known[normalize(name)] = true;
      added.push(name);
      list.push(name);
    });
    return added;
  }

  function collectNames(data) {
    var abilities = [], items = [];
    for (var name in data.poks) {
      var slots = data.poks[name].abilities || {};
      for (var slot in slots) if (slots[slot]) abilities.push(slots[slot]);
    }
    for (var species in data.formatted_sets) {
      var sets = data.formatted_sets[species];
      for (var setName in sets) {
        if (sets[setName].ability) abilities.push(sets[setName].ability);
        if (sets[setName].item) items.push(sets[setName].item);
      }
    }
    for (var stone in data.mega_stones || {}) items.push(stone);
    return { abilities: abilities, items: items };
  }

  // A Mega Stone the calculator's item list lacks still has to Mega Evolve.
  function loadMegaStones(stones) {
    for (var stone in stones || {}) {
      if (!calc.MEGA_STONES[stone]) calc.MEGA_STONES[stone] = stones[stone];
    }
  }

  // ── Set lists ─────────────────────────────────────────────────────────────
  // The calculator keeps one set list per generation, as a global per
  // generation and an array indexed by it. BPE ships no Smogon sets, so those
  // globals have to exist and be the very objects the array holds: the
  // calculator's own imported-set code writes through the globals, and the
  // menus read the array.
  var SETDEX_GLOBALS = ["SETDEX_CHAMPIONS", "SETDEX_RBY", "SETDEX_GSC", "SETDEX_ADV",
    "SETDEX_DPP", "SETDEX_BW", "SETDEX_XY", "SETDEX_SM", "SETDEX_SS", "SETDEX_SV"];

  SETDEX_GLOBALS.forEach(function (name, index) {
    if (typeof root[name] === "undefined" || !root[name]) root[name] = {};
    if (typeof SETDEX !== "undefined") SETDEX[index] = root[name];
  });

  // formatted_sets is already "<Species> -> <set name> -> set", which is the
  // calculator's own set format, so the trainers become this generation's sets.
  function loadSets(sets) {
    var target = root.SETDEX_SV;
    for (var species in sets) {
      target[species] = target[species] || {};
      for (var setName in sets[species]) target[species][setName] = sets[species][setName];
    }
  }

  function apply(data) {
    loadSpecies(data.poks);
    loadMoves(data.moves);
    loadEngineSpecies(Object.keys(data.poks));
    loadEngineMoves(Object.keys(data.moves));
    loadMegaStones(data.mega_stones);
    var names = collectNames(data);
    addNames(calc.ABILITIES[GEN], names.abilities);
    addNames(calc.ITEMS[GEN], names.items);
    loadSets(data.formatted_sets);

    BPE.data = data;

    // Re-run the calculator's generation setup so every menu is rebuilt from
    // the game's data, then let it pick its first set as usual.
    $("#gen" + GEN).prop("checked", true).change();

    waiting.forEach(function (callback) { callback(data); });
    waiting = [];
    $(document).trigger("bpe:data");
  }

  function load() {
    $.getJSON(DATA_URL).done(apply).fail(function (jqXHR, textStatus, error) {
      console.error("[bpe] could not load " + DATA_URL + ": " + textStatus, error);
      $("#bpe-data-error").show();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", load);
  } else {
    load();
  }
}(typeof window !== "undefined" ? window : globalThis));
