"""Regenerate the entire interactive map site from the game source.

Read-only against the game tree; writes only under BPEDocumentation/site/.

Usage:  py build_all.py
"""
import argparse
import os


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    if args.source_root:
        os.environ["BPE_SOURCE_ROOT"] = os.path.abspath(args.source_root)
    if args.output_dir:
        os.environ["BPE_SITE_ROOT"] = os.path.abspath(args.output_dir)
    # Import after selecting roots: all modules derive their paths at import time.
    import common as C
    import parse_trainers
    import pokemon_sprites
    import render_maps
    import extract_world
    import parse_pokemon
    import parse_items
    import build_calc_data
    import build_features
    import build_trainer_ai
    import build_facilities
    C.ensure_dirs()
    print("[1/10] Parsing trainers ...")
    parse_trainers.main()
    print("[2/10] Extracting party Pokemon icons ...")
    pokemon_sprites.main()
    print("[3/10] Rendering map images ...")
    render_maps.main()
    print("[4/10] Extracting world layout + objects ...")
    extract_world.build()
    print("[5/10] Building Pokedex data ...")
    parse_pokemon.main()
    print("[6/10] Building Items data ...")
    parse_items.main()
    print("[7/10] Building damage-calculator data ...")
    build_calc_data.main()
    print("[8/10] Building Features page data ...")
    build_features.main()
    print("[9/10] Building Trainer AI page data ...")
    build_trainer_ai.main()
    print("[10/10] Building Battle Facilities page data ...")
    build_facilities.main()
    print("\nDone. Serve with:  py -m http.server -d ../site 8000")


if __name__ == "__main__":
    main()
