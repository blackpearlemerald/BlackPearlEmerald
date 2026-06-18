"""
take_screenshots.py  --  Generate Pokédex screenshots using headless Chrome.

Creates temporary HTML files with inline data (bypassing async fetches),
then uses Chrome headless to screenshot them.

Usage: py take_screenshots.py
"""

import json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE.parent / "site"
DATA = SITE / "data"
OUT  = HERE.parent   # BPEDocumentation/

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

# ── helpers ──────────────────────────────────────────────────────────────────

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def js_literal(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

def make_fetch_override(*pairs):
    """Return a <script> block that overrides fetch() for given (url_substring, data) pairs."""
    cases = "\n".join(
        f'        if(url&&url.includes({json.dumps(sub)})){{return Promise.resolve({{ok:true,json:()=>Promise.resolve({js_literal(data)})}});}}'
        for sub, data in pairs
    )
    return f"""<script>
(function(){{
  var _f=window.fetch.bind(window);
  window.fetch=function(url){{
{cases}
    return _f.apply(this,arguments);
  }};
}})();
</script>"""

def patch_html(original_html, fetch_override_script, inject_before_tag):
    """Inject fetch override before the last JS script tag."""
    return original_html.replace(inject_before_tag, fetch_override_script + "\n" + inject_before_tag, 1)

TEMP_PROFILE = Path(os.environ.get("TEMP", "C:/Temp")) / "chrome_bpe_screenshot_profile"

def run_headless(url, out_png, window_size="1280,900"):
    tmp = out_png.parent / (out_png.stem + "_tmp.png")
    if tmp.exists():
        tmp.unlink()
    cmd = [
        CHROME,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--no-first-run",
        "--disable-extensions",
        f"--user-data-dir={TEMP_PROFILE}",
        f"--window-size={window_size}",
        f"--screenshot={tmp}",
        "--hide-scrollbars",
        "--virtual-time-budget=3000",
        url,
    ]
    print(f"  Running headless Chrome -> {tmp.name} ...")
    try:
        subprocess.run(cmd, capture_output=True, timeout=45)
    except subprocess.TimeoutExpired:
        print("  (timeout — checking output file anyway)")
    if tmp.exists() and tmp.stat().st_size > 5000:
        tmp.replace(out_png)
        print(f"  Saved: {out_png.name}  ({out_png.stat().st_size // 1024} KB)")
        return True
    else:
        print(f"  FAILED (size={tmp.stat().st_size if tmp.exists() else 0})")
        if tmp.exists():
            tmp.unlink()
        return False

# ── listing page ─────────────────────────────────────────────────────────────

def screenshot_listing():
    print("[1] Pokédex listing page ...")
    index_full = load_json(DATA / "pokedex_index.json")
    # Trim to first 200 by natDexNum for screenshot (avoids Chrome crashing on 603KB inline JSON)
    sorted_keys = sorted(index_full.keys(),
        key=lambda k: (index_full[k].get("natDexNum") or 99999, k))
    index = {k: index_full[k] for k in sorted_keys[:200]}
    orig  = (SITE / "pokedex.html").read_text(encoding="utf-8")

    override = make_fetch_override(("pokedex_index.json", index))
    patched = patch_html(orig, override, '<script src="js/pokedex.js"></script>')

    tmp_html = SITE / "_screenshot_listing.html"
    tmp_html.write_text(patched, encoding="utf-8")

    url = "http://localhost:8766/_screenshot_listing.html"
    ok = run_headless(url, OUT / "screenshot_pokedex_listing.png")
    tmp_html.unlink(missing_ok=True)
    return ok

# ── detail page (top: stats + evo) ───────────────────────────────────────────

def screenshot_detail(species_key="CHARIZARD"):
    print(f"[2] Pokédex detail page ({species_key}) ...")
    species_file = DATA / "species" / f"{species_key}.json"
    if not species_file.exists():
        print(f"  Species file not found: {species_file}")
        return False

    species = load_json(species_file)
    moves   = load_json(DATA / "moves.json")
    abilities = load_json(DATA / "abilities.json")
    index   = load_json(DATA / "pokedex_index.json")

    orig = (SITE / "pokemon.html").read_text(encoding="utf-8")
    override = make_fetch_override(
        (f"species/{species_key}.json", species),
        ("moves.json",    moves),
        ("abilities.json", abilities),
        ("pokedex_index.json", index),
    )
    patched = patch_html(orig, override, '<script src="js/pokemon.js"></script>')

    # Inject species id into URL via meta redirect or directly set location search
    # We'll inject a script that sets window.location.search before pokemon.js runs
    url_inject = f'<script>history.replaceState(null,"","?id={species_key}");</script>\n'
    patched = patch_html(patched, url_inject, '<script src="js/pokemon.js"></script>')

    tmp_html = SITE / "_screenshot_detail.html"
    tmp_html.write_text(patched, encoding="utf-8")

    url = f"http://localhost:8766/_screenshot_detail.html?id={species_key}"
    ok = run_headless(url, OUT / f"screenshot_pokedex_detail_{species_key.lower()}.png")
    tmp_html.unlink(missing_ok=True)
    return ok

# ── detail page scrolled down (learnset) ─────────────────────────────────────

def screenshot_detail_learnset(species_key="CHARIZARD"):
    """Take a tall screenshot (1280x2200) showing the full detail page inc. learnset table."""
    print(f"[3] Pokédex detail + learnset ({species_key}, tall view) ...")
    species_file = DATA / "species" / f"{species_key}.json"
    if not species_file.exists():
        return False

    species  = load_json(species_file)
    moves    = load_json(DATA / "moves.json")
    abilities = load_json(DATA / "abilities.json")
    index    = load_json(DATA / "pokedex_index.json")

    orig = (SITE / "pokemon.html").read_text(encoding="utf-8")
    override = make_fetch_override(
        (f"species/{species_key}.json", species),
        ("moves.json",    moves),
        ("abilities.json", abilities),
        ("pokedex_index.json", index),
    )
    patched = patch_html(orig, override, '<script src="js/pokemon.js"></script>')
    url_inject = f'<script>history.replaceState(null,"","?id={species_key}");</script>\n'
    patched = patch_html(patched, url_inject, '<script src="js/pokemon.js"></script>')

    tmp_html = SITE / "_screenshot_learnset.html"
    tmp_html.write_text(patched, encoding="utf-8")

    url = f"http://localhost:8766/_screenshot_learnset.html?id={species_key}"
    ok = run_headless(url, OUT / f"screenshot_pokedex_learnset_{species_key.lower()}.png",
                      window_size="1280,2200")
    tmp_html.unlink(missing_ok=True)
    return ok

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("BPE Pokédex screenshot tool")
    results = []
    results.append(screenshot_listing())
    results.append(screenshot_detail("CHARIZARD"))
    results.append(screenshot_detail_learnset("CHARIZARD"))

    print("\nDone.")
    for f in OUT.glob("screenshot_pokedex_*.png"):
        print(f"  {f.name}  ({f.stat().st_size // 1024} KB)")

if __name__ == "__main__":
    main()
