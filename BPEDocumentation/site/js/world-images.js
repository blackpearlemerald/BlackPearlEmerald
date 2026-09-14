/* Screen-sized canvas layers: never ask the compositor to scale a world-sized
 * surface. Image decoding, retained pixels and canvas dimensions are bounded. */
(function () {
  'use strict';
  const MiB = 1024 * 1024;
  const intersects = (a, b) => a.x0 <= b.x1 && a.x1 >= b.x0 && a.y0 <= b.y1 && a.y1 >= b.y0;
  const contains = (a, b) => a.x0 <= b.x0 && a.x1 >= b.x1 && a.y0 <= b.y0 && a.y1 >= b.y1;
  const rect = bounds => ({x0: bounds.getWest(), x1: bounds.getEast(), y0: -bounds.getNorth(), y1: -bounds.getSouth()});

  class WorldIndex {
    constructor(size = 512) { this.size = size; this.cells = new Map(); this.records = new Set(); }
    keys(b) {
      const keys = [];
      for (let y = Math.floor(b.y0 / this.size); y <= Math.floor(b.y1 / this.size); y++) {
        for (let x = Math.floor(b.x0 / this.size); x <= Math.floor(b.x1 / this.size); x++) keys.push(x + ',' + y);
      }
      return keys;
    }
    add(record) {
      record.cells = this.keys(record.box); this.records.add(record);
      for (const key of record.cells) {
        if (!this.cells.has(key)) this.cells.set(key, new Set());
        this.cells.get(key).add(record);
      }
    }
    remove(record) {
      this.records.delete(record);
      for (const key of record.cells || []) {
        const cell = this.cells.get(key); cell.delete(record);
        if (!cell.size) this.cells.delete(key);
      }
    }
    query(box) {
      const count = (Math.ceil((box.x1 - box.x0) / this.size) + 2) * (Math.ceil((box.y1 - box.y0) / this.size) + 2);
      let candidates = this.records;
      if (count < this.cells.size) {
        candidates = new Set();
        for (const key of this.keys(box)) for (const record of this.cells.get(key) || []) candidates.add(record);
      }
      return Array.from(candidates).filter(record => intersects(record.box, box));
    }
  }

  function release(image) { if (image.close) image.close(); else image.src = ''; }
  async function loadImage(url, signal) {
    if (typeof createImageBitmap === 'function') {
      const response = await fetch(url, {signal});
      if (!response.ok) throw new Error('Map image unavailable');
      return createImageBitmap(await response.blob());
    }
    // Older Safari fallback still observes the same selection and decode budget.
    return new Promise((resolve, reject) => {
      const img = new Image();
      const aborted = () => { img.src = ''; done(new Error('Image load canceled')); };
      function done(error) {
        img.onload = img.onerror = null;
        signal.removeEventListener('abort', aborted);
        if (error) reject(error); else resolve(img);
      }
      img.decoding = 'async'; img.onload = () => done();
      img.onerror = () => done(new Error('Map image unavailable'));
      signal.addEventListener('abort', aborted, {once: true});
      if (signal.aborted) aborted(); else img.src = url;
    });
  }

  class ImageCache {
    constructor(limit, changed, loader = loadImage) {
      this.limit = limit; this.changed = changed; this.loader = loader;
      this.entries = new Map(); this.active = 0; this.activeBytes = 0; this.queue = []; this.bytes = 0;
    }
    select(requests) {
      const wanted = new Map(); let bytes = 0;
      for (const request of requests) {
        if (wanted.has(request.url)) continue;
        const cost = request.width * request.height * 4;
        if (cost <= 0 || bytes + cost > this.limit) continue;
        wanted.set(request.url, {...request, cost}); bytes += cost;
      }
      for (const [url, entry] of this.entries) {
        if (wanted.has(url)) continue;
        entry.controller.abort();
        if (entry.image) release(entry.image);
        this.entries.delete(url);
      }
      this.bytes = bytes; // Includes reservations for pending decodes.
      this.queue = [];
      for (const [url, request] of wanted) {
        let entry = this.entries.get(url);
        if (!entry) {
          entry = {...request, controller: new AbortController(), state: 'queued'};
          this.entries.set(url, entry);
        }
        if (entry.state === 'queued') this.queue.push(entry);
      }
      this.pump();
    }
    pump() {
      // Canceled decoding can still finish; count it until it settles.
      while (this.active < 2 && this.queue.length) {
        const readyBytes = Array.from(this.entries.values()).reduce((sum, e) => sum + (e.image ? e.cost : 0), 0);
        if (readyBytes + this.activeBytes + this.queue[0].cost > this.limit) return;
        const entry = this.queue.shift();
        if (this.entries.get(entry.url) !== entry) continue;
        entry.state = 'loading'; this.active++; this.activeBytes += entry.cost;
        this.loader(entry.url, entry.controller.signal).then(image => {
          if (this.entries.get(entry.url) !== entry || entry.controller.signal.aborted) { release(image); return; }
          if (image.width !== entry.width || image.height !== entry.height) {
            release(image); throw new Error('Map image dimensions changed');
          }
          entry.image = image; entry.state = 'ready'; this.changed();
        }).catch(() => {
          // Keep failed entries until selection changes; never retry each frame.
          if (this.entries.get(entry.url) === entry) { entry.state = 'failed'; this.changed(); }
        }).finally(() => { this.active--; this.activeBytes -= entry.cost; this.pump(); });
      }
    }
    get(url) { return this.entries.get(url)?.image; }
    clear() { this.select([]); }
  }

  function surfaceSize(width, height) {
    // Pixel art needs one backing pixel per CSS pixel. Retina density and giant
    // desktop windows must not multiply allocations beyond 2 megapixels.
    const scale = Math.min(1, 2048 / width, 2048 / height, Math.sqrt(2 * MiB / (width * height)));
    return {width: Math.max(1, Math.floor(width * scale)), height: Math.max(1, Math.floor(height * scale))};
  }
  // Crop in source coordinates first: even the overview's destination rectangle
  // is at most the canvas dimensions at the highest zoom level.
  function crop(image, box, view, width, height) {
    const x0 = Math.max(box.x0, view.x0), y0 = Math.max(box.y0, view.y0);
    const x1 = Math.min(box.x1, view.x1), y1 = Math.min(box.y1, view.y1);
    if (x1 <= x0 || y1 <= y0) return null;
    const sx = image.width / (box.x1 - box.x0), sy = image.height / (box.y1 - box.y0);
    const dx = width / (view.x1 - view.x0), dy = height / (view.y1 - view.y0);
    return [(x0 - box.x0) * sx, (y0 - box.y0) * sy, (x1 - x0) * sx, (y1 - y0) * sy,
      (x0 - view.x0) * dx, (y0 - view.y0) * dy, (x1 - x0) * dx, (y1 - y0) * dy];
  }

  const WorldImages = L.Layer.extend({
    initialize(overview, options = {}) {
      this.overview = overview && {...overview, box: rect(overview.bounds)};
      this.budget = options.budget || (overview ? 32 : 4) * MiB;
      this.index = new WorldIndex(); this.serial = 0; this.drawn = 0;
    },
    onAdd(map) {
      this.suspended = false;
      this.root = L.DomUtil.create('canvas', 'world-images');
      this.root.setAttribute('aria-hidden', 'true'); this.root.style.zIndex = this.overview ? '1' : '2';
      map.getPane('overlayPane').appendChild(this.root);
      this.cache = new ImageCache(this.budget, () => this.schedule());
      this.suspend = () => {
        this.suspended = true; cancelAnimationFrame(this.frame); this.frame = null;
        this.cache.clear(); this.root.width = this.root.height = 1;
        this.coverage = this.lastView = null;
      };
      this.resume = () => { this.suspended = false; this.schedule(); };
      this.hidden = () => { if (document.hidden) this.suspend(); else this.resume(); };
      document.addEventListener('visibilitychange', this.hidden);
      window.addEventListener('pagehide', this.suspend);
      window.addEventListener('pageshow', this.resume);
      this.redraw();
    },
    onRemove() {
      cancelAnimationFrame(this.frame); this.frame = null;
      document.removeEventListener('visibilitychange', this.hidden);
      window.removeEventListener('pagehide', this.suspend);
      window.removeEventListener('pageshow', this.resume);
      this.cache.clear();
      this.root.width = this.root.height = 1; this.root.remove(); this.root = null;
      this.coverage = this.lastView = null;
    },
    // Leaflet already invokes these inside its pinch animation frame. Draw now,
    // without adding a frame of input delay or a CSS surface-scaling animation.
    getEvents() { return {zoom: this.redraw, move: this.redraw, moveend: this.settle, resize: this.settle}; },
    settle() { this.coverage = this.lastView = null; this.redraw(); },
    addImage(record) {
      record.order = record.order || ++this.serial;
      this.index.add(record); this.coverage = null; this.schedule();
    },
    removeImage(record) { this.index.remove(record); this.coverage = null; this.schedule(); },
    updateImage(record, geometry) {
      if (geometry) { this.index.remove(record); record.box = rect(record.bounds); this.index.add(record); }
      this.coverage = null; this.schedule();
    },
    schedule() {
      this.lastView = null;
      if (this.root && !this.suspended && !document.hidden && this.frame == null) this.frame = requestAnimationFrame(() => {
        this.frame = null; this.redraw();
      });
    },
    choose(view) {
      this.selectionZoom = this._map.getZoom();
      this.coverage = rect(this._map.getBounds().pad(0.15));
      const overviewEntry = this.overview && this.cache.entries.get(this.overview.url);
      this.coarse = Boolean(this.overview && overviewEntry?.state !== 'failed' && this._map.getZoom() <= this.overview.detailZoom);
      this.records = this.coarse ? [] : this.index.query(this.coverage);
      const requests = [];
      if (this.overview) {
        const b = this.overview.box, scale = 2 ** this.overview.detailZoom;
        requests.push({url: this.overview.url, width: Math.round((b.x1 - b.x0) * scale), height: Math.round((b.y1 - b.y0) * scale)});
      }
      const cx = (view.x0 + view.x1) / 2, cy = (view.y0 + view.y1) / 2;
      const distance = r => Math.max(r.box.x0 - cx, 0, cx - r.box.x1) ** 2 + Math.max(r.box.y0 - cy, 0, cy - r.box.y1) ** 2;
      this.records.sort((a, b) => Number(intersects(b.box, view)) - Number(intersects(a.box, view)) || distance(a) - distance(b) || a.order - b.order);
      for (const r of this.records) requests.push({url: r.url, width: r.box.x1 - r.box.x0, height: r.box.y1 - r.box.y0});
      this.cache.select(requests); this.records.sort((a, b) => a.order - b.order);
    },
    redraw() {
      if (!this.root || this.suspended || document.hidden) return;
      const size = this._map.getSize(), view = rect(this._map.getBounds());
      if (!size.x || !size.y) return;
      const origin = this._map.containerPointToLayerPoint([0, 0]);
      const key = [view.x0, view.y0, view.x1, view.y1, size.x, size.y, origin.x, origin.y, this._map.getZoom()].join(',');
      if (this.lastView === key) return; // zoom + move describe the same frame.
      const failed = this.overview && this.cache.entries.get(this.overview.url)?.state === 'failed';
      const coarse = Boolean(this.overview && !failed && this._map.getZoom() <= this.overview.detailZoom);
      if (!this.coverage || this.coarse !== coarse || Math.abs(this._map.getZoom() - this.selectionZoom) > 0.5
          || !contains(this.coverage, view)) this.choose(view);
      const backing = surfaceSize(size.x, size.y);
      if (this.root.width !== backing.width) this.root.width = backing.width;
      if (this.root.height !== backing.height) this.root.height = backing.height;
      this.root.style.width = size.x + 'px'; this.root.style.height = size.y + 'px';
      // Cancel the moving map pane's offset with translation only. Scale stays 1.
      L.DomUtil.setPosition(this.root, origin);
      const ctx = this.root.getContext('2d');
      ctx.clearRect(0, 0, backing.width, backing.height); ctx.imageSmoothingEnabled = false;
      this.drawn = 0;
      const draw = (url, box) => {
        const image = this.cache.get(url), args = image && crop(image, box, view, backing.width, backing.height);
        if (args) { ctx.drawImage(image, ...args); this.drawn++; }
      };
      if (this.overview) draw(this.overview.url, this.overview.box);
      for (const record of this.records || []) draw(record.url, record.box);
      this.lastView = key;
    },
    stats() { return {registered: this.index.records.size, drawn: this.drawn, cached: this.cache.entries.size,
      failed: Array.from(this.cache.entries.values()).filter(e => e.state === 'failed').length,
      loading: this.cache.active, reservedBytes: this.cache.bytes, decodingBytes: this.cache.activeBytes, budgetBytes: this.budget,
      canvasWidth: this.root?.width || 0, canvasHeight: this.root?.height || 0}; },
  });

  const WorldImage = L.Layer.extend({
    initialize(url, bounds, renderer, options) {
      L.setOptions(this, options); this.url = url; this.bounds = L.latLngBounds(bounds);
      this.box = rect(this.bounds); this.renderer = renderer;
    },
    onAdd(map) {
      if (!map.hasLayer(this.renderer)) this.renderer.addTo(map);
      this.renderer.addImage(this);
    },
    onRemove() { this.renderer.removeImage(this); },
    setUrl(url) { this.url = url; if (this._map) this.renderer.updateImage(this, false); return this; },
    setBounds(bounds) { this.bounds = L.latLngBounds(bounds); if (this._map) this.renderer.updateImage(this, true); else this.box = rect(this.bounds); return this; },
    getBounds() { return this.bounds; },
  });
  window.BPEWorldImages = {WorldIndex, ImageCache, surfaceSize, crop, intersects, contains,
    renderer: (overview, options) => new WorldImages(overview, options),
    image: (url, bounds, renderer, options) => new WorldImage(url, bounds, renderer, options)};
}());
