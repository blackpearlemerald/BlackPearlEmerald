"""Regenerate the entire interactive map site from the game source.

Read-only against the game tree; writes only under BPEDocumentation/site/.

Usage:  py build_all.py
"""
import common as C
import parse_trainers
import render_maps
import extract_world


def main():
    C.ensure_dirs()
    print("[1/3] Parsing trainers ...")
    parse_trainers.main()
    print("[2/3] Rendering map images ...")
    render_maps.main()
    print("[3/3] Extracting world layout + objects ...")
    extract_world.build()
    print("\nDone. Serve with:  py -m http.server -d ../site 8000")


if __name__ == "__main__":
    main()
