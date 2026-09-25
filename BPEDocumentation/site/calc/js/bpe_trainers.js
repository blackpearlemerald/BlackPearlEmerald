/* Black Pearl Emerald — the opposing trainer's team.
 *
 * Every trainer set carries the trainer it belongs to (tr_id) and its slot in
 * that party (sub_index), so loading one of a trainer's Pokémon shows the whole
 * team underneath in party order. Clicking a team member loads it; the one
 * currently loaded stays in the row, marked, because the row is read as "this
 * trainer's team", not as "who can switch in".
 */
(function (root) {
  "use strict";

  var BPE = root.BPE = root.BPE || {};
  var teams = {};        // tr_id -> [{species, setName, set}] in party order
  var teamOf = {};       // "<Species> (<set name>)" -> tr_id

  function setId(species, setName) { return species + " (" + setName + ")"; }

  // Names reach this from the game's data and from a player's own save, so
  // they are escaped rather than trusted as markup.
  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }


  function index(data) {
    teams = {};
    teamOf = {};
    var sets = data.formatted_sets;
    for (var species in sets) {
      for (var setName in sets[species]) {
        var set = sets[species][setName];
        if (set.tr_id == null) continue;
        (teams[set.tr_id] = teams[set.tr_id] || []).push({
          species: species, setName: setName, set: set
        });
        teamOf[setId(species, setName)] = set.tr_id;
      }
    }
    for (var id in teams) {
      teams[id].sort(function (a, b) {
        return (a.set.sub_index || 0) - (b.set.sub_index || 0);
      });
    }
  }

  // build_calc_data.py names each sprite with the calculator's own transform,
  // where JS replaces only the first occurrence.
  function spriteName(species) {
    return species.toLowerCase()
      .replace(" ", "-").replace(".", "").replace("’", "").replace(":", "-");
  }

  // "Lvl 13 Leader DAN " -> "Leader DAN"
  function trainerLabel(setName) {
    return String(setName).replace(/^Lvl\s+\d+\s*/, "").trim();
  }

  function moveList(set) {
    return (set.moves || []).filter(function (move) {
      return move && move !== "-" && move !== "(No Move)";
    });
  }

  function render(currentId) {
    var container = document.getElementById("bpe-team");
    if (!container) return;
    var trId = teamOf[currentId];
    if (trId == null) { container.innerHTML = ""; container.hidden = true; return; }

    var team = teams[trId] || [];
    var label = trainerLabel(team.length ? team[0].setName : "");
    var html = '<div class="bpe-team-label">' + escapeHtml(label) + "</div>" +
      '<div class="bpe-team-list">';
    team.forEach(function (member) {
      var id = setId(member.species, member.setName);
      var current = id === currentId ? " is-current" : "";
      var level = member.set.level != null ? "Lv " + member.set.level : "";
      html += '<div class="bpe-team-mon' + current + '" data-set-id="' + id.replace(/"/g, "&quot;") + '"' +
        ' title="' + member.species + " " + level + '">' +
        '<img class="bpe-team-sprite" src="./img/newhd/' + spriteName(member.species) + '.png"' +
        ' alt="' + member.species + '" loading="lazy" onerror="this.style.visibility=\'hidden\'">' +
        '<div class="bpe-team-name">' + member.species + '</div>' +
        '<div class="bpe-team-level">' + level + '</div>' +
        '<div class="bpe-team-moves">' +
        moveList(member.set).map(function (move) {
          return '<span class="bpe-team-move">' + escapeHtml(move) + "</span>";
        }).join("") +
        "</div></div>";
    });
    container.innerHTML = html + "</div>";
    container.hidden = false;
  }

  // What the opposing side is showing. select2 keeps the chosen option in its
  // own data; the input's value is only reliable for a set picked by hand.
  function currentSetId() {
    var selector = $("#p2 .set-selector");
    var selected = selector.data("select2") ? selector.select2("data") : null;
    return (selected && selected.id) || selector.val() || "";
  }

  function mount() {
    if (document.getElementById("bpe-team")) return;
    var container = document.createElement("div");
    container.id = "bpe-team";
    container.className = "bpe-team";
    container.hidden = true;
    BPE.strip().appendChild(container);

    // Clicking a team member loads that exact set on the opposing side.
    $(container).on("click", ".bpe-team-mon", function () {
      var id = this.getAttribute("data-set-id");
      if (!id || id === currentSetId()) return;
      BPE.loadOpposingSet(id);
    });
  }

  BPE.renderTeam = function () { render(currentSetId()); };

  // Load a set on the opposing side. The selector is a select2 input over the
  // calculator's own option objects, so the selection goes in as one of those
  // or the box keeps showing the previous Pokémon's name.
  BPE.loadOpposingSet = function (id) {
    var selector = $("#p2 .set-selector");
    var split = id.indexOf(" (");
    var option = {
      id: id,
      text: id,
      pokemon: split > 0 ? id.slice(0, split) : id,
      set: split > 0 ? id.slice(split + 2, id.lastIndexOf(")")) : ""
    };
    if (selector.data("select2")) selector.select2("data", option, true);
    else selector.val(id).change();
  };

  BPE.ready(function (data) {
    index(data);
    mount();
    render(currentSetId());
    // The set selector is a select2 input; its change event is what the
    // calculator itself listens to.
    $("#p2 .set-selector").on("change", function () { render(currentSetId()); });
  });
}(typeof window !== "undefined" ? window : globalThis));
