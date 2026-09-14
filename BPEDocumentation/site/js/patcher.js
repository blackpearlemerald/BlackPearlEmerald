(function () {
  'use strict';

  var statusBox = document.getElementById('patcher-status');
  var statusTitle = document.getElementById('patcher-status-title');
  var statusCopy = document.getElementById('patcher-status-copy');
  var applyButton = document.getElementById('rom-patcher-button-apply');
  var errorRow = document.getElementById('rom-patcher-row-error-message');
  var errorMessage = document.getElementById('rom-patcher-error-message');
  var autoPatchQueued = false;

  function setStatus(state, title, copy) {
    statusBox.className = 'patcher-status is-' + state;
    statusTitle.textContent = title;
    statusCopy.textContent = copy;
  }

  function watchForPatcherErrors() {
    if (!window.MutationObserver || !errorRow) return;

    new MutationObserver(function () {
      var message = errorMessage.textContent.trim();
      if (!errorRow.classList.contains('show') || !message) return;
      if (/checksum mismatch/i.test(message)) return;

      autoPatchQueued = false;
      setStatus('error', 'The ROM could not be patched', message);
    }).observe(errorRow, {
      attributes: true,
      childList: true,
      subtree: true,
      characterData: true
    });
  }

  window.addEventListener('load', async function () {
    watchForPatcherErrors();

    try {
      var release = await window.BPERelease.ready;
      if (!release.patch) throw new Error('No patch is available for this release.');
      document.querySelector('.patcher-kicker').textContent = 'BPE Emerald ' + release.label;
      document.getElementById('bpe-patch-label').textContent = release.label + ' (UPS)';
      var controller = new AbortController();
      window.addEventListener('bpe:versionchange', function () { controller.abort(); autoPatchQueued = true; applyButton.disabled = true; });
      setStatus('checking', 'Checking the ' + release.label + ' patch…', 'Please wait before choosing your Emerald ROM.');
      var response = await fetch(new URL(release.patch.url, window.BPERelease.root), { signal: controller.signal });
      if (!response.ok) throw new Error('The selected release patch could not be downloaded.');
      var bytes = await response.arrayBuffer();
      var digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))).map(function (n) { return n.toString(16).padStart(2, '0'); }).join('');
      if (digest !== release.patch.archiveSha256) throw new Error('The selected release patch failed its checksum check.');
      if (window.BPERelease.leaving) return;
      var patchUrl = URL.createObjectURL(new Blob([bytes], { type: 'application/zip' }));
      window.addEventListener('pagehide', function () { URL.revokeObjectURL(patchUrl); });
      RomPatcherWeb.initialize({
        language: 'en',
        requireValidation: true,
        allowDropFiles: true,

        onloadrom: function () {
          autoPatchQueued = false;
          applyButton.textContent = 'Patch & download';
          setStatus('checking', 'Checking your Emerald ROM…', 'The patch will start automatically if this is the correct base game.');
        },

        onloadpatch: function () {
          setStatus('ready', 'The BPE patch is ready', 'Choose your clean Pokémon Emerald ROM above to begin.');
        },

        onvalidaterom: function (romFile, isValid) {
          if (!isValid) {
            autoPatchQueued = false;
            setStatus('invalid', 'This is not the required Emerald ROM', 'Use a clean, unmodified US copy of Pokémon Emerald and try again.');
            return;
          }

          if (autoPatchQueued) return;
          autoPatchQueued = true;
          setStatus('working', 'Building your BPE ROM…', 'Keep this tab open. Your download will begin automatically.');

          window.setTimeout(function () {
            try {
              if (!window.BPERelease.leaving) RomPatcherWeb.applyPatch();
            } catch (error) {
              autoPatchQueued = false;
              setStatus('error', 'The ROM could not be patched', error.message || 'Please choose the ROM again and retry.');
            }
          }, 100);
        },

        onpatch: function () {
          setStatus('success', 'Your BPE ROM is ready', 'The patched .gba file should download automatically. Use the button below to download it again.');
          applyButton.textContent = 'Download again';
        }
      }, {
        file: patchUrl,
        patches: [
          {
            file: release.patch.file,
            name: 'Pokémon Black Pearl Emerald ' + release.label,
            inputCrc32: parseInt(release.baseRom.crc32, 16),
            description: 'BPE Emerald ' + release.label + ' release patch',
            outputName: 'Pokemon Black Pearl Emerald v' + release.version,
            outputExtension: 'gba'
          }
        ]
      });
    } catch (error) {
      if (window.BPERelease.leaving) return;
      setStatus('error', 'The patcher could not start', error.message || 'Reload the page and try again.');
    }
  });
}());
