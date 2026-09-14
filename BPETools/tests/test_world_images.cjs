const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

// A small Leaflet/DOM adapter exercises layer lifetime and geometry without
// substituting browser performance measurements for a real rendering engine.
function element() {
  return {width:0,height:0,style:{},setAttribute(){},getContext(){return this.ctx ||= {calls:[],clearRect(){this.calls=[];},drawImage(...args){this.calls.push(args);}};}, children:[], appendChild(child){ this.children.push(child);child.parent=this; },
    remove(){ if(this.parent)this.parent.children=this.parent.children.filter(c=>c!==this); },
    getAttribute(key){ return this[key]; }};
}
const raf = new Map();let nextFrame=0;
const pane=element();
let bounds={x0:-200,y0:-200,x1:200,y1:200};
function leafBounds(b) { return {getWest:()=>b.x0,getEast:()=>b.x1,getNorth:()=>-b.y0,getSouth:()=>-b.y1,
  pad(r){const dx=(b.x1-b.x0)*r,dy=(b.y1-b.y0)*r;return leafBounds({x0:b.x0-dx,x1:b.x1+dx,y0:b.y0-dy,y1:b.y1+dy});}}; }
const L={Layer:{extend(spec){ function Layer(...args){this.options={};spec.initialize?.apply(this,args);} Object.assign(Layer.prototype,spec);return Layer;}},
  setOptions(obj,options){Object.assign(obj.options,options);},latLngBounds:b=>b,
  DomUtil:{create:()=>element(),setPosition(el,point){el.position=point;}}};
const scope={L,window:{addEventListener(){},removeEventListener(){}},AbortController,document:{hidden:false,addEventListener(){},removeEventListener(){},createElement:()=>element()},performance,requestAnimationFrame:cb=>{const id=++nextFrame;raf.set(id,cb);return id;},cancelAnimationFrame:id=>raf.delete(id)};
vm.runInNewContext(fs.readFileSync('BPEDocumentation/site/js/world-images.js','utf8'),scope);
const api=scope.window.BPEWorldImages;
const index=new api.WorldIndex(64), records=[];
// Include negative coordinates, boundary contacts, and rectangles spanning cells.
for(let i=0;i<300;i++){const x=(i*73%1600)-800,y=(i*197%1600)-800;const record={id:i,box:{x0:x,y0:y,x1:x+5+i%150,y1:y+16+i%200}};records.push(record);index.add(record);}
for(let n=0;n<100;n++){const x=n*31%1500-750,y=n*67%1500-750,b={x0:x,y0:y,x1:x+175,y1:y+203};
  const actual=Array.from(index.query(b),r=>r.id).sort((a,b)=>a-b);
  const expected=records.filter(r=>r.box.x0<=b.x1&&r.box.x1>=b.x0&&r.box.y0<=b.y1&&r.box.y1>=b.y0).map(r=>r.id).sort((a,b)=>a-b);
  assert.deepEqual(actual,expected);
}
index.remove(records[0]);assert.ok(!index.query({x0:-1000,y0:-1000,x1:1000,y1:1000}).includes(records[0]));
records[0].box={x0:0,y0:0,x1:16,y1:32};index.add(records[0]);
assert.ok(index.query({x0:16,y0:32,x1:20,y1:35}).includes(records[0]));

async function run() {
  const closed=[];
  const bitmap=(url,width=16,height=32)=>({width,height,close(){closed.push(url);}});
  const request=(url,width=16,height=32)=>({url,width,height});
  const next=async()=>{for(let n=0;n<8;n++)await Promise.resolve();};
  // Loading, canceled decoding and ready images share the same hard budget.
  const loads=[];
  const cache=new api.ImageCache(4096,()=>{},(url,signal)=>new Promise(resolve=>loads.push({url,signal,resolve})));
  cache.select([request('a'),request('b'),request('c'),request('too-large',64,64)]);
  assert.equal(cache.bytes,4096);assert.equal(loads.length,2);assert.equal(cache.active,2);
  cache.select([request('c'),request('d')]);
  assert.ok(loads[0].signal.aborted);assert.equal(loads.length,2,'obsolete decodes still occupy the budget');
  loads[0].resolve(bitmap('a'));await next();
  assert.ok(closed.includes('a'));assert.equal(loads.length,3);assert.equal(cache.activeBytes,4096);
  loads[1].resolve(bitmap('b'));await next();
  loads[2].resolve(bitmap('c'));loads[3].resolve(bitmap('d'));await next();
  assert.equal(cache.active,0);assert.ok(cache.get('c'));assert.ok(cache.get('d'));
  cache.select([request('d'),request('d')]);assert.equal(cache.bytes,2048);assert.ok(closed.includes('c'));
  cache.clear();assert.equal(cache.bytes,0);assert.ok(closed.includes('d'));
  const failed=new api.ImageCache(4096,()=>{},async()=>{throw new Error('offline');});
  failed.select([request('missing')]);await next();failed.select([request('missing')]);
  assert.equal(failed.entries.get('missing').state,'failed');assert.equal(failed.active,0);
  const wrong=new api.ImageCache(4096,()=>{},async()=>bitmap('wrong',32,32));
  wrong.select([request('wrong')]);await next();assert.ok(closed.includes('wrong'));assert.equal(wrong.get('wrong'),undefined);
  // Retina, large desktop windows and zoom never enlarge the backing surface.
  for(const [w,h] of [[390,747],[844,273],[7680,4320],[100000,100000]]) {
    const surface=api.surfaceSize(w,h);
    assert.ok(surface.width<=2048&&surface.height<=2048&&surface.width*surface.height<=2097152);
  }
  assert.equal(api.surfaceSize(390,747).width,390);
  for(const zoom of [-6,-3.125,0,4]) {
    const extent=390/2**zoom, view={x0:-100,y0:-50,x1:-100+extent,y1:-50+extent};
    const args=api.crop(bitmap('world',1074,1208),{x0:-1200,y0:-1248,x1:15984,y1:18080},view,390,747);
    assert.ok(args[4]>=0&&args[5]>=0&&args[4]+args[6]<=390.00001&&args[5]+args[7]<=747.00001);
  }
  assert.equal(api.crop(bitmap('offscreen'),{x0:1000,y0:1000,x1:1016,y1:1032},bounds,390,747),null);
  assert.deepEqual(Array.from(api.crop(bitmap('negative',16,32),{x0:-16,y0:-32,x1:0,y1:0},
    {x0:-8,y0:-16,x1:8,y1:16},160,320)),[8,16,8,16,0,0,80,160]);

  let position={x:0,y:0};
  const map={getPane:()=>pane,getZoom:()=>-1,getSize:()=>({x:390,y:747}),
    containerPointToLayerPoint:()=>position,getBounds:()=>leafBounds(bounds)};
  async function drain(){for(let n=0;n<20;n++){await next();const batch=Array.from(raf);raf.clear();for(const[,cb]of batch)cb();}assert.equal(raf.size,0);}
  const renderer=api.renderer();renderer._map=map;renderer.onAdd(map);
  renderer.cache.loader=async url=>bitmap(url);
  const near=api.image('near',leafBounds({x0:-16,y0:-32,x1:0,y1:0}),renderer,{});
  const far=api.image('far',leafBounds({x0:2000,y0:2000,x1:2016,y1:2032}),renderer,{});
  renderer.addImage(near);renderer.addImage(far);await drain();
  assert.equal(renderer.drawn,1);assert.equal(renderer.root.width,390);assert.equal(renderer.root.height,747);
  assert.equal(renderer.root.children.length,0,'no world-sized image elements');
  const root=renderer.root;
  bounds={x0:-10,y0:-10,x1:10,y1:10};map.getZoom=()=>4;renderer.redraw();
  assert.equal(renderer.root,root);assert.equal(root.width,390);assert.equal(root.style.transform,undefined);
  assert.equal(root.ctx.imageSmoothingEnabled,false);
  position={x:20,y:30};renderer.redraw();assert.equal(root.position,position,'pane rebasing must update even with unchanged world bounds');
  const order=near.order;renderer.removeImage(near);renderer.addImage(near);await drain();assert.equal(near.order,order);
  renderer.removeImage(near);await drain();assert.equal(renderer.drawn,0);assert.ok(closed.includes('near'));
  bounds={x0:1950,y0:1950,x1:2050,y1:2050};renderer.redraw();await drain();assert.equal(renderer.drawn,1);
  far._map=map;far.setUrl('changed');far.setBounds(leafBounds({x0:1980,y0:1980,x1:1996,y1:2012}));await drain();
  assert.ok(renderer.cache.get('changed'));assert.equal(renderer.cache.get('far'),undefined);
  scope.document.hidden=true;renderer.hidden();assert.equal(renderer.cache.bytes,0);assert.equal(root.width,1);
  scope.document.hidden=false;renderer.hidden();await drain();assert.equal(root.width,390);assert.equal(renderer.drawn,1);
  renderer.suspend();renderer.schedule();await drain();assert.equal(root.width,1);assert.equal(renderer.cache.bytes,0);
  renderer.resume();await drain();assert.equal(root.width,390);assert.equal(renderer.drawn,1);
  renderer.onRemove();await drain();assert.equal(root.width,1);assert.equal(pane.children.length,0);
  assert.equal(renderer.cache.bytes,0);

  // Missing overviews fall back to bounded native detail without an error loop.
  bounds={x0:-200,y0:-200,x1:200,y1:200};map.getZoom=()=>-5;
  const overview=api.renderer({url:'overview',bounds:leafBounds({x0:-1600,y0:-1600,x1:1600,y1:1600}),detailZoom:-4});
  overview._map=map;overview.onAdd(map);
  overview.cache.loader=async url=>url==='overview'?Promise.reject(new Error('offline')):bitmap(url);
  overview.addImage(api.image('detail',leafBounds({x0:0,y0:0,x1:16,y1:32}),overview,{}));await drain();
  assert.equal(overview.coarse,false);assert.equal(overview.drawn,1);assert.ok(overview.cache.bytes<=overview.budget);
  overview.onRemove();await drain();assert.equal(pane.children.length,0);
  scope.fetch=async url=>({ok:true,blob:async()=>url});
  scope.createImageBitmap=async url=>url==='overview-ok'?bitmap(url,200,200):bitmap(url);
  const valid=api.renderer({url:'overview-ok',bounds:leafBounds({x0:-1600,y0:-1600,x1:1600,y1:1600}),detailZoom:-4});
  valid._map=map;valid.onAdd(map);
  valid.addImage(api.image('native',leafBounds({x0:0,y0:0,x1:16,y1:32}),valid,{}));await drain();
  assert.equal(valid.coarse,true);assert.equal(valid.drawn,1);assert.equal(valid.cache.entries.size,1);
  map.getZoom=()=>-3;valid.redraw();await drain();assert.equal(valid.drawn,2);assert.ok(valid.cache.get('native'));
  map.getZoom=()=>-5;valid.redraw();await drain();assert.equal(valid.drawn,1);assert.ok(closed.includes('native'));
  valid.onRemove();await drain();assert.ok(closed.includes('overview-ok'));
  console.log('Passed spatial lookup, bounded decoding, canceled work, bitmap release, source cropping, screen-sized rendering, rebasing, toggles, geometry updates, background cleanup and fallback.');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
