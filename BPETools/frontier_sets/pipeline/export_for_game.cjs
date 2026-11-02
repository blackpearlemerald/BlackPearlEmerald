// Writes the two files the game build reads: sets.json (tested sets, grouped into pools)
// and rules.json (who and what each generation and tier allows, from Showdown's own validator).
// Usage: node export_for_game.cjs   (needs the work folder described in ../README.md)
const fs = require('fs');
const path = require('path');

const OUT = path.resolve(__dirname, '..');
const REPO = path.resolve(OUT, '..', '..');
const WORK = process.env.BPE_FRONTIER_WORK || path.join(REPO, '.release-work', 'frontier-sets');
const {Dex, TeamValidator} = require(path.join(WORK, 'showdown', 'dist', 'sim', 'index.js'));

const toID = Dex.toID;
const GENS = ['nd', '1', '2', '3', '4', '5', '6', '7', '8', '9'];
const SINGLES = ['Ubers', 'OU', 'UU', 'RU'];
const DOUBLES = ['DUber', 'DOU'];
const SPECIES_BIT = {AG: 1, Ubers: 2, OU: 4, UU: 8, RU: 16, DUber: 32, DOU: 64};

function exists(id) {
	return Dex.formats.get(id).exists ? id : null;
}

function formatId(g, tier) {
	if (g === 'nd') return {Ubers: 'gen9nationaldexubers', OU: 'gen9nationaldex', UU: 'gen9nationaldexuu', RU: 'gen9nationaldexru', DOU: 'gen9nationaldexdoubles', DUber: 'gen9nationaldexdoublesubers'}[tier];
	const p = 'gen' + g;
	return {
		Ubers: exists(p + 'ubers') || exists(p + 'ou'), OU: exists(p + 'ou'), UU: exists(p + 'uu'), RU: exists(p + 'ru') || exists(p + 'nu') || exists(p + 'uu'),
		DOU: exists(p + 'doublesou'), DUber: exists(p + 'doublesubers') || exists(p + 'anythinggoes') || exists(p + 'ubers'),
	}[tier];
}

function dexFor(g) {
	return Dex.mod(g === 'nd' || g === '9' ? 'gen9' : 'gen' + g);
}

function enumNames(file, prefix) {
	const text = fs.readFileSync(path.join(REPO, file), 'utf8');
	// Aliases such as ITEM_BRIGHTPOWDER = ITEM_BRIGHT_POWDER are left out.
	return [...new Set([...text.matchAll(new RegExp(`\\b${prefix}_(\\w+)\\s*=(?!\\s*${prefix}_)`, 'g'))].map((m) => m[1]))];
}

const SPECIES_SUFFIX = ['normal', 'hero', 'incarnate', 'altered', 'singlestrike', 'midday', 'disguised', 'tealmask', 'west', 'teal', 'male',
	'aria', 'ordinary', 'red', 'plant', 'overcast', 'standard', 'fifty', 'fiftypercent', 'solo', 'shield', 'land', 'white', 'natural', 'baile',
	'core', 'fullbelly', 'zero', 'gulping', 'ice', 'familyofthree', 'twosegment', 'average', 'confined', 'amped', 'phantom', 'unremarkable'];

// A BPE species name, as the Showdown species it stands for.
function showdownSpecies(dex, name) {
	const id = toID(name).replace(/gigantamax$/, 'gmax');
	let s = dex.species.get(id);
	if (s.exists) return s;
	for (const suffix of SPECIES_SUFFIX) {
		if (id.endsWith(suffix)) {
			s = dex.species.get(id.slice(0, -suffix.length));
			if (s.exists) return s;
		}
	}
	// Cosmetic forms Showdown doesn't list, such as ALCREMIE_STRAWBERRY_RUBY_SWIRL.
	const words = name.split('_');
	while (words.pop() && words.length) {
		s = dex.species.get(toID(words.join('')));
		if (s.exists) return s;
	}
	return null;
}

function inEra(g, thing) {
	if (!thing || !thing.exists) return false;
	if (g === 'nd') return !['CAP', 'Custom', 'Future', 'LGPE'].includes(thing.isNonstandard);
	return !thing.isNonstandard;
}

function buildRules() {
	const speciesNames = enumNames('include/constants/species.h', 'SPECIES').filter((n) => !/^(NONE|EGG|COUNT|SHINY_TAG|CUSTOM_START)$/.test(n));
	const moveNames = enumNames('include/constants/moves.h', 'MOVE').filter((n) => n !== 'NONE');
	const itemNames = enumNames('include/constants/items.h', 'ITEM').filter((n) => n !== 'NONE');
	const abilityNames = enumNames('include/constants/abilities.h', 'ABILITY').filter((n) => n !== 'NONE');
	const rules = {gens: GENS, species: {}, moves: {}, items: {}, bans: {}};
	const unmapped = new Set();
	const dexNine = dexFor('nd');
	for (const n of speciesNames) rules.species[n] = GENS.map(() => 0);
	for (const n of moveNames) rules.moves[n] = 0;
	for (const n of itemNames) rules.items[n] = 0;

	GENS.forEach((g, gi) => {
		const dex = dexFor(g);
		const set = {species: 'Pikachu', name: 'x', moves: [], ability: '', item: ''};
		const era = {};
		for (const n of speciesNames) {
			const s = showdownSpecies(dex, n);
			if (!s) {
				unmapped.add(n);
				continue;
			}
			era[n] = s;
			if (inEra(g, s)) rules.species[n][gi] |= SPECIES_BIT.AG;
		}
		const known = new Set(moveNames.filter((n) => dexNine.moves.get(toID(n)).exists));
		for (const n of moveNames) {
			// Z-Moves and Max Moves can't be taught, so only real moves need a rule.
			if (!known.has(n) || inEra(g, dex.moves.get(toID(n)))) rules.moves[n] |= 1 << gi;
		}
		for (const n of itemNames) {
			const anyGen = dexNine.items.get(toID(n)).exists;
			if (g !== '1' && (!anyGen || inEra(g, dex.items.get(toID(n))))) rules.items[n] |= 1 << gi;
		}
		rules.bans[g] = {};
		for (const tier of [...SINGLES, ...DOUBLES]) {
			const fmt = formatId(g, tier);
			if (!fmt) continue;
			const v = TeamValidator.get(fmt);
			const ban = {format: fmt, moves: [], items: [], abilities: []};
			for (const n of speciesNames) {
				const s = era[n];
				if (s && !v.checkSpecies(set, s, s, {})) rules.species[n][gi] |= SPECIES_BIT[tier];
			}
			for (const n of moveNames) {
				const m = dex.moves.get(toID(n));
				if (known.has(n) && inEra(g, m) && v.checkMove(set, m, {})) ban.moves.push(n);
			}
			for (const n of itemNames) {
				const it = dex.items.get(toID(n));
				if (!inEra(g, it)) continue;
				let banned = !!v.checkItem(set, it, {});
				const megas = it.megaStone ? (typeof it.megaStone === 'string' ? [it.megaStone] : Object.values(it.megaStone)) : [];
				if (it.id === 'redorb') megas.push('Groudon-Primal');
				if (it.id === 'blueorb') megas.push('Kyogre-Primal');
				if (it.id === 'ultranecroziumz') megas.push('Necrozma-Ultra');
				for (const form of megas) {
					const s = dex.species.get(form);
					if (s.exists && v.checkSpecies(set, s, s, {})) banned = true;
				}
				if (banned) ban.items.push(n);
			}
			for (const n of abilityNames) {
				if (v.ruleTable.check('ability:' + toID(n))) ban.abilities.push(n);
			}
			rules.bans[g][tier] = ban;
		}
	});
	console.log('species with no Showdown match:', [...unmapped].join(' '));
	return rules;
}

function buildSets() {
	const final = path.join(WORK, 'final');
	const sets = [], index = new Map(), pools = {};
	const add = (pool, list) => {
		const out = [];
		for (const s of list.slice().sort((a, b) => b.wr - a.wr || a.form.localeCompare(b.form))) {
			const row = [s.species, s.form, s.item, s.ability, s.nature, s.evs, s.moves, s.grade, s.source];
			const key = JSON.stringify(row.slice(0, 7));
			if (!index.has(key)) {
				index.set(key, sets.length);
				sets.push(row);
			}
			out.push([index.get(key), Math.round((s.wr || 0) * 1000), s.games || 0]);
		}
		pools[pool] = out;
	};
	for (const f of fs.readdirSync(final).sort()) {
		if (f.endsWith('.json') && !f.startsWith('_')) add(f.replace('.json', ''), JSON.parse(fs.readFileSync(path.join(final, f), 'utf8')));
	}
	const ag = path.join(WORK, 'final_ag');
	for (const f of fs.readdirSync(ag).sort()) add(f.replace('.json', ''), JSON.parse(fs.readFileSync(path.join(ag, f), 'utf8')));
	return {sets, pools};
}

// One entry per line, so that a change to a set is a small diff.
const {sets, pools} = buildSets();
const poolText = Object.entries(pools).map(([k, v]) => JSON.stringify(k) + ':' + JSON.stringify(v));
fs.writeFileSync(path.join(OUT, 'sets.json'), '{"format":1,"sets":[\n' + sets.map((s) => JSON.stringify(s)).join(',\n') + '\n],"pools":{\n' + poolText.join(',\n') + '\n}}\n');

const rules = buildRules();
const rulesText = ['"gens":' + JSON.stringify(rules.gens)];
for (const k of ['species', 'moves', 'items']) rulesText.push(JSON.stringify(k) + ':{\n' + Object.entries(rules[k]).map(([n, v]) => JSON.stringify(n) + ':' + JSON.stringify(v)).join(',\n') + '\n}');
rulesText.push('"bans":{\n' + Object.entries(rules.bans).map(([n, v]) => JSON.stringify(n) + ':' + JSON.stringify(v)).join(',\n') + '\n}');
fs.writeFileSync(path.join(OUT, 'rules.json'), '{' + rulesText.join(',\n') + '}\n');
console.log(sets.length, 'sets', Object.keys(pools).length, 'pools');
