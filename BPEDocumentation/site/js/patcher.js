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

  // A validated ROM is kept in this browser's IndexedDB (cookies are far too
  // small) so a returning visitor need not choose it again. It never leaves the
  // device, and every failure here just falls back to choosing a file.
  var savedRom = {
    key: 'emerald',
    restoring: false,
    open: function () {
      return new Promise(function (resolve, reject) {
        var request = indexedDB.open('bpe-patcher', 1);
        request.onupgradeneeded = function () { request.result.createObjectStore('rom'); };
        request.onsuccess = function () { resolve(request.result); };
        request.onerror = request.onblocked = function () { reject(request.error); };
      });
    },
    run: function (mode, action) {
      return savedRom.open().then(function (db) {
        return new Promise(function (resolve, reject) {
          var transaction = db.transaction('rom', mode);
          var request = action(transaction.objectStore('rom'));
          transaction.oncomplete = function () { db.close(); resolve(request.result); };
          transaction.onerror = transaction.onabort = function () { db.close(); reject(transaction.error); };
        });
      });
    },
    save: function (romFile) {
      try {
        // Copy the bytes now: the engine hands this buffer to its workers.
        var record = { name: romFile.fileName, data: new Blob([romFile._u8array]) };
        savedRom.run('readwrite', function (store) { return store.put(record, savedRom.key); }).catch(function () {});
      } catch (error) { /* storage unavailable */ }
    },
    forget: function () {
      try {
        savedRom.run('readwrite', function (store) { return store.delete(savedRom.key); }).catch(function () {});
      } catch (error) { /* storage unavailable */ }
    },
    restore: async function () {
      try {
        var record = await savedRom.run('readonly', function (store) { return store.get(savedRom.key); });
        if (!record || !record.data) return;
        var bytes = await record.data.arrayBuffer();
        if (window.BPERelease.leaving || document.getElementById('rom-patcher-input-file-rom').files.length) return;
        var binFile = new BinFile(bytes);
        binFile.fileName = record.name || 'Pokemon Emerald.gba';
        savedRom.restoring = true;
        RomPatcherWeb.provideRomFile(binFile, true);
      } catch (error) { /* storage unavailable */ }
    }
  };

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
      var restoreTried = false;
      RomPatcherWeb.initialize({
        language: 'en',
        requireValidation: true,
        allowDropFiles: true,
        onloadrom: function () { setStatus('checking', 'Checking ROM…'); },
        onloadpatch: function () {
          setStatus('ready');
          if (!restoreTried) {
            restoreTried = true;
            savedRom.restore();
          }
        },
        onvalidaterom: function (romFile, isValid) {
          var restored = savedRom.restoring;
          savedRom.restoring = false;
          if (isValid) {
            setStatus('ready', restored ? 'Remembered your ROM from last time. Ready to patch.' : '');
            if (!restored) savedRom.save(romFile);
          } else {
            if (restored) savedRom.forget();
            setStatus('invalid', 'Choose an unmodified Pokémon Emerald (USA) ROM.');
          }
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
