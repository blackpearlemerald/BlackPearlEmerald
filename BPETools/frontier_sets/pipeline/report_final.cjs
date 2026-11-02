// Final coverage by pool, with Anything Goes built from each generation's pools. Writes final/_report.json.
const fs = require('fs');
const path = require('path');
const ROOT = __dirname;
const {Dex} = require(path.join(ROOT, 'showdown', 'dist', 'sim', 'index.js'));
const bucket = (t) => {
	if (!t) return null;
	t = t.replace(/[()]/g, '');
	if (t === 'AG') return 'AG';
	if (t === 'Uber') return 'Ubers';
	if (t === 'OU' || t === 'UUBL') return 'OU';
	if (t === 'UU' || t === 'RUBL') return 'UU';
	if (['RU', 'NUBL', 'NU', 'PUBL', 'PU', 'ZUBL', 'ZU'].includes(t)) return 'RU';
	return null;
};
const gens = ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'nd'];
const load = (n) => {
	const p = path.join(ROOT, 'final', n + '.json');
	return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf8')) : [];
};
const rep = {};
let totalSets = 0, unique = new Set();
for (const g of gens) {
	const dex = g === 'nd' || g === '9' ? Dex.mod('gen9') : Dex.mod('gen' + g);
	const members = {};
	for (const s of dex.species.all()) {
		if (!s.exists || s.isNonstandard === 'CAP' || s.isNonstandard === 'Custom' || s.isNonstandard === 'Future' || s.isNonstandard === 'LGPE') continue;
		const b = bucket(g === 'nd' ? (s.natDexTier || s.tier) : s.tier);
		if (b) (members[b] = members[b] || new Set()).add(s.id);
	}
	rep[g] = {};
	const ag = [];
	for (const t of ['Ubers', 'OU', 'UU', 'RU']) {
		const sets = load(`${g}-${t}`);
		ag.push(...sets);
		const forms = new Set(sets.map((s) => s.form));
		const tested = sets.filter((s) => s.games > 0);
		const list = [...(members[t] || [])];
		const miss = list.filter((k) => !forms.has(k) && ![...forms].some((f) => f.startsWith(k)));
		rep[g][t] = {sets: sets.length, pokemon: forms.size, tier: list.length, missing: miss.length, missingList: miss.slice(0, 200), tested: tested.length, A: sets.filter((s) => s.grade === 'A').length, B: sets.filter((s) => s.grade === 'B').length, C: sets.filter((s) => s.grade === 'C').length, learnable: sets.filter((s) => s.strict).length};
	}
	rep[g].AG = {sets: ag.length, pokemon: new Set(ag.map((s) => s.form)).size};
	const dou = load(`${g}-DOU`), dub = load(`${g}-DUber`);
	rep[g].DOU = {sets: dou.length, pokemon: new Set(dou.map((s) => s.form)).size, native: dou.filter((s) => s.mode === 'd').length, megas: dou.filter((s) => s.form !== s.species).length};
	rep[g].DUber = {sets: dub.length, pokemon: new Set(dub.map((s) => s.form)).size, native: dub.filter((s) => s.mode === 'd').length, megas: dub.filter((s) => s.form !== s.species).length};
	for (const s of [...ag, ...dou, ...dub]) {
		totalSets++;
		unique.add([s.form, s.item, s.ability, s.nature, s.evs.join(), s.moves.slice().sort().join()].join('|'));
	}
}
fs.writeFileSync(path.join(ROOT, 'final', '_report.json'), JSON.stringify(rep, null, 1));
for (const g of gens) {
	const r = rep[g];
	console.log(g.padEnd(3), ['Ubers', 'OU', 'UU', 'RU'].map((t) => `${t} ${r[t].sets}s ${r[t].tier - r[t].missing}/${r[t].tier}`).join(' | '), `| AG ${r.AG.sets}s ${r.AG.pokemon}p | DOU ${r.DOU.sets}s ${r.DOU.pokemon}p (${r.DOU.native} native) | DUber ${r.DUber.sets}s ${r.DUber.pokemon}p (${r.DUber.native} native)`);
}
console.log('entries', totalSets, 'unique sets', unique.size, 'ROM at 40 bytes', Math.round(unique.size * 40 / 1024) + ' KB');
const nd = load('nd-OU').concat(load('nd-UU'), load('nd-RU'), load('nd-Ubers'));
console.log('grades nd singles', nd.reduce((a, s) => (a[s.grade] = (a[s.grade] || 0) + 1, a), {}), 'learnable', nd.filter((s) => s.strict).length, 'of', nd.length);
const all = gens.flatMap((g) => ['Ubers', 'OU', 'UU', 'RU', 'DOU', 'DUber'].flatMap((t) => load(`${g}-${t}`)));
console.log('all grades', all.reduce((a, s) => (a[s.grade] = (a[s.grade] || 0) + 1, a), {}), 'not learnable', all.filter((s) => !s.strict).length);
const top = load('nd-OU').sort((a, b) => b.wr - a.wr).slice(0, 5).concat(load('nd-OU').sort((a, b) => a.wr - b.wr).slice(0, 3));
for (const s of top) console.log(s.wr.toFixed(3), s.games, s.grade, s.form, '@', s.item, '/', s.ability, '/', s.nature, '/', s.evs.join('-'), '/', s.moves.join(', '), '/', s.source);
console.log('nd-RU missing sample', rep.nd.RU.missingList.slice(0, 50).join(' '));
console.log('nd Ubers missing', rep.nd.Ubers.missingList.join(' '), '| UU', rep.nd.UU.missingList.join(' '), '| OU', rep.nd.OU.missingList.join(' '));
