// Builds every candidate set for Gens 1-9 and National Dex, then checks each with Showdown's validator.
// Sources: Showdown Factory and Battle Stadium sets, Showdown's Random Battle generator, Smogon usage stats.
// Output: cand/<gen>-<tier>.json
const fs = require('fs');
const os = require('os');
const path = require('path');
const {Worker, isMainThread, parentPort, workerData} = require('worker_threads');

const ROOT = __dirname;
const {Dex, Teams, TeamValidator} = require(path.join(ROOT, 'showdown', 'dist', 'sim', 'index.js'));
const bpe = JSON.parse(fs.readFileSync(path.join(ROOT, 'bpe_data.json'), 'utf8'));
const statsIndex = JSON.parse(fs.readFileSync(path.join(ROOT, 'stats_index.json'), 'utf8'));
const toID = Dex.toID;
const hp = (m) => m.replace(/^hiddenpower.*/, 'hiddenpower');
const STATS = ['hp', 'atk', 'def', 'spa', 'spd', 'spe'];

const GROUPS = [
	['recover', 'roost', 'softboiled', 'slackoff', 'synthesis', 'moonlight', 'morningsun', 'milkdrink', 'shoreup', 'strengthsap', 'rest'],
	['protect', 'detect', 'kingsshield', 'spikyshield', 'banefulbunker', 'silktrap', 'burningbulwark', 'obstruct'],
	['uturn', 'voltswitch', 'flipturn', 'partingshot', 'teleport', 'chillyreception'],
	['toxic', 'willowisp', 'thunderwave', 'spore', 'sleeppowder', 'glare', 'stunspore', 'hypnosis', 'lovelykiss', 'yawn'],
].map((g) => new Set(g));
const PHYS_SETUP = new Set(['swordsdance', 'bulkup', 'dragondance', 'bellydrum', 'coil', 'howl', 'shiftgear', 'curse', 'victorydance', 'honeclaws', 'tidyup', 'filletaway']);
const SPEC_SETUP = new Set(['nastyplot', 'calmmind', 'quiverdance', 'tailglow', 'geomancy', 'takeheart', 'growth']);
const UTILITY = new Set(['uturn', 'voltswitch', 'flipturn', 'knockoff', 'fakeout', 'rapidspin', 'mortalspin', 'trailblaze', 'icywind', 'snarl',
	'electroweb', 'bulldoze', 'foulplay', 'nightshade', 'seismictoss', 'superfang', 'ruination', 'pursuit']);
const ALWAYS_BANNED = new Set(['terablast', 'terastarstorm']);

function bpeId(id) {
	if (bpe.species[id]) return id;
	for (const s of bpe.defaults) if (bpe.species[id + s]) return id + s;
	const c = Object.keys(bpe.species).filter((k) => k.startsWith(id)).sort((a, b) => a.length - b.length);
	return c[0] || null;
}
const moveInfo = (m) => bpe.moves[hp(m)];
const cat = (m) => (moveInfo(m) ? moveInfo(m).cat : null);

function pickMoves(pool, cls, item) {
	const onlyAttacks = ['choiceband', 'choicespecs', 'choicescarf', 'assaultvest'].includes(item);
	const chosen = [];
	const groups = new Set();
	const seen = new Set();
	for (const [mv, share] of pool) {
		if (chosen.length === 4) break;
		const c = cat(mv);
		if (!c) continue;
		if (onlyAttacks && c === 'STATUS' && !(['trick', 'switcheroo'].includes(mv) && item.startsWith('choice'))) continue;
		if (cls === 'phys' && (SPEC_SETUP.has(mv) || (c === 'SPECIAL' && share < 0.5 && !UTILITY.has(mv)))) continue;
		if (cls === 'spec' && (PHYS_SETUP.has(mv) || (c === 'PHYSICAL' && share < 0.5 && !UTILITY.has(mv)))) continue;
		const group = GROUPS.findIndex((g) => g.has(mv));
		if (group >= 0 && groups.has(group) && share < 0.45) continue;
		const key = moveInfo(mv).type + c;
		if (c !== 'STATUS' && !UTILITY.has(mv) && seen.has(key) && share < 0.45) continue;
		chosen.push([mv, share]);
		if (group >= 0) groups.add(group);
		if (c !== 'STATUS') seen.add(key);
	}
	if (chosen.length < 4) return null;
	const attacks = chosen.filter(([m]) => cat(m) !== 'STATUS').length;
	if (!attacks || (['phys', 'spec'].includes(cls) && attacks < 2)) return null;
	return chosen;
}

function classifySpread(s) {
	const [nat, raw] = s.split(':');
	const v = raw.split('/').map(Number);
	return {nature: nat.toLowerCase(), evs: v, cls: v[1] >= 128 && v[3] >= 128 ? 'mixed' : v[1] >= 128 ? 'phys' : v[3] >= 128 ? 'spec' : 'bulky'};
}

function roleSpread(moves, role) {
	const phys = moves.filter((m) => cat(m) === 'PHYSICAL').length;
	const spec = moves.filter((m) => cat(m) === 'SPECIAL').length;
	const bulky = role ? /Bulky|Staller|Support|Protect|Redirection/.test(role) : phys + spec <= 1;
	const attacker = phys >= spec ? 'phys' : 'spec';
	if (bulky && phys + spec <= 2) return {nature: phys <= spec ? 'bold' : 'impish', evs: [252, 0, 128, 0, 128, 0]};
	if (bulky) return {nature: attacker === 'phys' ? 'adamant' : 'modest', evs: [252, attacker === 'phys' ? 252 : 0, 0, attacker === 'spec' ? 252 : 0, 4, 0]};
	return {nature: attacker === 'phys' ? 'jolly' : 'timid', evs: [4, attacker === 'phys' ? 252 : 0, 0, attacker === 'spec' ? 252 : 0, 0, 252]};
}

// Usage stats ---------------------------------------------------------------
function usageSets(name, info) {
	const out = [];
	const m = name.match(/^gen(\d)(.*)$/);
	const gen = +m[1];
	const natdex = m[2].startsWith('nationaldex');
	const mode = /doubles/.test(m[2]) ? 'd' : 's';
	const d = JSON.parse(fs.readFileSync(path.join(ROOT, 'stats', info.file), 'utf8'));
	for (const [spName, v] of Object.entries(d.data)) {
		const usage = v.usage || 0;
		if (usage < 0.003 || (v['Raw count'] || 0) < 40) continue;
		const W = Object.values(v.Moves).reduce((a, b) => a + b, 0) / 4;
		if (W <= 0) continue;
		const pool = Object.entries(v.Moves).map(([k, w]) => [k, w / W]).filter(([k, s]) => k && s >= 0.1 && !ALWAYS_BANNED.has(k)).sort((a, b) => b[1] - a[1]);
		const items = Object.entries(v.Items || {}).map(([k, w]) => [k, w / W]).filter(([k, s]) => k && k !== 'nothing' && s >= 0.1 && bpe.items.includes(k)).sort((a, b) => b[1] - a[1]);
		const abilities = Object.entries(v.Abilities || {}).filter(([k]) => k).sort((a, b) => b[1] - a[1]).map(([k]) => bpe.abilityAlias[k] || k);
		const old = gen <= 2;
		const classes = {};
		for (const [sp, w] of Object.entries(v.Spreads || {}).sort((a, b) => b[1] - a[1])) {
			if (sp.startsWith('Other')) continue;
			const c = classifySpread(sp);
			if (['modest', 'timid', 'bold', 'calm'].includes(c.nature) && c.cls === 'phys') continue;
			if (['adamant', 'jolly', 'impish', 'careful'].includes(c.nature) && c.cls === 'spec') continue;
			(classes[c.cls] = classes[c.cls] || []).push([sp, w]);
		}
		const groups = old ? [['phys', null], ['spec', null], ['bulky', null]] : Object.entries(classes).filter(([cls, g]) => cls !== 'mixed' && g.reduce((a, x) => a + x[1], 0) / W >= 0.12 && g[0][1] / W >= 0.03).map(([cls, g]) => [cls, g[0][0]]);
		for (const [cls, sp] of groups) {
			const itemList = gen === 1 ? [['', 1]] : (items.length ? items.slice(0, 3) : [['leftovers', 0]]);
			let made = 0;
			for (const [item, ishare] of itemList) {
				if (made === 2) break;
				if ((item === 'choiceband' && cls !== 'phys') || (item === 'choicespecs' && cls !== 'spec') || (item === 'choicescarf' && cls === 'bulky')) continue;
				if (cls === 'bulky' && ['focussash', 'expertbelt', 'lifeorb', 'widelens'].includes(item)) continue;
				const chosen = pickMoves(pool, cls, item);
				if (!chosen) continue;
				const low = Math.min(...chosen.map((c) => c[1]));
				if (low < 0.1) continue;
				const moves = chosen.map((c) => c[0]);
				let nature, evs;
				if (old) ({nature, evs} = roleSpread(moves)); else ({nature, evs} = classifySpread(sp));
				const grade = (usage >= 0.01 && low >= 0.25 && (gen === 1 || ishare >= 0.15) && info.battles >= 3000) ? 'A' : 'B';
				out.push({gen: natdex ? 'nd' : String(gen), mode, species: spName, item, ability: abilities[0] || '', nature, evs, moves, grade, source: name,
					evidence: {usage: +usage.toFixed(4), raw: v['Raw count'], low: +low.toFixed(2), item: +ishare.toFixed(2), battles: info.battles, month: info.month, cutoff: info.cutoff}});
				made++;
			}
		}
	}
	return out;
}

// Showdown's Factory files --------------------------------------------------
function* walk(o, tier) {
	for (const [k, v] of Object.entries(o)) {
		if (v && typeof v === 'object' && Array.isArray(v.sets)) yield [tier, k, v.sets];
		else if (v && typeof v === 'object') yield* walk(v, k);
	}
}
function factorySets() {
	const out = [];
	const asList = (x) => (Array.isArray(x) ? x : x ? [x] : []);
	for (const g of [6, 7, 8, 9]) {
		for (const file of ['factory-sets.json', 'bss-factory-sets.json']) {
			const p = path.join(ROOT, 'showdown', 'data', 'random-battles', `gen${g}`, file);
			if (!fs.existsSync(p)) continue;
			for (const [tier, key, sets] of walk(JSON.parse(fs.readFileSync(p, 'utf8')))) {
				if (tier === 'Mono' || tier === 'LC') continue;
				for (const s of sets) {
					const slots = (s.moves || []).map(asList).map((l) => l.map(toID));
					if (slots.length < 4) continue;
					const items = asList(s.item).map(toID);
					const abilities = asList(s.ability).map(toID);
					const natures = asList(s.nature).map(toID);
					// Slots often hold options; take several real combinations of them.
					const seen = new Set();
					for (let v = 0; v < 6; v++) {
						const moves = slots.map((l, i) => l[(v + i) % l.length]);
						if (new Set(moves).size < 4) continue;
						const k = moves.slice().sort().join();
						if (seen.has(k)) continue;
						seen.add(k);
						for (const item of items.slice(0, 2)) {
							out.push({gen: String(g), mode: 's', species: s.species || key, item, ability: abilities[0] || '', nature: natures[0] || 'serious',
								evs: STATS.map((x) => (s.evs || {})[x] || 0), moves, grade: 'A', source: `gen${g}-${file.replace('-sets.json', '')}`, evidence: {}});
						}
					}
				}
			}
		}
	}
	return out;
}

// Showdown's Random Battle generator ----------------------------------------
function randomSets() {
	const out = [];
	const seen = new Set();
	const ids = [];
	for (let g = 1; g <= 9; g++) ids.push([g, `gen${g}randombattle`, 's']);
	for (const g of [7, 8, 9]) ids.push([g, `gen${g}randomdoublesbattle`, 'd']);
	for (const [g, id, mode] of ids) {
		const f = Dex.formats.get(id);
		if (!f.exists) continue;
		for (let i = 0; i < 2500; i++) {
			let team;
			try {
				team = Teams.generate(id);
			} catch {
				break;
			}
			for (const p of team) {
				const moves = p.moves.map(toID).filter((m) => !ALWAYS_BANNED.has(m));
				if (moves.length < 4) continue;
				const k = [g, mode, toID(p.species), toID(p.item), moves.slice().sort().join()].join('|');
				if (seen.has(k)) continue;
				seen.add(k);
				const {nature, evs} = roleSpread(moves, p.role);
				out.push({gen: String(g), mode, species: p.species, item: toID(p.item), ability: toID(p.ability), nature, evs, moves, grade: 'C', source: id, role: p.role || '', evidence: {}});
			}
		}
		console.log(id, 'running total', out.length);
	}
	return out;
}

// Tier assignment and validation --------------------------------------------
function dexFor(g) {
	return g === 'nd' || g === '9' ? Dex.mod('gen9') : Dex.mod('gen' + g);
}
function bucket(t) {
	if (!t) return null;
	t = t.replace(/[()]/g, '');
	if (t === 'AG') return 'AG';
	if (t === 'Uber') return 'Ubers';
	if (t === 'OU' || t === 'UUBL') return 'OU';
	if (t === 'UU' || t === 'RUBL') return 'UU';
	if (['RU', 'NUBL', 'NU', 'PUBL', 'PU', 'ZUBL', 'ZU'].includes(t)) return 'RU';
	return null;
}
function formatId(g, tier) {
	const ex = (id) => (Dex.formats.get(id).exists ? id : null);
	if (g === 'nd') return {Ubers: 'gen9nationaldexubers', OU: 'gen9nationaldex', UU: 'gen9nationaldexuu', RU: 'gen9nationaldexru', AG: 'gen9nationaldexag', DOU: 'gen9nationaldexdoubles', DUber: 'gen9nationaldexdoublesubers'}[tier];
	const p = 'gen' + g;
	return {
		Ubers: ex(p + 'ubers') || ex(p + 'ou'), OU: ex(p + 'ou'), UU: ex(p + 'uu'), RU: ex(p + 'ru') || ex(p + 'nu') || ex(p + 'uu'),
		AG: ex(p + 'anythinggoes') || ex(p + 'ubers'), DOU: ex(p + 'doublesou'), DUber: ex(p + 'doublesubers') || ex(p + 'anythinggoes') || ex(p + 'ubers'),
	}[tier];
}

function normalise(s) {
	const dex = dexFor(s.gen);
	const sp = dex.species.get(s.species);
	if (!sp.exists) return null;
	let base = sp;
	if (sp.isMega || sp.isPrimal || sp.forme === 'Mega' || /^Mega/.test(sp.forme)) base = dex.species.get(sp.baseSpecies);
	const item = s.item ? dex.items.get(s.item) : null;
	let form = base;
	if (item && item.megaStone) {
		const target = typeof item.megaStone === 'string' ? item.megaStone : item.megaStone[base.name];
		if (target) form = dex.species.get(target);
	}
	if (s.gen === '1') s.item = '';
	const key = bpeId(base.id);
	if (!key || !bpe.species[key]) return null;
	if (s.item && !bpe.items.includes(s.item)) return null;
	const info = bpe.species[key];
	const moves = s.moves.map(toID);
	if (moves.some((m) => !bpe.moves[hp(m)])) return null;
	const strict = moves.every((m) => info.moves.includes(hp(m)));
	const loose = strict || moves.every((m) => info.moves.includes(hp(m)) || (bpe.allLearn[key] || bpe.allLearn[base.id] || []).includes(hp(m)));
	if (!loose) return null;
	let ability = bpe.abilityAlias[s.ability] || s.ability;
	// Macro-built forms such as Arceus and Silvally have no ability list in the dump; trust the set.
	if (info.abilities.length && !info.abilities.includes(ability)) ability = info.abilities[0];
	if (!ability) return null;
	return {...s, species: base.id, form: form.id, name: base.name, ability, moves, strict};
}

function validate(jobs) {
	const out = [];
	const cache = {};
	for (const s of jobs) {
		const v = (cache[s.fmt] = cache[s.fmt] || TeamValidator.get(s.fmt));
		const set = {species: s.name, item: s.item, ability: s.ability, nature: s.nature, moves: s.moves, level: 100, gender: '',
			evs: Object.fromEntries(STATS.map((k, i) => [k, s.evs[i]])), ivs: {hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31}};
		if (s.moves.some((m) => m.startsWith('hiddenpower'))) set.ivs = undefined;
		let problems;
		try {
			problems = v.validateTeam([set]);
		} catch (e) {
			problems = ['crash ' + e.message];
		}
		const real = (problems || []).filter((p) => !/bring at least|must bring|team must|at least \d+|Team size/i.test(p) && !/EVs|Hidden Power|IVs|ability/i.test(p));
		out.push(real.length ? {ok: false, tier: s.tier, gen: s.gen, why: real[0].slice(0, 90)} : {ok: true, set: s});
	}
	return out;
}

if (!isMainThread) {
	parentPort.postMessage(validate(workerData));
	return;
}

(async () => {
	const all = [];
	console.log('Factory');
	all.push(...factorySets());
	console.log('after factory', all.length);
	for (const [name, info] of Object.entries(statsIndex)) all.push(...usageSets(name, info));
	console.log('after usage', all.length);
	all.push(...randomSets());
	console.log('after random', all.length);

	const jobs = [];
	const seen = new Set();
	const push = (s, tier, grade) => {
		const fmt = formatId(s.gen, tier);
		if (!fmt) return;
		const key = [s.gen, tier, s.form, s.item, s.moves.slice().sort().join()].join('|');
		if (seen.has(key)) return;
		seen.add(key);
		jobs.push({...s, tier, fmt, grade: grade || s.grade});
	};
	for (const raw of all) {
		// Sets from Gen 5 on also feed National Dex, whose rules cover every generation.
		const copies = [raw];
		if (raw.gen !== 'nd' && +raw.gen >= 5) copies.push({...raw, gen: 'nd', grade: raw.gen === '9' ? raw.grade : (raw.grade === 'A' ? 'A' : raw.grade)});
		for (const c of copies) {
			const s = normalise({...c});
			if (!s) continue;
			const dex = dexFor(s.gen);
			const fs_ = dex.species.get(s.form);
			if (!fs_.exists) continue;
			const t = s.gen === 'nd' ? (fs_.natDexTier || fs_.tier) : fs_.tier;
			const tier = bucket(t);
			if (s.mode === 's') {
				if (tier) push(s, tier);
				// Singles sets are extra options for doubles; the battle tests decide if they stay.
				if (s.gen === 'nd' || +s.gen >= 3) {
					push(s, 'DOU', 'C');
					push(s, 'DUber', 'C');
				}
			} else {
				if (s.gen === 'nd' || +s.gen >= 3) {
					push(s, 'DOU');
					push(s, 'DUber');
				}
			}
		}
	}
	console.log('jobs', jobs.length);

	const n = Math.min(9, Math.floor(os.cpus().length * 0.4));
	os.setPriority(os.constants.priority.PRIORITY_BELOW_NORMAL);
	const chunks = Array.from({length: n}, () => []);
	jobs.forEach((j, i) => chunks[i % n].push(j));
	const results = (await Promise.all(chunks.map((c) => new Promise((res, rej) => {
		const w = new Worker(__filename, {workerData: c});
		w.on('message', res);
		w.on('error', rej);
	})))).flat();

	const pools = {};
	const why = {};
	for (const r of results) {
		if (r.ok) {
			const s = r.set;
			const k = `${s.gen}-${s.tier}`;
			(pools[k] = pools[k] || []).push(s);
		} else {
			const k = r.why.replace(/^.*?(is|has|can't|cannot)/, '$1').slice(0, 40);
			why[k] = (why[k] || 0) + 1;
		}
	}
	fs.mkdirSync(path.join(ROOT, 'cand'), {recursive: true});
	const summary = {};
	for (const [k, sets] of Object.entries(pools)) {
		fs.writeFileSync(path.join(ROOT, 'cand', k + '.json'), JSON.stringify(sets));
		summary[k] = {sets: sets.length, pokemon: new Set(sets.map((s) => s.form)).size, A: sets.filter((s) => s.grade === 'A').length, B: sets.filter((s) => s.grade === 'B').length, C: sets.filter((s) => s.grade === 'C').length, strict: sets.filter((s) => s.strict).length};
	}
	fs.writeFileSync(path.join(ROOT, 'cand', '_summary.json'), JSON.stringify(summary, null, 1));
	console.log(Object.entries(summary).sort().map(([k, v]) => `${k}: ${v.sets} sets, ${v.pokemon} mons, A${v.A} B${v.B} C${v.C}, learnable ${v.strict}`).join('\n'));
	console.log('rejected reasons', Object.entries(why).sort((a, b) => b[1] - a[1]).slice(0, 12));
})();
