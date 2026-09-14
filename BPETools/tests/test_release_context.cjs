const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const script = fs.readFileSync('BPEDocumentation/site/js/release-context.js', 'utf8');
const storage = new Map();
function page(id, relative, responses={}, blocked=false) {
  const url = new URL(`https://example.test/BlackPearlEmerald/versions/${id}/${relative}`);
  const events=[];
  const win = {dispatchEvent: e=>events.push(e.type)};
  Object.defineProperty(win,'localStorage',{get(){if(blocked)throw Error('blocked');return {
    getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)
  };}});
  const scope={window:win, URL,URLSearchParams,Event,document:{currentScript:{src:`https://example.test/BlackPearlEmerald/versions/${id}/js/release-context.js`}}, location:{pathname:url.pathname,search:url.search,hash:url.hash,assign:u=>scope.destination=u},fetch:async target=>{
    const path=new URL(target).pathname;
    if(path.endsWith('/release.json'))return {ok:true,json:async()=>({version:id})};
    return responses[path]||{ok:true,status:200,json:async()=>({maps:[]})};
  }};
  vm.runInNewContext(script,scope);
  return {scope,context:win.BPERelease,storage:win.BPEStorage,events};
}
(async()=>{
  const to={version:'1.0.1',path:'versions/1.0.1/'};
  const current=page('2.0.0-beta','pokemon.html?id=BULBASAUR#moves');
  await current.context.ready;
  await current.context.switchTo(to);
  assert.equal(current.scope.destination,'https://example.test/BlackPearlEmerald/versions/1.0.1/pokemon.html?id=BULBASAUR#moves');
  assert.deepEqual(current.events,['bpe:versionchange']);
  const missing=page('2.0.0-beta','pokemon.html?id=NEW_MON',{'/BlackPearlEmerald/versions/1.0.1/data/species/NEW_MON.json':{ok:false,status:404}});
  await missing.context.switchTo(to);
  assert.ok(missing.scope.destination.endsWith('/pokedex.html?missing=NEW_MON'));
  const failed=page('2.0.0-beta','item.html?id=POTION',{'/BlackPearlEmerald/versions/1.0.1/data/items/POTION.json':{ok:false,status:503}});
  await assert.rejects(failed.context.switchTo(to));
  assert.equal(failed.scope.destination,undefined);
  const map=page('2.0.0-beta','index.html?map=MAP_NEW&item=ITEM_POTION');
  await map.context.switchTo(to);
  assert.ok(map.scope.destination.endsWith('/index.html?missing=MAP_NEW'));
  const old=page('1.0.1','calc/index.html'), newer=page('2.0.0-beta','calc/index.html');
  assert.equal(typeof old.storage.unsetPreference,'undefined');
  assert.equal(old.storage.getItem('unsetPreference'),null);
  old.storage.customSets='old team'; newer.storage.customSets='new team';
  assert.equal(old.storage.customSets,'old team');assert.equal(newer.storage.customSets,'new team');
  old.storage.themeIndex='2';assert.equal(newer.storage.themeIndex,'2');
  const privateMode=page('1.0.1','calc/index.html',{},true);
  privateMode.storage.setItem('customSets','memory only');assert.equal(privateMode.storage.customSets,'memory only');
  privateMode.context.remember('1.0.1');
  console.log('Passed version navigation, missing entities, failed downloads, state isolation and blocked storage checks.');
})().catch(e=>{console.error(e);process.exitCode=1});
