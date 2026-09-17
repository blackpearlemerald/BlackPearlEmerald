// Runs the website Save Converter in Node for BPETools/tests/test_bpe_save_format.py.
//   node BPETools/tests/save_converter_cli.cjs <input> <output> <gameId>
// Prints a JSON report, or {"error": message}.
const fs = require('node:fs');
const converter = require('../../BPEDocumentation/site/js/save-converter.js');

const [input, output, gameId] = process.argv.slice(2);
try {
  const result = converter.convertSaveFile(new Uint8Array(fs.readFileSync(input)), { gameId: Number(gameId) });
  fs.writeFileSync(output, result.bytes);
  console.log(JSON.stringify(result.report));
} catch (error) {
  console.log(JSON.stringify({ error: error.message }));
}
