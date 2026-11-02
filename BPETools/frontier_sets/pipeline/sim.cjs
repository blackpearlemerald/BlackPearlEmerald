// Plays candidate sets against each other on Showdown's engine with a simple damage-minded AI.
// All pools use modern National Dex rules, the closest match to BPE's battle system.
// Usage: node sim.cjs <appearancesPerSet> [poolFilterRegex]
const fs = require('fs');
const os = require('os');
const path = require('path');
const {Worker, isMainThread, parentPort, workerData} = require('worker_threads');

const ROOT = __dirname;
const STATS = ['hp', 'atk', 'def', 'spa', 'spd', 'spe'];

function makeRng(seed) {
	let s = seed >>> 0;
	return () => {
		s = (s + 0x6D2B79F5) >>> 0;
		let t = s;
		t = Math.imul(t ^ (t >>> 15), t | 1);
		t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

function workerMain() {
	const {Battle, Dex} = require(path.join(ROOT, 'showdown', 'dist', 'sim', 'index.js'));
	const dex = Dex.mod('gen9');
	const SETUP = (m) => m.boosts === undefined && m.target === 'self' && m.selfBoost === undefined && false;

	function estimate(user, foe, move) {
		if (move.category === 'Status') return 0;
		if (!dex.getImmunity(move.type, foe)) return 0;
		const ability = foe.ability;
		if ((ability === 'levitate' && move.type === 'Ground') || (ability === 'flashfire' && move.type === 'Fire') ||
			(['waterabsorb', 'stormdrain', 'dryskin'].includes(ability) && move.type === 'Water') || (['voltabsorb', 'lightningrod', 'motordrive'].includes(ability) && move.type === 'Electric') ||
			(ability === 'sapsipper' && move.type === 'Grass')) return 0;
		if (move.damage === 'level') return 100 / foe.maxhp * 100;
		let bp = move.basePower || 70;
		if (move.multihit) bp *= Array.isArray(move.multihit) ? 3 : move.multihit;
		const off = user.getStat(move.category === 'Physical' ? 'atk' : 'spa', false, true);
		const def = foe.getStat(move.category === 'Physical' ? 'def' : 'spd', false, true);
		let d = (0.84 * bp * off / def + 2);
		if (user.hasType(move.type)) d *= ['adaptability'].includes(user.ability) ? 2 : 1.5;
		const eff = dex.getEffectiveness(move.type, foe);
		d *= Math.pow(2, eff);
		const acc = move.accuracy === true ? 1 : move.accuracy / 100;
		return d * acc * 0.925 / foe.maxhp * 100;
	}

	function statusScore(user, foes, side, move) {
		const hpPct = user.hp / user.maxhp;
		const id = move.id;
		const foe = foes[0];
		if (move.heal || move.flags.heal || ['recover', 'roost', 'softboiled', 'slackoff', 'synthesis', 'moonlight', 'morningsun', 'milkdrink', 'shoreup', 'rest', 'strengthsap'].includes(id)) return hpPct < 0.5 ? 75 : hpPct < 0.7 ? 25 : 0;
		if (move.boosts && move.target === 'self') {
			const stat = Object.keys(move.boosts)[0];
			return hpPct > 0.65 && user.boosts[stat] < 2 ? 62 : 0;
		}
		if (['stealthrock', 'spikes', 'toxicspikes', 'stickyweb'].includes(id)) return side.foe.sideConditions[id] ? 0 : (side.foe.pokemonLeft > 1 ? 58 : 0);
		if (['reflect', 'lightscreen', 'auroraveil', 'tailwind', 'trickroom'].includes(id)) return side.sideConditions[id] || user.battle.field.pseudoWeather[id] ? 0 : 50;
		if (move.status || move.volatileStatus === 'confusion') {
			if (!foe || foe.status) return 0;
			if (move.status && !foe.setStatus && false) return 0;
			if (!dex.getImmunity(move.type, foe)) return 0;
			if (move.status === 'tox' && (foe.hasType('Steel') || foe.hasType('Poison'))) return 0;
			if (move.status === 'brn' && foe.hasType('Fire')) return 0;
			if (move.status === 'par' && foe.hasType('Electric')) return 0;
			return 55;
		}
		if (['protect', 'detect', 'spikyshield', 'kingsshield', 'banefulbunker', 'silktrap', 'burningbulwark'].includes(id)) return side.battle.gameType === 'doubles' ? 30 : 8;
		if (id === 'wish') return hpPct < 0.7 ? 45 : 10;
		if (['taunt', 'encore', 'substitute', 'leechseed', 'haze', 'defog', 'rapidspin', 'whirlwind', 'roar', 'trick', 'switcheroo', 'partingshot', 'helpinghand', 'followme', 'ragepowder', 'allyswitch'].includes(id)) return 25;
		return 12;
	}

	function bestSwitch(side, req) {
		let best = -1, bestScore = -1e9;
		const foes = side.foe.active.filter((p) => p && !p.fainted);
		req.side.pokemon.forEach((p, i) => {
			const mon = side.pokemon.find((x) => x.fullname === p.ident || x.name === p.ident.slice(4));
			if (p.active || p.condition.endsWith(' fnt')) return;
			const m = side.pokemon[i];
			let s = m.hp / m.maxhp * 30;
			for (const foe of foes) {
				for (const mv of m.moveSlots) s = Math.max(s, s + 0);
				let off = 0;
				for (const slot of m.moveSlots) off = Math.max(off, estimate(m, foe, dex.moves.get(slot.id)));
				let def = 0;
				for (const t of foe.types) def = Math.max(def, dex.getEffectiveness(t, m) + (dex.getImmunity(t, m) ? 0 : -9));
				s += Math.min(off, 100) - def * 25;
			}
			if (s > bestScore) {
				bestScore = s;
				best = i + 1;
			}
		});
		return best;
	}

	function chooseMove(battle, side, slot, req, taken) {
		const user = side.active[slot];
		const r = req.active[slot];
		if (!r) return 'pass';
		const foes = side.foe.active.filter((p) => p && !p.fainted && p.hp > 0);
		if (!foes.length) return 'default';
		const doubles = side.active.length > 1;
		let best = null, bestScore = -1;
		r.moves.forEach((m, i) => {
			if (m.disabled || m.pp === 0) return;
			const move = dex.moves.get(m.id);
			if (move.category === 'Status') {
				const score = statusScore(user, foes, side, move);
				if (score > bestScore) {
					bestScore = score;
					best = {i: i + 1, target: move.target === 'normal' ? 1 : 0};
				}
				return;
			}
			foes.forEach((foe) => {
				const pos = side.foe.active.indexOf(foe) + 1;
				let d = estimate(user, foe, move);
				const hpLeft = foe.hp / foe.maxhp * 100;
				let score = Math.min(d, hpLeft) + (d >= hpLeft ? 40 : 0);
				if (move.priority > 0 && d >= hpLeft) score += 30;
				if (move.selfdestruct) score *= 0.5;
				if (move.flags.recharge || move.self?.volatileStatus === 'mustrecharge') score *= 0.6;
				const spread = ['allAdjacent', 'allAdjacentFoes'].includes(move.target);
				if (doubles && spread) score *= 1.2;
				if (score > bestScore) {
					bestScore = score;
					best = {i: i + 1, target: doubles && !spread && ['normal', 'any', 'adjacentFoe'].includes(move.target) ? pos : 0};
				}
			});
		});
		if (!best) return 'default';
		// Switch out of hopeless matchups now and then.
		const benchOk = !r.trapped && side.pokemon.some((p, i) => !p.isActive && !p.fainted && !taken.has(i + 1));
		if (!doubles && benchOk && bestScore < 18 && battle.prng.random() < 0.7) {
			const sw = bestSwitch(side, req);
			if (sw > 0 && !taken.has(sw)) {
				taken.add(sw);
				return 'switch ' + sw;
			}
		}
		let choice = 'move ' + best.i;
		if (best.target) choice += ' ' + best.target;
		if (r.canMegaEvo || r.canMegaEvoX) choice += r.canMegaEvoX ? ' megax' : ' mega';
		else if (r.canUltraBurst) choice += ' ultra';
		else if (r.canZMove && r.canZMove[best.i - 1] && bestScore > 25) choice += ' zmove';
		return choice;
	}

	function act(battle, side) {
		const req = side.activeRequest;
		if (!req || req.wait) return;
		if (req.teamPreview) return battle.choose(side.id, 'default');
		if (req.forceSwitch) {
			const taken = new Set();
			const parts = req.forceSwitch.map((f, i) => {
				if (!f) return 'pass';
				const sw = bestSwitch(side, req);
				if (sw < 0 || taken.has(sw)) {
					const alt = side.pokemon.findIndex((p, j) => !p.isActive && !p.fainted && !taken.has(j + 1));
					if (alt < 0) return 'pass';
					taken.add(alt + 1);
					return 'switch ' + (alt + 1);
				}
				taken.add(sw);
				return 'switch ' + sw;
			});
			if (!battle.choose(side.id, parts.join(', '))) battle.choose(side.id, 'default');
			return;
		}
		const taken = new Set();
		const parts = req.active.map((_, i) => chooseMove(battle, side, i, req, taken));
		if (!battle.choose(side.id, parts.join(', '))) {
			battle.undoChoice?.(side.id);
			battle.choose(side.id, 'default');
		}
	}

	const toSet = (s, level) => ({name: s.name, species: s.form !== s.species && false ? s.form : s.name, item: s.item, ability: s.ability, moves: s.moves, nature: s.nature,
		evs: Object.fromEntries(STATS.map((k, i) => [k, s.nuzlocke ? 0 : s.evs[i]])), ivs: {hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31}, level: 100, gender: ''});

	function play(formatid, a, b, seed) {
		const battle = new Battle({formatid, seed: [seed & 0xFFFF, (seed >>> 16) & 0xFFFF, 7, 11], p1: {name: 'A', team: a}, p2: {name: 'B', team: b}});
		let guard = 0;
		while (!battle.ended && guard++ < 700 && battle.turn < 120) {
			const before = battle.turn;
			for (const side of battle.sides) act(battle, side);
			if (battle.requestState === '' ) break;
		}
		return battle.ended ? (battle.winner === 'A' ? 1 : battle.winner === 'B' ? 2 : 0) : 0;
	}

	function run({pool, sets, appearances, seed, teamSize}) {
		const rng = makeRng(seed);
		const doubles = /D(OU|Uber|AG)$/.test(pool);
		const formatid = doubles ? 'gen9nationaldexdoublesubers' : 'gen9nationaldexag';
		const stats = sets.map(() => [0, 0]);
		const need = sets.length * appearances;
		let done = 0, errs = 0, battles = 0;
		const start = Date.now();
		const order = () => {
			const o = sets.map((_, i) => i);
			for (let i = o.length - 1; i > 0; i--) {
				const j = Math.floor(rng() * (i + 1));
				[o[i], o[j]] = [o[j], o[i]];
			}
			return o;
		};
		let q = order(), p = 0;
		const nextSet = (used) => {
			for (let tries = 0; tries < 50; tries++) {
				if (p >= q.length) {
					q = order();
					p = 0;
				}
				const i = q[p++];
				if (!used.has(sets[i].species)) return i;
			}
			return q[0];
		};
		while (done < need) {
			const usedA = new Set(), usedB = new Set(), A = [], B = [];
			for (let k = 0; k < teamSize; k++) {
				const a = nextSet(usedA); usedA.add(sets[a].species); A.push(a);
				const b = nextSet(usedB); usedB.add(sets[b].species); B.push(b);
			}
			done += teamSize * 2;
			let w;
			try {
				w = play(formatid, A.map((i) => toSet(sets[i])), B.map((i) => toSet(sets[i])), Math.floor(rng() * 4e9));
			} catch (e) {
				errs++;
				if (errs < 2) console.error(pool, e.stack);
				continue;
			}
			battles++;
			if (w === 0) continue;
			for (const i of A) { stats[i][0]++; if (w === 1) stats[i][1]++; }
			for (const i of B) { stats[i][0]++; if (w === 2) stats[i][1]++; }
		}
		return {pool, stats, battles, errs, ms: Date.now() - start};
	}
	parentPort.on('message', (job) => parentPort.postMessage(run(job)));
}

if (!isMainThread) {
	workerMain();
	return;
}

(async () => {
	const appearances = +(process.argv[2] || 30);
	const filter = new RegExp(process.argv[3] || '.');
	const inDir = path.join(ROOT, process.argv[4] || 'cand');
	const outDir = path.join(ROOT, process.argv[5] || 'sim');
	fs.mkdirSync(outDir, {recursive: true});
	const files = fs.readdirSync(inDir).filter((f) => f.endsWith('.json') && !f.startsWith('_') && filter.test(f));
	const queue = [];
	for (const f of files) {
		const pool = f.replace('.json', '');
		const sets = JSON.parse(fs.readFileSync(path.join(inDir, f), 'utf8'));
		if (sets.length < 6 || new Set(sets.map((s) => s.species)).size < 7) {
			fs.writeFileSync(path.join(outDir, pool + '.json'), JSON.stringify({pool, stats: sets.map(() => [0, 0]), battles: 0, skipped: true}));
			continue;
		}
		const doubles = /D(OU|Uber)$/.test(pool);
		// Split big pools into chunks so all workers share them.
		const chunk = 2500;
		for (let i = 0; i < sets.length; i += chunk) queue.push({pool, offset: i, sets: sets.slice(i, i + chunk).length >= 40 ? sets.slice(i, i + chunk) : sets.slice(Math.max(0, i + chunk - 200), i + chunk), appearances, seed: (i + 1) * 104729 + pool.length * 7, teamSize: doubles ? 4 : 3});
	}
	queue.sort((a, b) => a.pool.localeCompare(b.pool));
	console.log('jobs', queue.length, 'sets', queue.reduce((a, j) => a + j.sets.length, 0));
	const results = {};
	let total = 0, errs = 0, finished = 0;
	const t0 = Date.now();
	const n = Math.min(9, Math.floor(os.cpus().length * 0.4));
	os.setPriority(os.constants.priority.PRIORITY_BELOW_NORMAL);
	await Promise.all(Array.from({length: n}, () => new Promise((res) => {
		const w = new Worker(__filename);
		const next = () => {
			if (!queue.length) {
				w.terminate();
				res();
				return;
			}
			const j = queue.shift();
			w.current = j;
			w.postMessage(j);
		};
		w.on('message', (r) => {
			const j = w.current;
			(results[r.pool] = results[r.pool] || []).push({offset: j.offset, stats: r.stats});
			total += r.battles;
			errs += r.errs;
			finished++;
			if (finished % 10 === 0) console.log(finished, 'done', total, 'battles', errs, 'errors', ((Date.now() - t0) / 1000).toFixed(0) + 's');
			next();
		});
		w.on('error', (e) => {
			console.error('worker error', e.message);
			next();
		});
		next();
	})));
	for (const [pool, parts] of Object.entries(results)) {
		const sets = JSON.parse(fs.readFileSync(path.join(inDir, pool + '.json'), 'utf8'));
		const stats = sets.map(() => [0, 0]);
		for (const part of parts) part.stats.forEach((s, i) => {
			if (part.offset + i < stats.length) {
				stats[part.offset + i][0] += s[0];
				stats[part.offset + i][1] += s[1];
			}
		});
		fs.writeFileSync(path.join(outDir, pool + '.json'), JSON.stringify({pool, stats}));
	}
	console.log('finished', total, 'battles', errs, 'errors', ((Date.now() - t0) / 1000).toFixed(0) + 's');
})();
