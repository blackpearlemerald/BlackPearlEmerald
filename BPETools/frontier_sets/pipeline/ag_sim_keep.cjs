// Keeps up to three of the best tested sets for each AG-tier Pokemon, per generation.
const fs = require('fs');
const path = require('path');
const ROOT = __dirname;
const mix = JSON.parse(fs.readFileSync(path.join(ROOT, 'ag_in/nd-AGmix.json'), 'utf8'));
const sim = JSON.parse(fs.readFileSync(path.join(ROOT, 'ag_sim/nd-AGmix.json'), 'utf8'));
mix.forEach((s, i) => { s.games = sim.stats[i][0]; s.wins = sim.stats[i][1]; s.wr = s.games ? s.wins / s.games : 0; });
const ag = mix.filter((s) => s.poolGen);
const ub = mix.filter((s) => !s.poolGen).map((s) => s.wr).sort((a, b) => a - b);
const median = ub[ub.length >> 1];
const out = {};
for (const s of ag.sort((a, b) => b.wr - a.wr)) {
	const list = (out[s.poolGen] = out[s.poolGen] || []);
	if (s.wr < median - 0.05 || list.filter((x) => x.form === s.form).length >= 3) continue;
	list.push({...s, gen: s.poolGen, tier: 'AG'});
}
fs.mkdirSync(path.join(ROOT, 'final_ag'), {recursive: true});
for (const [g, l] of Object.entries(out)) {
	fs.writeFileSync(path.join(ROOT, 'final_ag', g + '-AG.json'), JSON.stringify(l));
	console.log(g, l.map((s) => `${s.form} ${s.wr.toFixed(2)} ${s.item}`).join(', '));
}
console.log('ubers median', median.toFixed(3));
