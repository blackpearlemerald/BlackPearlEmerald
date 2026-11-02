// Drops sets that make no sense before battle testing, and caps filler sets per Pokemon. Writes cand2/.
const fs = require('fs');
const path = require('path');

const ROOT = __dirname;
const bpe = JSON.parse(fs.readFileSync(path.join(ROOT, 'bpe_data.json'), 'utf8'));
const hp = (m) => m.replace(/^hiddenpower.*/, 'hiddenpower');
const info = (m) => bpe.moves[hp(m)] || {cat: 'STATUS', type: '', power: 0};
const ORB = {flameorb: ['guts', 'flareboost', 'marvelscale', 'quickfeet', 'magicguard', 'toxicboost'], toxicorb: ['poisonheal', 'toxicboost', 'guts', 'marvelscale', 'quickfeet', 'magicguard']};
const ROCK = {heatrock: ['sunnyday', 'drought', 'orichalcumpulse'], damprock: ['raindance', 'drizzle'], smoothrock: ['sandstorm', 'sandstream', 'sandspit'], icyrock: ['hail', 'snowscape', 'snowwarning', 'chillyreception']};
const LOCKED = {lightball: ['pikachu'], thickclub: ['cubone', 'marowak'], leek: ['farfetchd', 'sirfetchd'], luckypunch: ['chansey'], souldew: ['latias', 'latios'], adamantorb: ['dialga'], lustrousorb: ['palkia'], griseousorb: ['giratina'], griseouscore: ['giratina'], adamantcrystal: ['dialga'], lustrousglobe: ['palkia']};

function problem(s) {
	const m = s.moves, it = s.item, ab = s.ability, ev = s.evs;
	if (new Set(m).size !== 4) return 'moves';
	const cats = m.map(info);
	const attacks = cats.filter((c) => c.cat !== 'STATUS');
	const has = (...x) => x.some((y) => m.includes(y));
	if (ev.reduce((a, b) => a + b, 0) > 510 || Math.max(...ev) > 255) return 'evs';
	if (!attacks.length && s.grade !== 'A') return 'no attacks';
	if (s.grade === 'A' && !s.evidence.raw) {
		// Showdown's own sets are trusted here; the battle tests judge them.
		if (ORB[it] && !ORB[it].includes(ab) && !has('trick', 'switcheroo', 'fling', 'facade', 'psychoshift')) return 'orb with no use';
		return null;
	}
	if (ev[1] >= 128 && !cats.some((c) => c.cat === 'PHYSICAL' && (c.power >= 50 || c.power <= 1)) && !has('foulplay')) return 'attack EVs unused';
	if (ev[3] >= 128 && !cats.some((c) => c.cat === 'SPECIAL' && (c.power >= 50 || c.power <= 1))) return 'special EVs unused';
	if (['choiceband', 'choicespecs', 'choicescarf', 'assaultvest'].includes(it) && m.some((x) => info(x).cat === 'STATUS' && !['trick', 'switcheroo'].includes(x))) return 'choice or vest with status';
	if (it === 'choicescarf' && ev[5] === 0) return 'scarf with no speed';
	if (it === 'lifeorb' && attacks.length < 2) return 'life orb on support';
	if (it === 'focussash' && ev[0] >= 100) return 'focus sash on bulky set';
	if (ORB[it] && !ORB[it].includes(ab) && !has('trick', 'switcheroo', 'fling', 'facade', 'psychoshift')) return 'orb with no use';
	if (ROCK[it] && !ROCK[it].some((x) => m.includes(x) || x === ab)) return 'weather rock with no weather';
	if (it === 'lightclay' && !has('reflect', 'lightscreen', 'auroraveil')) return 'light clay with no screens';
	if (LOCKED[it] && !LOCKED[it].some((x) => s.species.startsWith(x))) return 'item for another Pokemon';
	if (it === 'blacksludge' && !has('trick', 'switcheroo') && false) return 'sludge';
	if (m.includes('trickroom') && ev[5] >= 100) return 'trick room with speed';
	if (['modest', 'timid', 'bold', 'calm'].includes(s.nature) && cats.some((c) => c.cat === 'PHYSICAL' && c.power >= 60) && !has('foulplay', 'bodypress')) return 'nature lowers its attack';
	if (['adamant', 'jolly', 'impish', 'careful'].includes(s.nature) && cats.some((c) => c.cat === 'SPECIAL' && c.power >= 60)) return 'nature lowers its attack';
	if (m.includes('facade') && !ORB[it] && ab !== 'guts') return 'facade with no status';
	const setups = m.filter((x) => ['swordsdance', 'dragondance', 'bulkup', 'nastyplot', 'calmmind', 'quiverdance', 'irondefense', 'amnesia', 'cosmicpower', 'coil', 'curse', 'shiftgear'].includes(x));
	if (setups.length > 1 && !has('storedpower', 'bodypress')) return 'two setup moves';
	if (setups.length && m.includes('trickroom')) return 'setup with trick room';
	if (has('swordsdance', 'dragondance', 'bulkup') && !cats.some((c) => c.cat === 'PHYSICAL')) return 'physical setup with no physical moves';
	if (has('nastyplot', 'calmmind', 'quiverdance') && !cats.some((c) => c.cat === 'SPECIAL')) return 'special setup with no special moves';
	return null;
}

const inDir = path.join(ROOT, 'cand');
const outDir = path.join(ROOT, 'cand2');
fs.rmSync(outDir, {recursive: true, force: true});
fs.mkdirSync(outDir, {recursive: true});
const why = {};
const lines = [];
for (const f of fs.readdirSync(inDir)) {
	if (!f.endsWith('.json') || f.startsWith('_')) continue;
	const pool = f.replace('.json', '');
	if (/-AG$/.test(pool)) continue;
	const doubles = /D(OU|Uber)$/.test(pool);
	const sets = JSON.parse(fs.readFileSync(path.join(inDir, f), 'utf8'));
	const keep = [];
	const capC = {};
	// Native doubles sets first, so singles copies only fill gaps.
	sets.sort((a, b) => (a.grade + (a.mode === 'd' ? '0' : '1')).localeCompare(b.grade + (b.mode === 'd' ? '0' : '1')));
	for (const s of sets) {
		const p = problem(s);
		if (p) {
			why[p] = (why[p] || 0) + 1;
			continue;
		}
		if (s.grade === 'C') {
			capC[s.form] = (capC[s.form] || 0) + 1;
			if (capC[s.form] > (doubles ? 3 : 4)) continue;
		}
		keep.push(s);
	}
	fs.writeFileSync(path.join(outDir, f), JSON.stringify(keep));
	lines.push([pool, sets.length, keep.length]);
}
console.log(lines.map((l) => l.join(' ')).join('\n'));
console.log('total kept', lines.reduce((a, l) => a + l[2], 0));
console.log(Object.entries(why).sort((a, b) => b[1] - a[1]));
