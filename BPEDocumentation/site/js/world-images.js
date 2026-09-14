/* World-space images share a transform. Leaflet ImageOverlay resizes every
 * image on every pinch frame; these lightweight layers only update one parent.
 * Images outside a buffered viewport are released after movement settles. */
(function () {
  'use strict';

  const intersects = (a, b) => a.x0 <= b.x1 && a.x1 >= b.x0 && a.y0 <= b.y1 && a.y1 >= b.y0;
  const contains = (a, b) => a.x0 <= b.x0 && a.x1 >= b.x1 && a.y0 <= b.y0 && a.y1 >= b.y1;
  const rect = bounds => ({x0: bounds.getWest(), x1: bounds.getEast(),
    y0: -bounds.getNorth(), y1: -bounds.getSouth()});

  // The same index serves large terrain rectangles and small sprite bounds.
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
      record.cells = this.keys(record.box);
      this.records.add(record);
      for (const key of record.cells) {
        if (!this.cells.has(key)) this.cells.set(key, new Set());
        this.cells.get(key).add(record);
      }
    }
    remove(record) {
      this.records.delete(record);
      for (const key of record.cells || []) {
        const cell = this.cells.get(key);
        cell.delete(record);
        if (!cell.size) this.cells.delete(key);
      }
    }
    query(box) {
      const count = (Math.ceil((box.x1 - box.x0) / this.size) + 2)
        * (Math.ceil((box.y1 - box.y0) / this.size) + 2);
      let candidates = this.records;
      if (count < this.cells.size) {
        candidates = new Set();
        for (const key of this.keys(box)) for (const record of this.cells.get(key) || []) candidates.add(record);
      }
      return Array.from(candidates).filter(record => intersects(record.box, box));
    }
  }

  const WorldImages = L.Layer.extend({
    initialize(overview) {
      this.overview = overview;
      this.index = new WorldIndex();
      this.mounted = new Set();
      this.serial = 0;
    },
    onAdd(map) {
      this.root = L.DomUtil.create('div', 'world-images leaflet-zoom-animated');
      map.getPane('overlayPane').appendChild(this.root);
      // Fractional positions are retained, including negative world coordinates.
      // This reference scale stays fixed: child geometry never changes on zoom.
      // Native pixel dimensions also avoid Safari rounding tiny sprite boxes
      // (e.g. 16 px / 64) before applying a later magnifying transform.
      this.referenceZoom = 0;
      this.referenceScale = map.options.crs.scale(this.referenceZoom);
      if (this.overview) {
        const info = this.overview;
        const img = document.createElement('img');
        img.alt = ''; img.draggable = false; img.decoding = 'async';
        img.className = 'world-overview';
        this.position({element: img, box: rect(info.bounds)});
        img.src = info.url;
        this.root.appendChild(img);
        // If an overview cannot load, keep the native images as the fallback.
        img.onerror = () => { img.style.display = 'none'; this.overviewFailed = true; this.coverage = null; this.refresh(); };
      }
      this.transform();
      this.refresh();
    },
    onRemove() {
      cancelAnimationFrame(this.frame);
      this.frame = null;
      for (const record of this.mounted) this.unmount(record);
      this.root.remove();
      this.root = null;
      this.coverage = null;
      this.pending = [];
    },
    getEvents() {
      return {zoom: this.transform, zoomanim: this.animateZoom,
        move: this.checkCoverage, moveend: this.settle, resize: this.settle};
    },
    transform() {
      if (!this.root) return;
      const origin = this._map.latLngToLayerPoint([0, 0]);
      L.DomUtil.setTransform(this.root, origin, this._map.getZoomScale(this._map.getZoom(), this.referenceZoom));
    },
    animateZoom(event) {
      const origin = this._map.project([0, 0], event.zoom)
        .subtract(this._map._getNewPixelOrigin(event.center, event.zoom));
      L.DomUtil.setTransform(this.root, origin, this._map.getZoomScale(event.zoom, this.referenceZoom));
    },
    checkCoverage() {
      // Panning is already handled by Leaflet's map pane. Only fill new coverage
      // when a pinch-out or drag approaches the edge of our existing buffer.
      if (this.coarse !== this.useOverview() || !this.coverage || !contains(this.coverage, rect(this._map.getBounds().pad(0.1)))) this.refresh();
    },
    useOverview() { return Boolean(this.overview && !this.overviewFailed && this._map.getZoom() <= this.overview.detailZoom); },
    settle() {
      this.transform();
      this.refresh(true);
    },
    addImage(record) {
      record.order = record.order || ++this.serial;
      this.index.add(record);
      this.coverage = null;
      this.schedule();
    },
    removeImage(record) {
      this.index.remove(record);
      this.unmount(record);
    },
    updateImage(record, geometry) {
      if (geometry) {
        this.index.remove(record);
        record.box = rect(record.bounds);
        this.index.add(record);
        if (record.element) this.position(record);
      }
      if (record.element && record.element.getAttribute('src') !== record.url) record.element.src = record.url;
      this.coverage = null;
      this.schedule();
    },
    position(record) {
      const b = record.box, s = this.referenceScale, style = record.element.style;
      style.left = b.x0 * s + 'px';
      style.top = b.y0 * s + 'px';
      style.width = (b.x1 - b.x0) * s + 'px';
      style.height = (b.y1 - b.y0) * s + 'px';
    },
    mount(record) {
      if (record.element || !this.index.records.has(record)) return;
      const img = record.element = document.createElement('img');
      img.className = record.options.className || '';
      img.alt = '';
      img.draggable = false;
      img.decoding = 'async';
      // Source order wins even when incremental loading completes out of order.
      img.style.zIndex = record.order;
      this.position(record);
      img.src = record.url;
      this.root.appendChild(img);
      this.mounted.add(record);
    },
    unmount(record) {
      if (record.element) record.element.remove();
      record.element = null;
      this.mounted.delete(record);
    },
    refresh(trim = false) {
      if (!this._map) return;
      const view = rect(this._map.getBounds());
      this.coverage = rect(this._map.getBounds().pad(0.4));
      this.coarse = this.useOverview();
      if (this.coarse) {
        this.pending = [];
        for (const record of this.mounted) this.unmount(record);
        return;
      }
      const records = this.index.query(this.coverage);
      if (trim) for (const record of this.mounted) if (!intersects(record.box, this.coverage)) this.unmount(record);
      // Load the actual view first; nearby artwork follows within the same budget.
      this.pending = records.filter(record => !record.element)
        .sort((a, b) => Number(intersects(b.box, view)) - Number(intersects(a.box, view)) || a.order - b.order);
      this.schedule();
    },
    schedule() {
      if (this._map && this.frame == null) this.frame = requestAnimationFrame(() => this.flush());
    },
    flush() {
      this.frame = null;
      if (!this._map) return;
      if (!this.coverage) this.refresh();
      const start = performance.now();
      while (this.pending && this.pending.length && performance.now() - start < 3) this.mount(this.pending.shift());
      if (this.pending && this.pending.length) this.schedule();
    },
    stats() { return {registered: this.index.records.size, mounted: this.mounted.size, pending: (this.pending || []).length}; },
  });

  const WorldImage = L.Layer.extend({
    initialize(url, bounds, renderer, options) {
      L.setOptions(this, options);
      this.url = url;
      this.bounds = L.latLngBounds(bounds);
      this.box = rect(this.bounds);
      this.renderer = renderer;
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

  window.BPEWorldImages = {WorldIndex, intersects, contains,
    renderer: overview => new WorldImages(overview),
    image: (url, bounds, renderer, options) => new WorldImage(url, bounds, renderer, options)};
}());
