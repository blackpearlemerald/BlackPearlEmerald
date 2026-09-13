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

  window.addEventListener('load', function () {
    watchForPatcherErrors();

    try {
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
              RomPatcherWeb.applyPatch();
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
        file: 'patches/BlackPearlEmerald_v1.0.1.zip',
        patches: [
          {
            file: 'BlackPearlEmerald_v1.0.1.ups',
            name: 'Pokémon Black Pearl Emerald v1.0.1',
            inputCrc32: 0x1f1c08fb,
            description: 'Official BPE Emerald v1.0.1 release patch',
            outputName: 'Pokemon Black Pearl Emerald v1.0.1',
            outputExtension: 'gba'
          }
        ]
      });
    } catch (error) {
      setStatus('error', 'The patcher could not start', error.message || 'Reload the page and try again.');
    }
  });
}());
