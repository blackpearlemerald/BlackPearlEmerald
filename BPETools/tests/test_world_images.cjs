const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

// A small Leaflet/DOM adapter exercises layer lifetime and geometry without
// substituting browser performance measurements for a real rendering engine.
function element() {
  return {style:{}, children:[], appendChild(child){ this.children.push(child);child.parent=this; },
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
  DomUtil:{create:()=>element(),setTransform(el,point,scale){el.transform={point,scale};}}};
const scope={L,window:{},document:{createElement:()=>element()},performance,requestAnimationFrame:cb=>{const id=++nextFrame;raf.set(id,cb);return id;},cancelAnimationFrame:id=>raf.delete(id)};
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

const map={options:{crs:{scale:z=>2**z}},getPane:()=>pane,getZoom:()=>-4,
  getZoomScale:(z,ref)=>2**(z-ref),latLngToLayerPoint:()=>({x:0,y:0}),getBounds:()=>leafBounds(bounds)};
function drain(){for(let i=0;raf.size&&i<100;i++){const batch=Array.from(raf);raf.clear();for(const [,cb]of batch)cb();}assert.equal(raf.size,0);}
const renderer=api.renderer();renderer._map=map;renderer.onAdd(map);
const near=api.image('near.png',leafBounds({x0:-16,y0:-32,x1:0,y1:0}),renderer,{});
const far=api.image('far.png',leafBounds({x0:2000,y0:2000,x1:2016,y1:2032}),renderer,{});
renderer.addImage(near);renderer.addImage(far);drain();
assert.equal(renderer.mounted.size,1);assert.equal(near.element.style.width,'16px');assert.equal(near.element.style.left,'-16px');
assert.equal(renderer.root.transform.scale,1/16);
const node=near.element,geometry=JSON.stringify(node.style);
map.getZoom=()=>2.125;renderer.transform();
assert.equal(near.element,node);assert.equal(JSON.stringify(node.style),geometry,'pinching must not resize or rewrite image geometry');
assert.equal(renderer.root.transform.scale,2**2.125);
const order=near.order;renderer.removeImage(near);renderer.addImage(near);drain();assert.equal(near.order,order);
renderer.removeImage(near);drain();assert.equal(renderer.mounted.size,0);
// A stale mount queue must not resurrect a toggled-off layer.
renderer.pending=[near];renderer.schedule();drain();assert.equal(near.element,null);
bounds={x0:1950,y0:1950,x1:2050,y1:2050};renderer.settle();drain();assert.equal(renderer.mounted.size,1);assert.ok(far.element);
renderer.removeImage(far);assert.equal(renderer.index.records.size,0);
renderer.onRemove();assert.equal(pane.children.length,0);assert.equal(raf.size,0);
// The overview covers distant zooms; detail is loaded only when useful and is
// restored if the overview image fails. Crossing back must cancel stale work.
bounds={x0:-200,y0:-200,x1:200,y1:200};map.getZoom=()=>-5;
const overviewRenderer=api.renderer({url:'overview.png',bounds:leafBounds(bounds),detailZoom:-4});
overviewRenderer._map=map;overviewRenderer.onAdd(map);
const detail=api.image('detail.png',leafBounds({x0:0,y0:0,x1:16,y1:32}),overviewRenderer,{});
overviewRenderer.addImage(detail);drain();assert.equal(overviewRenderer.mounted.size,0);
map.getZoom=()=>-3.5;overviewRenderer.checkCoverage();drain();assert.equal(overviewRenderer.mounted.size,1);
map.getZoom=()=>-4.5;overviewRenderer.checkCoverage();drain();assert.equal(overviewRenderer.mounted.size,0);
overviewRenderer.root.children[0].onerror();drain();assert.equal(overviewRenderer.mounted.size,1);
overviewRenderer.onRemove();assert.equal(pane.children.length,0);assert.equal(raf.size,0);
console.log('Passed spatial lookup, edge contacts, native pixel geometry, fractional zoom, stable order, viewport release, stale queues and cleanup.');
