"""Read generated teachable moves directly from source inputs, without a ROM build."""
import json
import re
from pathlib import Path


def build(root):
    root = Path(root)
    def read(path):
        return (root / path).read_text(encoding="utf-8")
    all_moves = json.loads(read("src/data/pokemon/all_learnables.json"))
    special = json.loads(read("src/data/pokemon/special_movesets.json"))
    tms = sorted(set("MOVE_" + m for m in re.findall(r"F\((\w+)\)", read("include/constants/tms_hms.h"))))
    tutors = set(special["extraTutors"])
    for path in list((root / "data/scripts").glob("*.inc")) + list((root / "data/maps").glob("*/scripts.inc")):
        text = path.read_text(encoding="utf-8")
        if "special ChooseMonForMoveTutor" in text or "chooseboxmon SELECT_PC_MON_MOVE_TUTOR" in text:
            tutors.update(re.findall(r"setvar VAR_0x8005, (MOVE_[A-Z_]*)", text))
            tutors.update(re.findall(r"move_tutor (MOVE_[A-Z_]*)", text))
    config = re.search(r"#define\s+P_TM_LITERACY\s+GEN_(\w+)", read("include/config/pokemon.h"))
    literate = config is not None and (config[1] == "LATEST" or int(config[1]) > 6)
    out, teaching = {"None": []}, "DEFAULT_LEARNING"
    paths = sorted((root / "src/data/pokemon/species_info").glob("*_families.h"))
    paths.append(root / "src/data/pokemon/species_info.h")
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            mode = re.match(r"\s*\.teachingType\s*=\s*([A-Z_]+),", line)
            if mode:
                teaching = mode[1]
            match = re.match(r"\s*\.teachableLearnset\s*=\s*s(\w+?)TeachableLearnset", line)
            if not match:
                continue
            name = match[1]
            key = re.sub(r"(?!^)([A-Z]+)", r"_\1", name).upper()
            if name not in out:
                candidates = tms + sorted(tutors)
                if teaching == "ALL_TEACHABLES":
                    allowed = set(candidates) - set(special["signatureTeachables"])
                else:
                    allowed = set(all_moves[key])
                    if teaching == "TM_ILLITERATE":
                        if not literate:
                            allowed -= set(special["universalMoves"])
                    else:
                        allowed.update(special["universalMoves"])
                if key == "TERAPAGOS":
                    allowed.discard("MOVE_TERA_BLAST")
                out[name] = list(dict.fromkeys(m.removeprefix("MOVE_") for m in candidates if m in allowed))
            teaching = "DEFAULT_LEARNING"
    return out
