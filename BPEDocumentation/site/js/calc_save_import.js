/* BPE Emerald — damage-calculator save import.
 *
 * "Import .sav" reads a Black Pearl Emerald .sav/.srm in the browser with
 * save-converter.js (either save format) and puts every Pokémon from the party,
 * all PC boxes and the Day Care into the calculator's box, replacing the ones
 * imported before. Eggs are left out, and so are Pokémon that fainted in a
 * Nuzlocke run that is still going.
 *
 * The selected release's calculator data carries `save_data`, built by
 * scripts/build_calc_data.py from that release's source, which turns the game's
 * species, move and item numbers into calculator names. The box keeps one set
 * per Pokémon: the first of a species is "My Box", later ones "My Box 2", ...
 */
(function (root) {
  "use strict";

  var NATURES = ["Hardy", "Lonely", "Brave", "Adamant", "Naughty", "Bold", "Docile", "Relaxed",
    "Impish", "Lax", "Timid", "Hasty", "Serious", "Jolly", "Naive", "Modest", "Mild", "Quiet",
    "Bashful", "Rash", "Calm", "Gentle", "Sassy", "Careful", "Quirky"];
  // Calculator stat keys in the game's order: HP, Atk, Def, Spe, SpA, SpD
  var STAT_KEYS = ["hp", "at", "df", "sp", "sa", "sd"];
  var SET_NAME = "My Box";
  var NO_MOVE = "(No Move)";
  var MAX_LEVEL = 100;
  var MAX_PER_STAT_IVS = 31;
  var NUM_NORMAL_ABILITY_SLOTS = 2;
  var NUM_ABILITY_SLOTS = 3;

  // gExperienceTables (src/data/pokemon/experience_tables.h) with C integer
  // division. Levels 0 and 1 are fixed at 0 and 1 exp in every table.
  function cube(n) { return n * n * n; }
  var EXPERIENCE = {
    "Medium Fast": function (n) { return cube(n); },
    "Erratic": function (n) {
      if (n <= 50) return Math.trunc((100 - n) * cube(n) / 50);
      if (n <= 68) return Math.trunc((150 - n) * cube(n) / 100);
      if (n <= 98) return Math.trunc(Math.trunc((1911 - 10 * n) / 3) * cube(n) / 500);
      return Math.trunc((160 - n) * cube(n) / 100);
    },
    "Fluctuating": function (n) {
      if (n <= 15) return Math.trunc((Math.trunc((n + 1) / 3) + 24) * cube(n) / 50);
      if (n <= 36) return Math.trunc((n + 14) * cube(n) / 50);
      return Math.trunc((Math.trunc(n / 2) + 32) * cube(n) / 50);
    },
    "Medium Slow": function (n) { return Math.trunc(6 * cube(n) / 5) - 15 * n * n + 100 * n - 140; },
    "Fast": function (n) { return Math.trunc(4 * cube(n) / 5); },
    "Slow": function (n) { return Math.trunc(5 * cube(n) / 4); }
  };

  function experienceFor(growthRate, level) {
    if (level <= 1) return level;
    return (EXPERIENCE[growthRate] || EXPERIENCE["Medium Fast"])(level);
  }

  // GetLevelFromBoxMonExp
  function levelFromExp(growthRate, exp) {
    var level = 1;
    while (level <= MAX_LEVEL && experienceFor(growthRate, level) <= exp) level++;
    return Math.max(1, level - 1);
  }

  // GetAbilityBySpecies: an empty hidden slot falls back to another hidden
  // slot, and any empty slot to the first ability the species has.
  function abilityFor(slots, abilityNum) {
    function at(i) { return slots[i] && slots[i] !== "-------" ? slots[i] : null; }
    var ability = abilityNum < NUM_ABILITY_SLOTS ? at(abilityNum) : null;
    var i;
    if (abilityNum >= NUM_NORMAL_ABILITY_SLOTS)
      for (i = NUM_NORMAL_ABILITY_SLOTS; i < NUM_ABILITY_SLOTS && !ability; i++) ability = at(i);
    for (i = 0; i < NUM_ABILITY_SLOTS && !ability; i++) ability = at(i);
    return ability;
  }

  // Nicknames: letters, digits and the punctuation a player can type.
  var CHARACTERS = (function () {
    var table = { 0x00: " ", 0xAB: "!", 0xAC: "?", 0xAD: ".", 0xAE: "-", 0xB0: "…", 0xB1: "“",
      0xB2: "”", 0xB3: "‘", 0xB4: "’", 0xB5: "♂", 0xB6: "♀", 0xB8: ",", 0xBA: "/", 0xF0: ":" };
    var i;
    for (i = 0; i < 10; i++) table[0xA1 + i] = String(i);
    for (i = 0; i < 26; i++) {
      table[0xBB + i] = String.fromCharCode(65 + i);
      table[0xD5 + i] = String.fromCharCode(97 + i);
    }
    return table;
  }());

  function decodeName(bytes) {
    var text = "";
    for (var i = 0; i < bytes.length && bytes[i] !== 0xFF; i++) text += CHARACTERS[bytes[i]] || "";
    return text.trim();
  }

  function simplify(name) {
    return String(name).toLowerCase().replace(/[^a-z0-9]/g, "");
  }

  // Turns readSaveFile's result into calculator sets. `reader` is the
  // save-converter.js API; `itemNames` lists the items the calculator knows.
  function buildSets(save, calcData, reader, itemNames) {
    var data = calcData.save_data;
    var growthRates = data.growthRates;
    var nuzlocke = data.nuzlockeFlag != null && reader.readSaveFlag(save.saveBlock1, data.nuzlockeFlag) === 1;
    var randomized = (data.randomizerVars || []).some(function (id) {
      return reader.readSaveVar(save.saveBlock1, id) !== 0;
    });
    var ignoreEvs = nuzlocke && data.nuzlockeIgnoresEvs;
    var items = {};
    (itemNames || []).forEach(function (name) { items[simplify(name)] = name; });

    var result = {
      sets: {}, party: [], nuzlocke: nuzlocke, randomized: randomized,
      counts: { party: 0, box: 0, daycare: 0, eggs: 0, fainted: 0, unknown: 0 }
    };
    save.pokemon.forEach(function (mon) {
      var species = data.species[mon.species];
      if (mon.isEgg) { result.counts.eggs++; return; }
      if (mon.dead && nuzlocke) { result.counts.fainted++; return; }
      if (!species) { result.counts.unknown++; return; }

      var name = species[0];
      var growthRate = growthRates[species[1]];
      var shared = (calcData.poks[name] || {}).abilities || {};
      var slots = species[2] || [shared["0"], shared["1"], shared.H];
      var nature = (mon.personality % 25) ^ mon.hiddenNatureModifier;
      var item = mon.heldItem ? data.items[mon.heldItem] : null;
      var set = {
        level: levelFromExp(growthRate, mon.experience),
        nature: NATURES[nature] || NATURES[mon.personality % 25],
        ability: abilityFor(slots, mon.abilityNum) || undefined,
        item: item ? (itemNames ? items[simplify(item)] : item) : undefined,
        moves: mon.moves.map(function (id) { return (id && data.moves[id]) || NO_MOVE; }),
        evs: {},
        ivs: {},
        isCustomSet: true
      };
      STAT_KEYS.forEach(function (key, i) {
        set.evs[key] = ignoreEvs ? 0 : mon.evs[i];
        set.ivs[key] = mon.hyperTrained[i] ? MAX_PER_STAT_IVS : mon.ivs[i];
      });
      var nickname = decodeName(mon.nickname);
      if (nickname && simplify(nickname) !== simplify(name) && simplify(nickname) !== simplify(name.split("-")[0])) {
        set.nn = nickname;
        set.nickname = nickname;
      }

      var sets = result.sets[name] = result.sets[name] || {};
      var setName = SET_NAME;
      for (var n = 2; sets[setName]; n++) setName = SET_NAME + " " + n;
      sets[setName] = set;
      result.counts[mon.place]++;
      if (mon.place === "party") result.party.push(name + " (" + setName + ")");
    });
    return result;
  }

  function summary(save, built) {
    var counts = built.counts;
    var total = counts.party + counts.box + counts.daycare;
    var parts = [counts.party + " in your party", counts.box + " in the PC"];
    if (counts.daycare) parts.push(counts.daycare + " at the Day Care");
    var text = "Imported " + total + " Pokémon: " + parts.join(", ") + ".";
    if (counts.eggs) text += " " + counts.eggs + (counts.eggs === 1 ? " Egg was" : " Eggs were") + " left out.";
    if (counts.fainted) text += " " + counts.fainted + " fainted Nuzlocke Pokémon " + (counts.fainted === 1 ? "was" : "were") + " left out.";
    if (counts.unknown) text += " " + counts.unknown + " Pokémon " + (counts.unknown === 1 ? "is" : "are") +
      " not in this version's data. Check that the selected version matches your game.";
    if (save.loadFlags.boxLost) text += " Part of this save's PC is damaged and could not be read.";
    if (built.randomized) text += " This save uses the randomizer, but the calculator uses the normal abilities, types and base stats.";
    return text;
  }

  var api = { buildSets: buildSets, levelFromExp: levelFromExp, experienceFor: experienceFor };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.BPECalcSaveImport = api;

  // Page ---------------------------------------------------------------------------

  if (typeof document === "undefined") return;

  function setStatus(state, message) {
    var status = document.getElementById("bpe-save-status");
    status.className = "is-" + state;
    status.textContent = message;
    status.hidden = !message;
  }

  async function importSave(file) {
    setStatus("working", "Reading " + file.name + "…");
    try {
      var bytes = new Uint8Array(await file.arrayBuffer());
      var save = BPESaveConverter.readSaveFile(bytes);
      var built = buildSets(save, BPE.data, BPESaveConverter, calc.ITEMS[BPE.gen]);
      var imported = built.counts.party + built.counts.box + built.counts.daycare;
      if (!imported) {
        setStatus("error", "This save has no Pokémon to import yet.");
        return;
      }
      var previous = localStorage.customsets ? JSON.parse(localStorage.customsets) : {};
      var previousCount = Object.keys(previous).reduce(function (total, species) {
        return total + Object.keys(previous[species]).length;
      }, 0);
      if (previousCount && !confirm("Replace the " + previousCount + " Pokémon in your calculator box with the " +
          imported + " from this save?")) {
        setStatus("ready", "");
        return;
      }
      BPE.box.show(built);
      setStatus("success", summary(save, built));
    } catch (error) {
      console.error(error);
      setStatus("error", error.message || "This save could not be read.");
    }
  }

  function init() {
    var button = document.getElementById("bpe-read-save");
    var input = document.getElementById("bpe-save-upload");
    if (!button || !input) return;
    // Choosing the same file again (after saving in the game) must import again.
    input.addEventListener("click", function () { input.value = ""; });
    input.addEventListener("change", function () {
      if (input.files && input.files[0]) importSave(input.files[0]);
    });
    var clear = document.getElementById("clearSets");
    if (clear) clear.addEventListener("click", function () { setStatus("ready", ""); });
    // The calculator loads its data after the page; only BPE data can read saves.
    (function waitForData(attempt) {
      if (root.BPE && BPE.data && BPE.data.save_data) {
        button.style.display = "";
      } else if (attempt < 300) {
        setTimeout(function () { waitForData(attempt + 1); }, 100);
      }
    }(0));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
}(typeof window !== "undefined" ? window : globalThis));
