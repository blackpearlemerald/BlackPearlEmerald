// Black Pearl Emerald Save Converter: saves from any release before 2.1
// (1.0.1 through 2.0.7-beta) to the 2.1 save format. Everything runs in the
// browser; the file never leaves the player's computer. The damage calculator
// also uses readSaveFile to import the Pokémon in a save of either format.
//
// This is a port of BPETools/bpe_save_format.py, which is checked against the
// game's own C code. BPETools/tests/test_bpe_save_format.py runs this file in
// Node and requires byte-identical output, so keep the two in step.
(function (root) {
  'use strict';

  var SECTOR_SIZE = 4096;
  var SECTOR_COUNT = 32;
  var FLASH_SIZE = SECTOR_SIZE * SECTOR_COUNT;

  // 2.1 format (include/save_engine.h)
  var PAYLOAD_SIZE = 4080;
  var CRC_OFFSET = 4080;
  var KIND_OFFSET = 4084;
  var ID_OFFSET = 4085;
  var VERSION_OFFSET = 4086;
  var SIGNATURE_OFFSET = 4088;
  var COUNTER_OFFSET = 4092;
  var SIGNATURE_V2 = 0x32455042;
  var SIGNATURE_LEGACY = 0x08012025;
  var FORMAT_VERSION = 1;
  var KIND_PROGRESS = 1;
  var KIND_BOX = 2;
  var PROGRESS_PARTS = 5;
  var SECTOR_PROGRESS = [0, 5];
  var SECTOR_BOX_FIRST = 10;
  var BOX_SECTOR_COUNT = 19;
  var SECTOR_BOX_BACKUP = 29;
  var SECTOR_HOF = [30, 31];
  var BOX_MON_SIZE = 60;
  var BOX_MONS_PER_SECTOR = 66;
  var BOX_GAME_ID_OFFSET = BOX_MON_SIZE * BOX_MONS_PER_SECTOR;
  var META_SIZE = 4 + 4 * BOX_SECTOR_COUNT + 4;

  var TOTAL_BOXES = 41;
  var IN_BOX_COUNT = 30;
  var BOX_NAME_SIZE = 9;
  var FUSIONS_SIZE = 400;
  var SAVEBLOCK1_SIZE = 15836;
  var SAVEBLOCK2_SIZE = 2852;
  var SAVEBLOCK3_SIZE = 4;

  // Pre-2.1 format (1.0.1 through 2.0.7-beta share it)
  var LEGACY_SECTORS_PER_SLOT = 14;
  var LEGACY_DATA_SIZE = 3968;
  var LEGACY_FOOTER = 4084;
  var LEGACY_TOTAL_BOXES = 14;
  var LEGACY_STORAGE_SIZE = 34144;
  var LEGACY_BOXES_OFFSET = 4;
  var LEGACY_NAMES_OFFSET = 33604;
  var LEGACY_WALLPAPERS_OFFSET = 33730;
  var LEGACY_FUSIONS_OFFSET = 33744;
  var MAX_DEFAULT_WALLPAPER = 3;

  function storageHeaderSize(totalBoxes) {
    var unaligned = 1 + totalBoxes * BOX_NAME_SIZE + totalBoxes;
    return ((unaligned + 3) & ~3) + FUSIONS_SIZE;
  }

  // CRC-32 ----------------------------------------------------------------------

  var CRC_TABLE = (function () {
    var table = new Uint32Array(256);
    for (var n = 0; n < 256; n++) {
      var c = n;
      for (var k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
      table[n] = c >>> 0;
    }
    return table;
  }());

  function crc32Update(crc, bytes, start, end) {
    for (var i = start; i < end; i++) crc = CRC_TABLE[(crc ^ bytes[i]) & 0xFF] ^ (crc >>> 8);
    return crc >>> 0;
  }

  function sectorCrc(sector) {
    var crc = crc32Update(0xFFFFFFFF, sector, 0, CRC_OFFSET);
    crc = crc32Update(crc, sector, KIND_OFFSET, SECTOR_SIZE);
    return (~crc) >>> 0;
  }

  function readU32(bytes, offset) {
    return (bytes[offset] | (bytes[offset + 1] << 8) | (bytes[offset + 2] << 16) | (bytes[offset + 3] << 24)) >>> 0;
  }

  function readU16(bytes, offset) {
    return bytes[offset] | (bytes[offset + 1] << 8);
  }

  function writeU32(bytes, offset, value) {
    bytes[offset] = value & 0xFF;
    bytes[offset + 1] = (value >>> 8) & 0xFF;
    bytes[offset + 2] = (value >>> 16) & 0xFF;
    bytes[offset + 3] = (value >>> 24) & 0xFF;
  }

  function writeU16(bytes, offset, value) {
    bytes[offset] = value & 0xFF;
    bytes[offset + 1] = (value >>> 8) & 0xFF;
  }

  function sectorOf(image, number) {
    return image.subarray(number * SECTOR_SIZE, (number + 1) * SECTOR_SIZE);
  }

  function isSectorValid(sector, kind, id) {
    return readU32(sector, SIGNATURE_OFFSET) === SIGNATURE_V2 &&
      sector[KIND_OFFSET] === kind && sector[ID_OFFSET] === id &&
      readU16(sector, VERSION_OFFSET) === FORMAT_VERSION &&
      readU32(sector, CRC_OFFSET) === sectorCrc(sector);
  }

  function finishSector(payload, kind, id, counter) {
    if (payload.length > PAYLOAD_SIZE) throw new Error('Internal error: sector payload too large.');
    var sector = new Uint8Array(SECTOR_SIZE);
    sector.set(payload, 0);
    sector[KIND_OFFSET] = kind;
    sector[ID_OFFSET] = id;
    writeU16(sector, VERSION_OFFSET, FORMAT_VERSION);
    writeU32(sector, SIGNATURE_OFFSET, SIGNATURE_V2);
    writeU32(sector, COUNTER_OFFSET, counter);
    writeU32(sector, CRC_OFFSET, sectorCrc(sector));
    return sector;
  }

  // Bits ------------------------------------------------------------------------
  // Packed records are 480 bits; BigInt keeps the bit arithmetic exact.

  function bytesToBig(bytes, start, length) {
    var value = 0n;
    for (var i = length - 1; i >= 0; i--) value = (value << 8n) | BigInt(bytes[start + i]);
    return value;
  }

  function bigToBytes(value, length) {
    var out = new Uint8Array(length);
    for (var i = 0; i < length; i++) {
      out[i] = Number(value & 0xFFn);
      value >>= 8n;
    }
    return out;
  }

  function readField(bytes, base, spec) {
    var container = 0;
    for (var i = spec[1] - 1; i >= 0; i--) container = container * 256 + bytes[base + spec[0] + i];
    return Math.floor(container / Math.pow(2, spec[2])) % Math.pow(2, spec[3]);
  }

  // struct BoxPokemon -------------------------------------------------------------
  // [offset, size, bit start, width] within the header or substruct

  var HEADER_FIELDS = {
    language: [18, 1, 0, 3], hiddenNatureModifier: [18, 1, 3, 5],
    isBadEgg: [19, 1, 0, 1], hasSpecies: [19, 1, 1, 1], isEgg: [19, 1, 2, 1], blockBoxRS: [19, 1, 3, 1],
    dead: [19, 1, 4, 1], daysSinceFormChange: [19, 1, 5, 3],
    markings: [27, 1, 0, 4], compressedStatus: [27, 1, 4, 4],
    hpLost: [30, 2, 0, 14], shinyModifier: [30, 2, 14, 1]
  };

  var SUBSTRUCT_FIELDS = [
    {
      species: [0, 2, 0, 11], teraType: [0, 2, 11, 5], heldItem: [2, 2, 0, 10],
      experience: [4, 4, 0, 21], nickname11: [4, 4, 21, 8], ppBonuses: [8, 1, 0, 8], friendship: [9, 1, 0, 8],
      pokeball: [10, 2, 0, 6], nickname12: [10, 2, 6, 8]
    },
    {
      move1: [0, 2, 0, 11], evolutionTracker1: [0, 2, 11, 5], move2: [2, 2, 0, 11], evolutionTracker2: [2, 2, 11, 5],
      move3: [4, 2, 0, 11], move4: [6, 2, 0, 11], hyperTrainedHP: [6, 2, 14, 1], hyperTrainedAttack: [6, 2, 15, 1],
      pp1: [8, 1, 0, 7], hyperTrainedDefense: [8, 1, 7, 1], pp2: [9, 1, 0, 7], hyperTrainedSpeed: [9, 1, 7, 1],
      pp3: [10, 1, 0, 7], hyperTrainedSpAttack: [10, 1, 7, 1], pp4: [11, 1, 0, 7], hyperTrainedSpDefense: [11, 1, 7, 1]
    },
    {
      hpEV: [0, 1, 0, 8], attackEV: [1, 1, 0, 8], defenseEV: [2, 1, 0, 8], speedEV: [3, 1, 0, 8],
      spAttackEV: [4, 1, 0, 8], spDefenseEV: [5, 1, 0, 8]
    },
    {
      pokerus: [0, 1, 0, 8], metLocation: [1, 1, 0, 8], metLevel: [2, 2, 0, 7], metGame: [2, 2, 7, 4],
      dynamaxLevel: [2, 2, 11, 4], otGender: [2, 2, 15, 1],
      hpIV: [4, 4, 0, 5], attackIV: [4, 4, 5, 5], defenseIV: [4, 4, 10, 5], speedIV: [4, 4, 15, 5],
      spAttackIV: [4, 4, 20, 5], spDefenseIV: [4, 4, 25, 5], s3IsEgg: [4, 4, 30, 1], gigantamaxFactor: [4, 4, 31, 1],
      championRibbon: [8, 4, 15, 1], isShadow: [8, 4, 27, 1], abilityNum: [8, 4, 29, 2], modernFatefulEncounter: [8, 4, 31, 1]
    }
  ];

  var SUBSTRUCT_OFFSETS = [
    [0, 0, 0, 0, 0, 0, 1, 1, 2, 3, 2, 3, 1, 1, 2, 3, 2, 3, 1, 1, 2, 3, 2, 3],
    [1, 1, 2, 3, 2, 3, 0, 0, 0, 0, 0, 0, 2, 3, 1, 1, 3, 2, 2, 3, 1, 1, 3, 2],
    [2, 3, 1, 1, 3, 2, 2, 3, 1, 1, 3, 2, 0, 0, 0, 0, 0, 0, 3, 2, 3, 2, 1, 1],
    [3, 2, 3, 2, 1, 1, 3, 2, 3, 2, 1, 1, 3, 2, 3, 2, 1, 1, 0, 0, 0, 0, 0, 0]
  ];

  function decodeBoxMon(record) {
    var data = new Uint8Array(80);
    data.set(record.subarray(0, 80));
    var key = (readU32(data, 0) ^ readU32(data, 4)) >>> 0;
    var checksum = 0;
    for (var offset = 32; offset < 80; offset += 4) {
      var word = (readU32(data, offset) ^ key) >>> 0;
      writeU32(data, offset, word);
      checksum = (checksum + (word & 0xFFFF) + (word >>> 16)) & 0xFFFF;
    }
    var mon = {
      personality: readU32(data, 0),
      otId: readU32(data, 4),
      nickname: data.slice(8, 18),
      otName: data.slice(20, 27),
      checksumValid: readU16(data, 28) === checksum,
      fields: {}
    };
    var name;
    for (name in HEADER_FIELDS) mon.fields[name] = readField(data, 0, HEADER_FIELDS[name]);
    var mod = mon.personality % 24;
    for (var kind = 0; kind < 4; kind++) {
      var base = 32 + 12 * SUBSTRUCT_OFFSETS[kind][mod];
      for (name in SUBSTRUCT_FIELDS[kind]) mon.fields[name] = readField(data, base, SUBSTRUCT_FIELDS[kind][name]);
    }
    return mon;
  }

  // Packed records (include/packed_box_mon.h) ------------------------------------

  var PACKED_FIELDS = (function () {
    var fields = [['personality', 0, 32], ['otId', 32, 32]];
    var i;
    for (i = 0; i < 12; i++) fields.push(['nickname' + i, 64 + 8 * i, 8]);
    for (i = 0; i < 7; i++) fields.push(['otName' + i, 160 + 8 * i, 8]);
    fields.push(['language', 216, 3], ['hiddenNatureModifier', 219, 5], ['isBadEgg', 224, 1], ['isEgg', 225, 1],
      ['dead', 226, 1], ['daysSinceFormChange', 227, 3], ['markings', 230, 4], ['shinyModifier', 234, 1],
      ['species', 235, 11], ['teraType', 246, 5], ['heldItem', 251, 10], ['experience', 261, 21],
      ['ppBonuses', 282, 8], ['friendship', 290, 8], ['pokeball', 298, 6]);
    for (i = 0; i < 4; i++) fields.push(['move' + (i + 1), 304 + 11 * i, 11]);
    fields.push(['evolutionTracker1', 348, 5], ['evolutionTracker2', 353, 5]);
    ['hyperTrainedHP', 'hyperTrainedAttack', 'hyperTrainedDefense', 'hyperTrainedSpeed', 'hyperTrainedSpAttack', 'hyperTrainedSpDefense']
      .forEach(function (name, index) { fields.push([name, 358 + index, 1]); });
    ['hpEV', 'attackEV', 'defenseEV', 'speedEV', 'spAttackEV', 'spDefenseEV']
      .forEach(function (name, index) { fields.push([name, 364 + 8 * index, 8]); });
    fields.push(['pokerus', 412, 8], ['metLocation', 420, 8], ['metLevel', 428, 7], ['metGame', 435, 4],
      ['dynamaxLevel', 439, 4], ['otGender', 443, 1]);
    ['hpIV', 'attackIV', 'defenseIV', 'speedIV', 'spAttackIV', 'spDefenseIV']
      .forEach(function (name, index) { fields.push([name, 444 + 5 * index, 5]); });
    fields.push(['gigantamaxFactor', 474, 1], ['championRibbon', 475, 1], ['isShadow', 476, 1],
      ['abilityNum', 477, 2], ['modernFatefulEncounter', 479, 1]);
    return fields;
  }());

  // Packs an encrypted 80-byte record exactly like PackBoxMon in src/pokemon.c.
  function packBoxMon(record) {
    var mon = decodeBoxMon(record);
    var badEgg = mon.fields.isBadEgg === 1 || !mon.checksumValid;
    if (!badEgg && mon.fields.species === 0) return { packed: new Uint8Array(BOX_MON_SIZE), kind: 'empty', mon: mon };

    var values = Object.assign({}, mon.fields);
    values.personality = mon.personality;
    values.otId = mon.otId;
    for (var i = 0; i < 10; i++) values['nickname' + i] = mon.nickname[i];
    values.nickname10 = mon.fields.nickname11;
    values.nickname11 = mon.fields.nickname12;
    for (i = 0; i < 7; i++) values['otName' + i] = mon.otName[i];
    values.isBadEgg = badEgg ? 1 : 0;
    values.isEgg = (mon.fields.isEgg || mon.fields.s3IsEgg || badEgg) ? 1 : 0;

    var packed = 0n;
    PACKED_FIELDS.forEach(function (field) {
      var mask = (1n << BigInt(field[2])) - 1n;
      packed |= (BigInt(values[field[0]] || 0) & mask) << BigInt(field[1]);
    });
    return { packed: bigToBytes(packed, BOX_MON_SIZE), kind: badEgg ? 'bad_egg' : 'ok', mon: mon };
  }

  function getPacked(record, name) {
    for (var i = 0; i < PACKED_FIELDS.length; i++) {
      if (PACKED_FIELDS[i][0] === name) {
        var value = bytesToBig(record, 0, BOX_MON_SIZE) >> BigInt(PACKED_FIELDS[i][1]);
        return Number(value & ((1n << BigInt(PACKED_FIELDS[i][2])) - 1n));
      }
    }
    throw new Error('Unknown packed field ' + name);
  }

  // Pre-2.1 saves ------------------------------------------------------------------

  function legacyChecksum(bytes, start, size) {
    var total = 0;
    for (var offset = 0; offset + 4 <= size; offset += 4) total = (total + readU32(bytes, start + offset)) >>> 0;
    return ((total >>> 16) + total) & 0xFFFF;
  }

  function legacySectionSizes() {
    var sizes = { 0: SAVEBLOCK2_SIZE };
    for (var section = 1; section < 5; section++)
      sizes[section] = Math.max(0, Math.min(SAVEBLOCK1_SIZE - (section - 1) * LEGACY_DATA_SIZE, LEGACY_DATA_SIZE));
    for (section = 5; section < 14; section++)
      sizes[section] = Math.max(0, Math.min(LEGACY_STORAGE_SIZE - (section - 5) * LEGACY_DATA_SIZE, LEGACY_DATA_SIZE));
    return sizes;
  }

  function findFlashImage(fileBytes) {
    if (fileBytes.length < FLASH_SIZE) throw new Error('This file is too small to be a Pokémon Emerald save.');
    var best = { offset: 0, score: -1 };
    for (var start = 0; start + FLASH_SIZE <= fileBytes.length && start <= 0x10000; start += 4) {
      var score = 0;
      for (var sector = 0; sector < SECTOR_COUNT; sector++) {
        var signature = readU32(fileBytes, start + sector * SECTOR_SIZE + SIGNATURE_OFFSET);
        if (signature === SIGNATURE_LEGACY || signature === SIGNATURE_V2) score++;
      }
      if (score > best.score) best = { offset: start, score: score };
    }
    return { offset: best.offset, image: fileBytes.subarray(best.offset, best.offset + FLASH_SIZE) };
  }

  function detectFormat(image) {
    var v2 = 0, legacy = 0;
    for (var sector = 0; sector < SECTOR_BOX_BACKUP; sector++) {
      var signature = readU32(image, sector * SECTOR_SIZE + SIGNATURE_OFFSET);
      if (signature === SIGNATURE_V2) v2++;
      if (signature === SIGNATURE_LEGACY) legacy++;
    }
    return v2 ? '2.1' : legacy ? '2.0' : 'empty';
  }

  function loadLegacyImage(image) {
    var sizes = legacySectionSizes();
    var slots = [];
    for (var slot = 0; slot < 2; slot++) {
      var sections = {}, count = 0, counters = {};
      for (var physical = 0; physical < LEGACY_SECTORS_PER_SLOT; physical++) {
        var start = (slot * LEGACY_SECTORS_PER_SLOT + physical) * SECTOR_SIZE;
        var id = readU16(image, start + LEGACY_FOOTER);
        var stored = readU16(image, start + LEGACY_FOOTER + 2);
        if (readU32(image, start + LEGACY_FOOTER + 4) !== SIGNATURE_LEGACY || id >= LEGACY_SECTORS_PER_SLOT) continue;
        if (legacyChecksum(image, start, sizes[id]) !== stored) continue;
        if (!sections[id]) count++;
        sections[id] = image.subarray(start, start + SECTOR_SIZE);
        counters[readU32(image, start + LEGACY_FOOTER + 8)] = true;
      }
      var counterValues = Object.keys(counters);
      slots.push({ sections: sections, complete: count === LEGACY_SECTORS_PER_SLOT && counterValues.length === 1,
        counter: counterValues.length ? Number(counterValues[0]) : 0 });
    }
    var valid = [0, 1].filter(function (index) { return slots[index].complete; });
    if (!valid.length) throw new Error('This save has no complete save slot. It may be empty or damaged.');
    var chosen = valid[0];
    if (valid.length === 2) {
      var c0 = slots[0].counter, c1 = slots[1].counter;
      if ((c0 === 0xFFFFFFFF && c1 === 0) || (c0 === 0 && c1 === 0xFFFFFFFF))
        chosen = ((c0 + 1) >>> 0) < ((c1 + 1) >>> 0) ? 1 : 0;
      else
        chosen = c0 < c1 ? 1 : 0;
    }
    var picked = slots[chosen].sections;
    function join(first, last, sizeOf) {
      var total = 0, i;
      for (i = first; i <= last; i++) total += sizeOf(i);
      var out = new Uint8Array(total), offset = 0;
      for (i = first; i <= last; i++) {
        out.set(picked[i].subarray(0, sizeOf(i)), offset);
        offset += sizeOf(i);
      }
      return out;
    }
    var sb3 = new Uint8Array(SAVEBLOCK3_SIZE);
    sb3.set(picked[0].subarray(LEGACY_DATA_SIZE, LEGACY_DATA_SIZE + SAVEBLOCK3_SIZE));
    return {
      saveBlock2: picked[0].slice(0, SAVEBLOCK2_SIZE),
      saveBlock1: join(1, 4, function (i) { return sizes[i]; }),
      saveBlock3: sb3,
      storage: join(5, 13, function (i) { return sizes[i]; }),
      hallOfFame: [image.slice(28 * SECTOR_SIZE, 29 * SECTOR_SIZE), image.slice(29 * SECTOR_SIZE, 30 * SECTOR_SIZE)],
      slot: chosen,
      counter: slots[chosen].counter
    };
  }

  // 2.1 saves ----------------------------------------------------------------------

  var CHAR = { B: 0xBC, O: 0xC9, X: 0xD2 };

  function defaultBoxName(box) {
    var text = 'BOX' + (box + 1);
    var name = new Uint8Array(BOX_NAME_SIZE);
    for (var i = 0; i < text.length; i++) {
      var c = text[i];
      name[i] = c >= '0' && c <= '9' ? 0xA1 + Number(c) : CHAR[c];
    }
    name[text.length] = 0xFF;
    return name;
  }

  function buildImage(save, counter) {
    var image = new Uint8Array(FLASH_SIZE).fill(0xFF);
    var monCount = save.boxes.length / BOX_MON_SIZE;
    var crcs = [];
    for (var index = 0; index < BOX_SECTOR_COUNT; index++) {
      var first = index * BOX_MONS_PER_SECTOR;
      var count = Math.max(0, Math.min(BOX_MONS_PER_SECTOR, monCount - first));
      var payload = new Uint8Array(BOX_GAME_ID_OFFSET + 4);
      payload.set(save.boxes.subarray(first * BOX_MON_SIZE, (first + count) * BOX_MON_SIZE), 0);
      writeU32(payload, BOX_GAME_ID_OFFSET, save.gameId);
      var sector = finishSector(payload, KIND_BOX, index, counter + 1);
      crcs.push(readU32(sector, CRC_OFFSET));
      image.set(sector, (SECTOR_BOX_FIRST + index) * SECTOR_SIZE);
    }
    var part0 = new Uint8Array(META_SIZE + save.saveBlock2.length + save.storageHeader.length + save.saveBlock3.length);
    writeU32(part0, 0, save.gameId);
    crcs.forEach(function (crc, i) { writeU32(part0, 4 + 4 * i, crc); });
    part0.set(save.saveBlock2, META_SIZE);
    part0.set(save.storageHeader, META_SIZE + save.saveBlock2.length);
    part0.set(save.saveBlock3, META_SIZE + save.saveBlock2.length + save.storageHeader.length);
    var parts = [part0];
    for (var part = 1; part < PROGRESS_PARTS; part++)
      parts.push(save.saveBlock1.subarray((part - 1) * PAYLOAD_SIZE, part * PAYLOAD_SIZE));
    SECTOR_PROGRESS.forEach(function (firstSector, copy) {
      parts.forEach(function (payload, part) {
        image.set(finishSector(payload, KIND_PROGRESS, part, counter + copy), (firstSector + part) * SECTOR_SIZE);
      });
    });
    image.set(save.hallOfFame[0], SECTOR_HOF[0] * SECTOR_SIZE);
    image.set(save.hallOfFame[1], SECTOR_HOF[1] * SECTOR_SIZE);
    return image;
  }

  // Loads a 2.1 image with the rules of SaveEngine_Load (used to verify output).
  function loadImage(image) {
    var copies = [];
    SECTOR_PROGRESS.forEach(function (first, copy) {
      var parts = [], ok = true, counter = null;
      for (var part = 0; part < PROGRESS_PARTS; part++) {
        var sector = sectorOf(image, first + part);
        if (!isSectorValid(sector, KIND_PROGRESS, part)) ok = false;
        if (counter === null) counter = readU32(sector, COUNTER_OFFSET);
        else if (counter !== readU32(sector, COUNTER_OFFSET)) ok = false;
        parts.push(sector);
      }
      if (ok) copies.push({ counter: counter, copy: copy, parts: parts });
    });
    if (!copies.length) throw new Error('The converted save could not be read back.');
    // Like FindNewestCopy: the higher counter wins, copy A on a tie
    copies.sort(function (a, b) { return b.counter - a.counter || a.copy - b.copy; });
    var parts = copies[0].parts;
    var part0 = parts[0];
    var headerSize = storageHeaderSize(TOTAL_BOXES);
    var result = {
      gameId: readU32(part0, 0),
      saveBlock2: part0.slice(META_SIZE, META_SIZE + SAVEBLOCK2_SIZE),
      storageHeader: part0.slice(META_SIZE + SAVEBLOCK2_SIZE, META_SIZE + SAVEBLOCK2_SIZE + headerSize),
      saveBlock3: part0.slice(META_SIZE + SAVEBLOCK2_SIZE + headerSize, META_SIZE + SAVEBLOCK2_SIZE + headerSize + SAVEBLOCK3_SIZE),
      saveBlock1: new Uint8Array(SAVEBLOCK1_SIZE),
      boxes: new Uint8Array(TOTAL_BOXES * IN_BOX_COUNT * BOX_MON_SIZE)
    };
    for (var part = 1; part < PROGRESS_PARTS; part++) {
      var size = Math.max(0, Math.min(PAYLOAD_SIZE, SAVEBLOCK1_SIZE - (part - 1) * PAYLOAD_SIZE));
      result.saveBlock1.set(parts[part].subarray(0, size), (part - 1) * PAYLOAD_SIZE);
    }
    var monCount = TOTAL_BOXES * IN_BOX_COUNT;
    for (var index = 0; index < BOX_SECTOR_COUNT; index++) {
      var boxSector = sectorOf(image, SECTOR_BOX_FIRST + index);
      if (!isSectorValid(boxSector, KIND_BOX, index) || readU32(boxSector, BOX_GAME_ID_OFFSET) !== result.gameId ||
          readU32(boxSector, CRC_OFFSET) !== readU32(part0, 4 + 4 * index))
        throw new Error('The converted save could not be read back.');
      var first = index * BOX_MONS_PER_SECTOR;
      var count = Math.max(0, Math.min(BOX_MONS_PER_SECTOR, monCount - first));
      result.boxes.set(boxSector.subarray(0, count * BOX_MON_SIZE), first * BOX_MON_SIZE);
    }
    return result;
  }

  function sameBytes(a, b) {
    if (a.length !== b.length) return false;
    for (var i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
    return true;
  }

  // Conversion ---------------------------------------------------------------------

  function convertLegacy(legacy, gameId) {
    var storage = legacy.storage;
    var headerSize = storageHeaderSize(TOTAL_BOXES);
    var header = new Uint8Array(headerSize);
    var wallpapersOffset = 1 + TOTAL_BOXES * BOX_NAME_SIZE;
    header[0] = storage[0];
    for (var box = 0; box < TOTAL_BOXES; box++) {
      var nameOffset = 1 + box * BOX_NAME_SIZE;
      if (box < LEGACY_TOTAL_BOXES) {
        header.set(storage.subarray(LEGACY_NAMES_OFFSET + box * BOX_NAME_SIZE, LEGACY_NAMES_OFFSET + (box + 1) * BOX_NAME_SIZE), nameOffset);
        header[wallpapersOffset + box] = storage[LEGACY_WALLPAPERS_OFFSET + box];
      } else {
        header.set(defaultBoxName(box), nameOffset);
        header[wallpapersOffset + box] = box % (MAX_DEFAULT_WALLPAPER + 1);
      }
    }
    header.set(storage.subarray(LEGACY_FUSIONS_OFFSET, LEGACY_FUSIONS_OFFSET + FUSIONS_SIZE), headerSize - FUSIONS_SIZE);

    var report = { pcPokemon: 0, droppedBadEggs: 0, sourceSlot: legacy.slot, sourceCounter: legacy.counter };
    var boxes = new Uint8Array(TOTAL_BOXES * IN_BOX_COUNT * BOX_MON_SIZE);
    var identities = [];
    for (var index = 0; index < LEGACY_TOTAL_BOXES * IN_BOX_COUNT; index++) {
      var start = LEGACY_BOXES_OFFSET + index * 80;
      var result = packBoxMon(storage.subarray(start, start + 80));
      if (result.kind === 'bad_egg') {
        report.droppedBadEggs++;
      } else if (result.kind === 'ok') {
        report.pcPokemon++;
        boxes.set(result.packed, index * BOX_MON_SIZE);
        identities.push([index, result.mon]);
      }
    }
    return {
      save: { gameId: gameId, saveBlock2: legacy.saveBlock2, storageHeader: header, saveBlock3: legacy.saveBlock3,
        saveBlock1: legacy.saveBlock1, boxes: boxes, hallOfFame: legacy.hallOfFame },
      report: report,
      identities: identities
    };
  }

  function randomGameId() {
    var id = 0;
    var bytes = new Uint32Array(1);
    while (id === 0) {
      (root.crypto || require('node:crypto').webcrypto).getRandomValues(bytes);
      id = bytes[0];
    }
    return id;
  }

  // Converts a whole .sav/.srm file. Returns the new file bytes and a report,
  // or throws an Error with a message for the player.
  function convertSaveFile(fileBytes, options) {
    options = options || {};
    var found = findFlashImage(fileBytes);
    var format = detectFormat(found.image);
    if (format === '2.1') throw new Error('This save is already in the 2.1 format.');
    if (format === 'empty') throw new Error('This file does not contain a Pokémon Emerald save.');

    var legacy = loadLegacyImage(found.image);
    var converted = convertLegacy(legacy, options.gameId || randomGameId());
    var image = buildImage(converted.save, 1);

    // Read the result back and compare it with what was converted.
    var check = loadImage(image);
    var save = converted.save;
    if (check.gameId !== save.gameId || !sameBytes(check.saveBlock1, save.saveBlock1) ||
        !sameBytes(check.saveBlock2, save.saveBlock2) || !sameBytes(check.saveBlock3, save.saveBlock3) ||
        !sameBytes(check.storageHeader, save.storageHeader) || !sameBytes(check.boxes, save.boxes))
      throw new Error('The converted save did not match the original. Nothing was downloaded.');
    converted.identities.forEach(function (entry) {
      var record = check.boxes.subarray(entry[0] * BOX_MON_SIZE, (entry[0] + 1) * BOX_MON_SIZE);
      if (getPacked(record, 'personality') !== entry[1].personality || getPacked(record, 'otId') !== entry[1].otId ||
          getPacked(record, 'species') !== entry[1].fields.species)
        throw new Error('A Pokémon did not convert correctly. Nothing was downloaded.');
    });

    var output = new Uint8Array(fileBytes.length);
    output.set(fileBytes);
    output.set(image, found.offset);
    return { bytes: output, report: converted.report };
  }

  // Reading Pokémon (damage calculator) ------------------------------------------
  // SaveBlock1 is the same in every release, so these offsets hold for both
  // formats. test/save.c checks them against include/global.h.

  var SB1_PARTY_COUNT = 564;
  var SB1_PARTY = 568;
  var SB1_FLAGS = 5864;
  var SB1_VARS = 6164;
  var SB1_DAYCARE = 13480;
  var PARTY_SIZE = 6;
  var POKEMON_SIZE = 100;
  var POKEMON_LEVEL_OFFSET = 84;
  var DAYCARE_MON_SIZE = 140;
  var DAYCARE_MON_COUNT = 2;
  var VARS_START = 0x4000;
  // Game stat order: HP, Attack, Defense, Speed, Sp. Atk, Sp. Def
  var STATS = ['hp', 'attack', 'defense', 'speed', 'spAttack', 'spDefense'];
  var HYPER_TRAINED = ['hyperTrainedHP', 'hyperTrainedAttack', 'hyperTrainedDefense', 'hyperTrainedSpeed',
    'hyperTrainedSpAttack', 'hyperTrainedSpDefense'];

  // Loads a 2.1 image with the same rules as SaveEngine_Load (load_v21_image in
  // bpe_save_format.py): a box sector that disagrees with the commit is taken
  // from the backup sector when that matches. loadImage above is stricter on
  // purpose, because it checks the converter's own output.
  function loadV21Image(image) {
    var copies = [];
    SECTOR_PROGRESS.forEach(function (first, copy) {
      var parts = [], ok = true, counter = null;
      for (var part = 0; part < PROGRESS_PARTS; part++) {
        var sector = sectorOf(image, first + part);
        if (!isSectorValid(sector, KIND_PROGRESS, part)) ok = false;
        if (counter === null) counter = readU32(sector, COUNTER_OFFSET);
        else if (counter !== readU32(sector, COUNTER_OFFSET)) ok = false;
        parts.push(sector);
      }
      if (ok) copies.push({ counter: counter, copy: copy, parts: parts });
    });
    if (!copies.length) throw new Error('This save is damaged: neither copy of its progress can be read.');
    copies.sort(function (a, b) { return b.counter - a.counter || a.copy - b.copy; });
    var parts = copies[0].parts;
    var gameId = readU32(parts[0], 0);
    var saveBlock1 = new Uint8Array(SAVEBLOCK1_SIZE);
    for (var part = 1; part < PROGRESS_PARTS; part++) {
      var size = Math.max(0, Math.min(PAYLOAD_SIZE, SAVEBLOCK1_SIZE - (part - 1) * PAYLOAD_SIZE));
      saveBlock1.set(parts[part].subarray(0, size), (part - 1) * PAYLOAD_SIZE);
    }

    var backup = sectorOf(image, SECTOR_BOX_BACKUP);
    var backupId = backup[ID_OFFSET];
    var backupValid = backupId < BOX_SECTOR_COUNT && isSectorValid(backup, KIND_BOX, backupId) &&
      readU32(backup, BOX_GAME_ID_OFFSET) === gameId;
    var backupCrc = readU32(backup, CRC_OFFSET);
    var monCount = TOTAL_BOXES * IN_BOX_COUNT;
    var boxes = new Uint8Array(monCount * BOX_MON_SIZE);
    var loadFlags = {};
    for (var index = 0; index < BOX_SECTOR_COUNT; index++) {
      var data = sectorOf(image, SECTOR_BOX_FIRST + index);
      var committed = readU32(parts[0], 4 + 4 * index);
      var valid = isSectorValid(data, KIND_BOX, index);
      var sameGame = readU32(data, BOX_GAME_ID_OFFSET) === gameId;
      var source = null;
      if (valid && sameGame && readU32(data, CRC_OFFSET) === committed) {
        source = data;
      } else if (backupValid && backupId === index && backupCrc === committed) {
        source = backup;
        loadFlags.boxRestored = true;
      } else if (valid && sameGame) {
        source = data;
        loadFlags.boxUncommitted = true;
      } else if (backupValid && backupId === index) {
        source = backup;
        loadFlags.boxRestored = true;
      } else if (!valid) {
        loadFlags.boxLost = true;
      }
      var first = index * BOX_MONS_PER_SECTOR;
      var count = Math.max(0, Math.min(BOX_MONS_PER_SECTOR, monCount - first));
      if (source) boxes.set(source.subarray(0, count * BOX_MON_SIZE), first * BOX_MON_SIZE);
    }
    return { gameId: gameId, saveBlock1: saveBlock1, boxes: boxes, loadFlags: loadFlags, counter: copies[0].counter };
  }

  // The fields of a decoded Pokémon in one shape for both record formats.
  function monSummary(values, nickname) {
    return {
      personality: values.personality, otId: values.otId, nickname: nickname,
      species: values.species, heldItem: values.heldItem, experience: values.experience,
      moves: [values.move1, values.move2, values.move3, values.move4],
      abilityNum: values.abilityNum, hiddenNatureModifier: values.hiddenNatureModifier,
      teraType: values.teraType, friendship: values.friendship, metLocation: values.metLocation,
      isEgg: values.isEgg, dead: values.dead,
      ivs: STATS.map(function (stat) { return values[stat + 'IV']; }),
      evs: STATS.map(function (stat) { return values[stat + 'EV']; }),
      hyperTrained: HYPER_TRAINED.map(function (name) { return values[name]; })
    };
  }

  // An encrypted 80-byte struct BoxPokemon, or null for an empty slot or a Bad Egg.
  function readBoxMon(record) {
    var decoded = decodeBoxMon(record);
    var f = decoded.fields;
    if (f.isBadEgg || !decoded.checksumValid || f.species === 0) return null;
    var nickname = Array.prototype.slice.call(decoded.nickname).concat([f.nickname11, f.nickname12]);
    var values = Object.assign({}, f, { personality: decoded.personality, otId: decoded.otId });
    values.isEgg = (f.isEgg || f.s3IsEgg) ? 1 : 0;
    return monSummary(values, nickname);
  }

  // A 60-byte packed PC record, or null when UnpackBoxMon would not give a Pokémon.
  function unpackBoxMon(record) {
    var packed = bytesToBig(record, 0, BOX_MON_SIZE);
    if (packed === 0n) return null;
    var values = {};
    PACKED_FIELDS.forEach(function (field) {
      values[field[0]] = Number((packed >> BigInt(field[1])) & ((1n << BigInt(field[2])) - 1n));
    });
    if (values.isBadEgg || values.species === 0) return null;
    var nickname = [];
    for (var i = 0; i < 12; i++) nickname.push(values['nickname' + i]);
    return monSummary(values, nickname);
  }

  // Every Pokémon in a .sav/.srm from any release: party, PC boxes and Day
  // Care, in that order. Eggs are included and marked; Bad Eggs are not.
  function readSaveFile(fileBytes) {
    var found = findFlashImage(fileBytes);
    var format = detectFormat(found.image);
    if (format === 'empty') throw new Error('This file does not contain a Pokémon Emerald save.');

    var saveBlock1, boxRecords, boxRecordSize, readRecord, loadFlags = {};
    if (format === '2.1') {
      var loaded = loadV21Image(found.image);
      saveBlock1 = loaded.saveBlock1;
      boxRecords = loaded.boxes;
      boxRecordSize = BOX_MON_SIZE;
      readRecord = unpackBoxMon;
      loadFlags = loaded.loadFlags;
    } else {
      var legacy = loadLegacyImage(found.image);
      saveBlock1 = legacy.saveBlock1;
      boxRecords = legacy.storage.subarray(LEGACY_BOXES_OFFSET, LEGACY_BOXES_OFFSET + LEGACY_TOTAL_BOXES * IN_BOX_COUNT * 80);
      boxRecordSize = 80;
      readRecord = readBoxMon;
    }

    var pokemon = [], mon, start, slot;
    var partyCount = Math.min(saveBlock1[SB1_PARTY_COUNT], PARTY_SIZE);
    for (slot = 0; slot < partyCount; slot++) {
      start = SB1_PARTY + slot * POKEMON_SIZE;
      mon = readBoxMon(saveBlock1.subarray(start, start + 80));
      if (!mon) continue;
      mon.place = 'party';
      mon.slot = slot;
      mon.level = saveBlock1[start + POKEMON_LEVEL_OFFSET];
      pokemon.push(mon);
    }
    for (var index = 0; index * boxRecordSize < boxRecords.length; index++) {
      mon = readRecord(boxRecords.subarray(index * boxRecordSize, (index + 1) * boxRecordSize));
      if (!mon) continue;
      mon.place = 'box';
      mon.box = Math.floor(index / IN_BOX_COUNT);
      mon.slot = index % IN_BOX_COUNT;
      pokemon.push(mon);
    }
    for (slot = 0; slot < DAYCARE_MON_COUNT; slot++) {
      start = SB1_DAYCARE + slot * DAYCARE_MON_SIZE;
      mon = readBoxMon(saveBlock1.subarray(start, start + 80));
      if (!mon) continue;
      mon.place = 'daycare';
      mon.slot = slot;
      pokemon.push(mon);
    }
    return { format: format, loadFlags: loadFlags, saveBlock1: saveBlock1, pokemon: pokemon };
  }

  function readSaveFlag(saveBlock1, flag) {
    return (saveBlock1[SB1_FLAGS + (flag >> 3)] >> (flag & 7)) & 1;
  }

  function readSaveVar(saveBlock1, id) {
    return readU16(saveBlock1, SB1_VARS + 2 * (id - VARS_START));
  }

  var api = {
    convertSaveFile: convertSaveFile,
    packBoxMon: packBoxMon,
    loadLegacyImage: loadLegacyImage,
    loadImage: loadImage,
    loadV21Image: loadV21Image,
    readSaveFile: readSaveFile,
    readSaveFlag: readSaveFlag,
    readSaveVar: readSaveVar,
    detectFormat: detectFormat,
    sectorCrc: sectorCrc
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.BPESaveConverter = api;

  // Page ---------------------------------------------------------------------------

  if (typeof document === 'undefined') return;
  var input = document.getElementById('save-converter-file');
  var button = document.getElementById('save-converter-button');
  var status = document.getElementById('save-converter-status');
  var backedUp = document.getElementById('save-converter-backed-up');
  if (!input || !button || !status) return;
  var chosen = null;

  // Converting never touches the file the player chose, but someone who
  // discards the original cannot go back to an earlier version of the game,
  // so the button waits for the promise as well as the file.
  function canConvert() {
    return Boolean(chosen) && (!backedUp || backedUp.checked);
  }

  function refreshButton() {
    button.disabled = !canConvert();
  }

  function promptForBackup() {
    setStatus('ready', chosen && !canConvert()
      ? 'Back up your save file, then tick the box above.'
      : '');
  }

  function setStatus(state, message) {
    status.className = 'is-' + state;
    status.textContent = message || '';
    status.hidden = !message;
  }

  input.addEventListener('change', function () {
    chosen = input.files && input.files[0];
    refreshButton();
    promptForBackup();
  });

  if (backedUp) {
    backedUp.addEventListener('change', function () {
      refreshButton();
      promptForBackup();
    });
  }

  button.addEventListener('click', async function () {
    if (!canConvert()) return;
    button.disabled = true;
    setStatus('working', 'Converting…');
    try {
      var bytes = new Uint8Array(await chosen.arrayBuffer());
      var result = convertSaveFile(bytes);
      var name = chosen.name.replace(/\.(sav|srm)$/i, '') + '_2.1.0' + (/\.srm$/i.test(chosen.name) ? '.srm' : '.sav');
      var url = URL.createObjectURL(new Blob([result.bytes], { type: 'application/octet-stream' }));
      var link = document.createElement('a');
      link.href = url;
      link.download = name;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 10000);
      var message = 'Converted: ' + result.report.pcPokemon + ' PC Pokémon. Keep your original save.';
      if (result.report.droppedBadEggs) message += ' ' + result.report.droppedBadEggs + ' Bad Egg(s) were removed.';
      setStatus('success', message);
    } catch (error) {
      setStatus('error', error.message || 'This save could not be converted.');
    } finally {
      refreshButton();
    }
  });
}(typeof window !== 'undefined' ? window : globalThis));
