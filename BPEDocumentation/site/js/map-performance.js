/* Optional on-device diagnostics; inert unless the URL includes map-perf=1. */
(function () {
  'use strict';
  window.BPEMapPerformance = function (map, renderers) {
    if (new URLSearchParams(location.search).get('map-perf') !== '1') return;
    const reports = [];
    let frame = null, finish = null, previous = null, samples = [], started = 0;
    const output = document.createElement('pre');
    output.className = 'map-performance';
    output.textContent = 'Pinch the map to measure frame intervals.';
    document.getElementById('panel').appendChild(output);
    function tick(now) {
      if (previous !== null && samples.length < 2400) samples.push(now - previous);
      previous = now;
      frame = requestAnimationFrame(tick);
    }
    function start() {
      if (finish !== null) { cancelAnimationFrame(finish); finish = null; }
      if (frame !== null) return;
      started = performance.now(); samples = []; previous = null;
      frame = requestAnimationFrame(tick);
    }
    function stop() {
      cancelAnimationFrame(finish);
      finish = requestAnimationFrame(() => {
        finish = null; cancelAnimationFrame(frame); frame = null;
        if (!samples.length) return;
        const sorted = samples.slice().sort((a, b) => a - b);
        const percentile = fraction => +sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * fraction))].toFixed(2);
        const report = {durationMs: Math.round(performance.now() - started), frames: sorted.length,
          p50: percentile(0.5), p95: percentile(0.95), p99: percentile(0.99),
          max: +sorted[sorted.length - 1].toFixed(2),
          images: renderers.map(renderer => renderer.stats())};
        reports.push(report); if (reports.length > 20) reports.shift();
        output.textContent = 'Frame intervals (ms)\n' + JSON.stringify(report, null, 2)
          + '\nFrame timing is a proxy; also check visible motion.';
      });
    }
    function reset() {
      cancelAnimationFrame(frame); cancelAnimationFrame(finish);
      frame = finish = null; previous = null; samples = [];
    }
    const hidden = () => { if (document.hidden) reset(); };
    map.on('zoomstart', start);
    map.on('zoomend', stop);
    document.addEventListener('visibilitychange', hidden);
    map.on('unload', () => { reset(); document.removeEventListener('visibilitychange', hidden); });
    return {reports};
  };
}());
