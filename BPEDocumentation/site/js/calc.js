/**
 * BPE Emerald Damage Calculator
 * Uses @smogon/calc (Gen 9) via esm.sh CDN.
 * Trainer team loader pulls from js/data/trainers.json + world.json.
 */

import { Dex } from 'https://esm.sh/@smogon/data';
import { Generations, Pokemon, Move, Field, calculate } from 'https://esm.sh/@smogon/calc';

// ── Globals ──────────────────────────────────────────────────────────────────

const gens = new Generations(Dex);
const gen = gens.get(9);

const NATURES = [
  'Hardy','Lonely','Brave','Adamant','Naughty',
  'Bold','Docile','Relaxed','Impish','Lax',
  'Timid','Hasty','Serious','Jolly','Naive',
  'Modest','Mild','Quiet','Bashful','Rash',
  'Calm','Gentle','Sassy','Careful','Quirky',
];

const TYPES = [
  'Normal','Fire','Water','Electric','Grass','Ice',
  'Fighting','Poison','Ground','Flying','Psychic','Bug',
  'Rock','Ghost','Dragon','Dark','Steel','Fairy',
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function prettifyMap(id) {
  if (!id) return '';
  const s = id.replace(/^MAP_/, '').replace(/_/g, ' ')
    .split(' ').map(w => w ? w[0].toUpperCase() + w.slice(1).toLowerCase() : w)
    .join(' ');
  return s.replace(/([A-Za-z])(\d)/g, '$1 $2');
}

function populateSelect(sel, opts, selected = '') {
  sel.innerHTML = opts.map(v =>
    `<option value="${esc(v)}"${v === selected ? ' selected' : ''}>${esc(v)}</option>`
  ).join('');
}

function readEVs(prefix) {
  return {
    hp:  Number(document.getElementById(`${prefix}-hp`).value) || 0,
    atk: Number(document.getElementById(`${prefix}-atk`).value) || 0,
    def: Number(document.getElementById(`${prefix}-def`).value) || 0,
    spa: Number(document.getElementById(`${prefix}-spa`).value) || 0,
    spd: Number(document.getElementById(`${prefix}-spd`).value) || 0,
    spe: Number(document.getElementById(`${prefix}-spe`).value) || 0,
  };
}

function fillEVs(prefix, evs) {
  const map = { hp:'hp', atk:'atk', def:'def', spa:'spa', spd:'spd', spe:'spe' };
  Object.entries(map).forEach(([stat, key]) => {
    const el = document.getElementById(`${prefix}-${stat}`);
    if (el) el.value = (evs && evs[stat]) || 0;
  });
}

function fillField(id, val) {
  const el = document.getElementById(id);
  if (el) el.value = val || '';
}

function fillCheck(id, val) {
  const el = document.getElementById(id);
  if (el) el.checked = !!val;
}

// ── Move selector sync ────────────────────────────────────────────────────────

function syncMoveSelect() {
  const sel = document.getElementById('calc-move-select');
  const inputs = document.querySelectorAll('#att-moves .calc-move-input');
  const moves = Array.from(inputs).map(i => i.value.trim()).filter(Boolean);
  const prev = sel.value;
  sel.innerHTML = moves.length
    ? moves.map(m => `<option value="${esc(m)}"${m === prev ? ' selected' : ''}>${esc(m)}</option>`).join('')
    : '<option value="">— fill a move above —</option>';
}

// ── Calculation ───────────────────────────────────────────────────────────────

function doCalculate() {
  const resultEl = document.getElementById('calc-result');

  const moveName = document.getElementById('calc-move-select').value.trim();
  if (!moveName) {
    showResult(resultEl, 'Enter moves above and select one to calculate.', true);
    return;
  }

  const attSpecies = document.getElementById('att-species').value.trim();
  const defSpecies = document.getElementById('def-species').value.trim();
  if (!attSpecies || !defSpecies) {
    showResult(resultEl, 'Enter both species first.', true);
    return;
  }

  try {
    const attOpts = {
      level:   Number(document.getElementById('att-level').value) || 50,
      nature:  document.getElementById('att-nature').value || 'Hardy',
      evs:     readEVs('att'),
      boosts:  { atk: Number(document.getElementById('att-boost').value) || 0,
                 spa: Number(document.getElementById('att-boost').value) || 0 },
      status:  document.getElementById('att-burned').checked ? 'brn' : '',
    };
    const attAbility = document.getElementById('att-ability').value.trim();
    if (attAbility) attOpts.ability = attAbility;
    const attItem = document.getElementById('att-item').value.trim();
    if (attItem) attOpts.item = attItem;
    const attTera = document.getElementById('att-tera').value;
    const attTeraActive = document.getElementById('att-tera-active').checked;
    if (attTera && attTeraActive) attOpts.teraType = attTera;

    const defOpts = {
      level:  Number(document.getElementById('def-level').value) || 50,
      nature: document.getElementById('def-nature').value || 'Hardy',
      evs:    readEVs('def'),
      boosts: { def: Number(document.getElementById('def-boost').value) || 0,
                spd: Number(document.getElementById('def-spd-boost').value) || 0 },
    };
    const defAbility = document.getElementById('def-ability').value.trim();
    if (defAbility) defOpts.ability = defAbility;
    const defItem = document.getElementById('def-item').value.trim();
    if (defItem) defOpts.item = defItem;
    const defTera = document.getElementById('def-tera').value;
    const defTeraActive = document.getElementById('def-tera-active').checked;
    if (defTera && defTeraActive) defOpts.teraType = defTera;

    const attacker = new Pokemon(gen, attSpecies, attOpts);
    const defender = new Pokemon(gen, defSpecies, defOpts);
    const move = new Move(gen, moveName);

    const fieldOpts = { gameType: 'Singles' };
    const attSide = {};
    const defSide = {};
    if (document.getElementById('field-reflect').checked) defSide.isReflect = true;
    if (document.getElementById('field-lscreen').checked) defSide.isLightScreen = true;
    if (document.getElementById('field-rain').checked)    fieldOpts.weather = 'Rain';
    if (document.getElementById('field-sun').checked)     fieldOpts.weather = 'Sun';
    if (document.getElementById('field-sand').checked)    fieldOpts.weather = 'Sand';
    if (document.getElementById('field-hail').checked)    fieldOpts.weather = 'Snow';
    fieldOpts.attackerSide = attSide;
    fieldOpts.defenderSide = defSide;
    const field = new Field(fieldOpts);

    const result = calculate(gen, attacker, defender, move, field);
    const dmg = result.damage;
    const rolls = Array.isArray(dmg) ? dmg : [dmg, dmg];
    const minDmg = Array.isArray(rolls[0]) ? rolls[0][0] : Math.min(...rolls);
    const maxDmg = Array.isArray(rolls[0]) ? rolls[rolls.length-1] : Math.max(...rolls);
    const defHP = result.defender.originalCurHP || result.defender.stats.hp;
    const minPct = ((minDmg / defHP) * 100).toFixed(1);
    const maxPct = ((maxDmg / defHP) * 100).toFixed(1);

    const desc = result.desc ? result.desc() : '';
    const html = `<div class="calc-result-main">${minPct}% – ${maxPct}% (${minDmg} – ${maxDmg} damage)</div>`
               + (desc ? `<div class="calc-result-desc">${esc(desc)}</div>` : '');
    resultEl.innerHTML = html;
    resultEl.className = 'calc-result';
  } catch (err) {
    showResult(resultEl, `Calculation error: ${err.message}. Check species and move names match Showdown format.`, true);
  }
}

function showResult(el, msg, isError = false) {
  el.textContent = msg;
  el.className = 'calc-result' + (isError ? ' error' : '');
}

// ── Trainer Loader ────────────────────────────────────────────────────────────

let trainerAll = [];
let trainerQuery = '';
let activePopup = null;

function renderTrainers(filtered) {
  const grid = document.getElementById('calc-tr-grid');
  const countEl = document.getElementById('calc-tr-count');
  countEl.textContent = filtered.length + ' trainers';

  if (!filtered.length) {
    grid.innerHTML = '<div class="dex-empty">No trainers match.</div>';
    return;
  }

  grid.innerHTML = filtered.slice(0, 120).map(t => {
    const sprite = t.sprite
      ? `<img class="calc-tr-sprite" src="img/sprites/${esc(t.sprite)}" alt="" onerror="this.style.display='none'">`
      : `<div class="calc-tr-sprite-ph"></div>`;

    const party = t.party.map((m, i) => {
      const icon = m.sprite
        ? `<img class="calc-mon-icon" src="img/pokemon/${esc(m.sprite)}" alt="${esc(m.species)}" onerror="this.remove()" loading="lazy">`
        : `<span style="font-size:10px;color:#5a7080">${esc(m.species.slice(0,6))}</span>`;
      return `<button class="calc-mon-btn" data-tid="${esc(t.id)}" data-pidx="${i}"
                title="${esc(m.species)} Lv.${m.level}">${icon}<span class="calc-mon-lv">Lv.${m.level}</span></button>`;
    }).join('');

    return `<div class="calc-tr-card">
      <div class="calc-tr-card-top">${sprite}<div>
        <div class="calc-tr-name">${esc(t.name)}</div>
        <div class="calc-tr-class">${esc(t.trClass)}</div>
      </div></div>
      <div class="calc-tr-party">${party}</div>
    </div>`;
  }).join('');

  // Wire up Pokémon buttons
  grid.querySelectorAll('.calc-mon-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      const tid = btn.dataset.tid;
      const pidx = parseInt(btn.dataset.pidx, 10);
      const trainer = trainerAll.find(t => t.id === tid);
      if (!trainer) return;
      const mon = trainer.party[pidx];
      if (!mon) return;
      showMonPopup(btn, mon);
    });
  });
}

function showMonPopup(anchor, mon) {
  dismissPopup();

  const popup = document.createElement('div');
  popup.className = 'calc-mon-popup';
  popup.innerHTML = `<h4>${esc(mon.species)} Lv.${mon.level}</h4>
    <button class="calc-popup-btn att" id="pp-att">Set as Attacker</button>
    <button class="calc-popup-btn def" id="pp-def">Set as Defender</button>`;

  document.body.appendChild(popup);
  activePopup = popup;

  const rect = anchor.getBoundingClientRect();
  let top = rect.bottom + window.scrollY + 6;
  let left = rect.left + window.scrollX;
  if (left + 200 > window.innerWidth) left = window.innerWidth - 210;
  popup.style.top = top + 'px';
  popup.style.left = left + 'px';

  popup.querySelector('#pp-att').addEventListener('click', () => { fillMon('att', mon); dismissPopup(); });
  popup.querySelector('#pp-def').addEventListener('click', () => { fillMon('def', mon); dismissPopup(); });

  setTimeout(() => document.addEventListener('click', dismissPopup, { once: true }), 10);
}

function dismissPopup() {
  if (activePopup) { activePopup.remove(); activePopup = null; }
}

function fillMon(role, mon) {
  fillField(`${role}-species`, mon.species || '');
  document.getElementById(`${role}-level`).value = mon.level || 50;
  if (mon.nature) document.getElementById(`${role}-nature`).value = mon.nature;
  fillField(`${role}-ability`, mon.ability || '');
  fillField(`${role}-item`, mon.item || '');
  if (mon.tera) {
    document.getElementById(`${role}-tera`).value = mon.tera;
  }

  if (mon.evs) {
    fillEVs(role, mon.evs);
  } else {
    fillEVs(role, null);
  }

  if (role === 'att' && mon.moves) {
    const inputs = document.querySelectorAll('#att-moves .calc-move-input');
    inputs.forEach((inp, i) => { inp.value = mon.moves[i] || ''; });
    syncMoveSelect();
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────

function init() {
  // Populate nature selects
  ['att-nature', 'def-nature'].forEach(id => {
    populateSelect(document.getElementById(id), NATURES, 'Hardy');
  });

  // Populate tera selects
  ['att-tera', 'def-tera'].forEach(id => {
    const sel = document.getElementById(id);
    sel.innerHTML = '<option value="">None</option>' +
      TYPES.map(t => `<option value="${t}">${t}</option>`).join('');
  });

  // Move select sync
  document.querySelectorAll('#att-moves .calc-move-input').forEach(inp => {
    inp.addEventListener('input', syncMoveSelect);
  });

  // Calculate button
  document.getElementById('calc-btn').addEventListener('click', doCalculate);

  // Allow Enter to calculate
  document.querySelector('.calc-main').addEventListener('keydown', e => {
    if (e.key === 'Enter') doCalculate();
  });

  // Trainer search
  document.getElementById('calc-tr-search').addEventListener('input', function () {
    trainerQuery = this.value.trim().toLowerCase();
    renderTrainers(filterTrainers());
  });

  // Load trainer data
  Promise.all([
    fetch('js/data/trainers.json').then(r => r.json()),
    fetch('js/data/world.json').then(r => r.json()),
  ]).then(([trainersData, world]) => {
    const spriteIndex = {};
    (world.trainers || []).forEach(t => {
      if (spriteIndex[t.trainerId]) return;
      const sp = world.sprites && world.sprites[t.gfx];
      if (!sp) return;
      const file = (sp.dirs && (sp.dirs[t.dir] || sp.dirs.down)) || sp.file;
      if (file) spriteIndex[t.trainerId] = file;
    });

    const mapTrainerSet = new Set((world.trainers || []).map(t => t.trainerId));

    trainerAll = Object.keys(trainersData)
      .filter(id => id !== 'TRAINER_NONE' && trainersData[id].party && trainersData[id].party.length > 0)
      .map(id => {
        const t = trainersData[id];
        return { id, name: t.name || '', trClass: t.class || '', party: t.party || [],
                 sprite: spriteIndex[id] || null, onMap: mapTrainerSet.has(id) };
      })
      .sort((a, b) => {
        if (a.onMap !== b.onMap) return a.onMap ? -1 : 1;
        const ka = (a.trClass + ' ' + a.name).toLowerCase();
        const kb = (b.trClass + ' ' + b.name).toLowerCase();
        return ka < kb ? -1 : ka > kb ? 1 : 0;
      });

    renderTrainers(filterTrainers());
  }).catch(() => {
    document.getElementById('calc-tr-grid').innerHTML =
      '<div class="dex-empty">Failed to load trainer data.</div>';
  });
}

function filterTrainers() {
  if (!trainerQuery) return trainerAll;
  return trainerAll.filter(t => {
    if (t.name.toLowerCase().includes(trainerQuery)) return true;
    if (t.trClass.toLowerCase().includes(trainerQuery)) return true;
    if (t.party.some(m => m.species && m.species.toLowerCase().includes(trainerQuery))) return true;
    return false;
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
