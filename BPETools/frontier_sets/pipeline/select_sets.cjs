// Uses battle results to keep good sets. Usage: node select_sets.cjs <inDir> <simDir> <outDir> <final 0|1>
const fs = require('fs');
const path = require('path');

const ROOT = __dirname;
const [inDir, simDir, outDir, finalFlag] = process.argv.slice(2);
const final = finalFlag === '1';
fs.rmSync(path.join(ROOT, outDir), {recursive: true, force: true});
fs.mkdirSync(path.join(ROOT, outDir), {recursive: true});
const median = (a) => {
	const b = a.slice().sort((x, y) => x - y);
	return b.length ? b[Math.floor(b.length / 2)] : 0;
};
const summary = {};
for (const f of fs.readdirSync(path.join(ROOT, inDir))) {
	if (!f.endsWith('.json') || f.startsWith('_')) continue;
	const pool = f.replace('.json', '');
	const sets = JSON.parse(fs.readFileSync(path.join(ROOT, inDir, f), 'utf8'));
	const sim = JSON.parse(fs.readFileSync(path.join(ROOT, simDir, f), 'utf8'));
	sets.forEach((s, i) => {
		const [g, w] = sim.stats[i] || [0, 0];
		s.games = (s.games || 0) + g;
		s.wins = (s.wins || 0) + w;
		s.wr = s.games ? s.wins / s.games : 0;
	});
	if (sim.skipped) {
		fs.writeFileSync(path.join(ROOT, outDir, f), JSON.stringify(sets));
		summary[pool] = {sets: sets.length, pokemon: new Set(sets.map((s) => s.form)).size, tested: false};
		continue;
	}
	const med = median(sets.map((s) => s.wr));
	const byForm = {};
	for (const s of sets) (byForm[s.form] = byForm[s.form] || []).push(s);
	const keep = [];
	for (const list of Object.values(byForm)) {
		list.sort((a, b) => b.wr - a.wr);
		const best = list[0].wr;
		const floor = med - (final ? 0.1 : 0.14);
		const near = final ? 0.06 : 0.09;
		let kept = list.filter((s) => s.wr >= floor && s.wr >= best - near && (s.grade !== 'C' || s.wr >= med - 0.02));
		if (!kept.length && list[0].wr >= med - 0.16) kept = [list[0]];
		if (final) {
			// Keep the strongest sets, with fewer near-copies of one idea.
			const out = [];
			for (const s of kept.sort((a, b) => (b.wr + (b.grade === 'A' ? 0.02 : 0)) - (a.wr + (a.grade === 'A' ? 0.02 : 0)))) {
				if (out.length >= 8) break;
				const close = out.some((o) => o.item === s.item && o.moves.filter((m) => s.moves.includes(m)).length >= 3);
				if (close && out.length >= 3) continue;
				out.push(s);
			}
			kept = out;
		}
		keep.push(...kept);
	}
	fs.writeFileSync(path.join(ROOT, outDir, f), JSON.stringify(keep));
	summary[pool] = {sets: keep.length, pokemon: new Set(keep.map((s) => s.form)).size, from: sets.length, median: +med.toFixed(3)};
}
fs.writeFileSync(path.join(ROOT, outDir, '_summary.json'), JSON.stringify(summary, null, 1));
console.log(Object.entries(summary).map(([k, v]) => `${k}: ${v.sets} sets, ${v.pokemon} mons (from ${v.from ?? 'n/a'})`).join('\n'));
