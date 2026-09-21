// Runs the website's save reading in Node for BPETools/tests/test_calc_save_import.py.
//   node BPETools/tests/save_reader_cli.cjs <save> [calc data .json]
// Prints {"format", "loadFlags", "pokemon"} from save-converter.js, plus the
// calculator import ("sets", "party", "counts", ...) when calc data is given.
// Prints {"error": message} when the save cannot be read.
const fs = require('node:fs');
const reader = require('../../BPEDocumentation/site/js/save-converter.js');
const saveImport = require('../../BPEDocumentation/site/js/calc_save_import.js');

const [input, calcDataPath] = process.argv.slice(2);
try {
  const save = reader.readSaveFile(new Uint8Array(fs.readFileSync(input)));
  const output = { format: save.format, loadFlags: save.loadFlags, pokemon: save.pokemon };
  if (calcDataPath) {
    const calcData = JSON.parse(fs.readFileSync(calcDataPath, 'utf8'));
    Object.assign(output, saveImport.buildSets(save, calcData, reader, null));
  }
  console.log(JSON.stringify(output));
} catch (error) {
  console.log(JSON.stringify({ error: error.message }));
}
