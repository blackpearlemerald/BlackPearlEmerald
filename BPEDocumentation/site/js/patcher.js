(function () {
  'use strict';
  var statusBox = document.getElementById('patcher-status');
  var applyButton = document.getElementById('rom-patcher-button-apply');
  var errorRow = document.getElementById('rom-patcher-row-error-message');
  var errorMessage = document.getElementById('rom-patcher-error-message');

  function setStatus(state, message) {
    statusBox.className = 'is-' + state;
    statusBox.textContent = message || '';
    statusBox.hidden = !message;
    applyButton.textContent = 'Patch & Download';
  }

  function watchForPatcherErrors() {
    if (!window.MutationObserver) return;
    new MutationObserver(function () {
      var message = errorMessage.textContent.trim();
      if (!errorRow.classList.contains('show') || !message) return;
      if (/checksum mismatch/i.test(message)) return;
      setStatus('error', message);
    }).observe(errorRow, { attributes: true, childList: true, subtree: true, characterData: true });
  }

  // The engine supplies the click handler; choosing a ROM only validates it.
  applyButton.addEventListener('click', function (event) {
    if (window.BPERelease.leaving) {
      event.stopImmediatePropagation();
      return;
    }
    setStatus('working');
  });

  window.addEventListener('load', async function () {
    watchForPatcherErrors();
    try {
      var release = await window.BPERelease.ready;
      if (!release.patch) throw new Error('No patch is available for this version.');
      document.getElementById('bpe-patch-label').textContent = 'Version ' + release.label + ' patch';
      var controller = new AbortController();
      window.addEventListener('bpe:versionchange', function () {
        controller.abort();
        applyButton.disabled = true;
        document.getElementById('rom-patcher-input-file-rom').disabled = true;
      });
      setStatus('loading', 'Loading patch…');
      var response = await fetch(new URL(release.patch.url, window.BPERelease.root), { signal: controller.signal });
      if (!response.ok) throw new Error('Could not load this patch. Reload to try again.');
      var bytes = await response.arrayBuffer();
      var digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))).map(function (n) { return n.toString(16).padStart(2, '0'); }).join('');
      if (digest !== release.patch.archiveSha256) throw new Error('Could not verify this patch. Reload to try again.');
      if (window.BPERelease.leaving) return;
      var patchUrl = URL.createObjectURL(new Blob([bytes], { type: 'application/zip' }));
      window.addEventListener('pagehide', function () { URL.revokeObjectURL(patchUrl); });
      RomPatcherWeb.initialize({
        language: 'en',
        requireValidation: true,
        allowDropFiles: true,
        onloadrom: function () { setStatus('checking', 'Checking ROM…'); },
        onloadpatch: function () { setStatus('ready'); },
        onvalidaterom: function (romFile, isValid) {
          if (isValid) setStatus('ready');
          else setStatus('invalid', 'Choose an unmodified Pokémon Emerald (USA) ROM.');
        },
        onpatch: function () { setStatus('success'); }
      }, {
        file: patchUrl,
        patches: [{
          file: release.patch.file,
          name: 'Pokémon Black Pearl Emerald ' + release.label,
          inputCrc32: parseInt(release.baseRom.crc32, 16),
          outputName: 'Pokemon Black Pearl Emerald v' + release.version,
          outputExtension: 'gba'
        }]
      });
    } catch (error) {
      if (!window.BPERelease.leaving) setStatus('error', error.message || 'Reload to try again.');
    }
  });
}());
