// The AG tier's own Pokemon were left out of the first battle tests. This tests them against Ubers.
const fs = require('fs');
const path = require('path');
const ROOT = __dirname;
const load = (d, f) => JSON.parse(fs.readFileSync(path.join(ROOT, d, f + '.json'), 'utf8'));
const ubers = load('final', 'nd-Ubers');
const seen = new Set(), mix = [...ubers];
for (const g of ['4', '8', '9', 'nd']) for (const s of load('cand', g + '-AG')) {
	const k = [s.form, s.item, s.ability, s.moves.slice().sort().join()].join('|');
	if (seen.has(k)) continue;
	seen.add(k);
	mix.push({...s, poolGen: g});
}
fs.mkdirSync(path.join(ROOT, 'ag_in'), {recursive: true});
fs.writeFileSync(path.join(ROOT, 'ag_in', 'nd-AGmix.json'), JSON.stringify(mix));
console.log(ubers.length, 'ubers', mix.length - ubers.length, 'AG sets');
