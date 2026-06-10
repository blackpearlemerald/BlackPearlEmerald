"""
parse_bug_reports.py
Reads the Discord #bug-reports JSON export and produces a prioritized BUG_REPORTS.md.

Run from expansion root:
    py BPETools/parse_bug_reports.py
"""

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
MESSAGES_DIR = ROOT / "discord messages"
BUG_JSON = MESSAGES_DIR / "Pokemon Black Pearl Emerald - Text Channels - bug-reports [1275927356216705118].json"
OUTPUT_MD = MESSAGES_DIR / "BUG_REPORTS.md"

# ── Load ───────────────────────────────────────────────────────────────────────
with open(BUG_JSON, encoding="utf-8") as f:
    data = json.load(f)

messages = data["messages"]
msg_map = {m["id"]: m for m in messages}

# ── Roles treated as dev/staff ─────────────────────────────────────────────────
STAFF_ROLES = {"Developer", "Admin", "Moderator", "Mod"}

def is_staff(msg):
    return any(r["name"] in STAFF_ROLES for r in msg["author"].get("roles", []))

def reaction_count(msg):
    return sum(r["count"] for r in msg.get("reactions", []))

def parse_date(ts):
    try:
        return datetime.fromisoformat(ts).strftime("%Y-%m-%d")
    except Exception:
        return ts[:10]

# ── Build thread chains ────────────────────────────────────────────────────────
reply_map: dict[str, list] = defaultdict(list)
top_level = []
for m in messages:
    ref = m.get("reference")
    if m["type"] == "Reply" and ref:
        reply_map[ref["messageId"]].append(m)
    else:
        top_level.append(m)

# ── Noise filter ───────────────────────────────────────────────────────────────
# Short acknowledgements and chat noise that are not bug reports
NOISE_PREFIXES = (
    "thank", "thanks", "ty ", "ty!", "lol", "lmao", "haha",
    "nice", "cool", "ok ", "okay", "yep", "yep,", "yeah,", "yeah ",
    "all good", "alright", "gotcha", "got it", "makes sense",
    "same here", "same!", "me too", "noted", "noted.", "understood",
    "will do", "np ", "no problem", "fair enough", "true", "true,",
    "good luck", "agreed", "same", "same.", "oh okay", "oh ok",
    "sounds good", "great", "perfect", "good to know",
)
NOISE_EXACT = {
    "same", "noted", "thanks", "thank you", "ty", "ok", "okay", "yep",
    "yeah", "lol", "nice", "great", "cool", "np", "agreed", "true",
    "understood", "gotcha", "alright", "sure", "nope", "yes", "no",
    "haha", "lmao", "wow", "oh", "ah", "hmm", "oof", "rip",
    "and magnitude",  # partial reply noise
}

def is_noise(content: str) -> bool:
    stripped = content.strip().lower()
    if stripped in NOISE_EXACT:
        return True
    if stripped.startswith(NOISE_PREFIXES):
        return True
    # Very short messages that don't describe a bug
    if len(stripped) < 20 and not any(c in stripped for c in ("crash", "freeze", "bug", "error", "broken", "wrong", "glitch", "stuck")):
        return True
    # Contextual confirmations that are clearly not standalone bug reports
    noise_phrases = (
        "freeze was a one time", "was a one time thing",
        "missing 4 in a row is",
        "i have a lycanroc too but",
    )
    for p in noise_phrases:
        if stripped.startswith(p):
            return True
    return False

# Staff-authored posts that read as dev notes/announcements, not user bug reports
# We keep staff posts that look like they're reporting known bugs (critical notices)
def is_dev_note(msg, content: str) -> bool:
    if not is_staff(msg):
        return False
    c = content.lower()
    # Dev clarification/explanation (not a bug report)
    clarification_patterns = [
        "its intentional", "it's intentional", "that's intentional",
        "this is intentional", "actually,", "actually ", "as a rule of thumb",
        "not recommended", "recommended for", "i've been told", "ive been told",
        "try ", "use ", "retroarch", "pizzaboy", "pizza boy",
        "sandyshocks has", "sandy shocks",
        "nothing insanely", "nothing game breaking", "lot of small things",
    ]
    for p in clarification_patterns:
        if c.startswith(p):
            return True
    # Short dev replies
    if len(content) < 80 and not any(kw in c for kw in ("softlock", "crash", "freeze", "broken", "do not", "don't")):
        return True
    return False

# ── Severity classification ────────────────────────────────────────────────────
CRITICAL_KW = [
    "softlock", "soft lock", "soft-lock",
    "crash", "crashing", "crashed", "crashes",
    "freeze", "freezes", "frozen", "freezing",
    "stuck forever", "stuck in a loop", "can't progress", "cannot progress",
    "infinite loop", "game breaking", "game-breaking", "gamebreaking",
    "white out loop", "whiteout loop", "hardlock", "hard lock",
    "game won't", "game wont", "can't get out", "cant get out",
    "locked out", "no way back", "no way to get back",
    "bad egg",
]
HIGH_KW = [
    "broken", "doesn't work", "does not work", "not working", "won't work",
    "doesn't work", "wont work", "doesnt work",
    "missing", "can't obtain", "unobtainable", "not obtainable",
    "wrong pokemon", "wrong mon", "wrong move", "wrong item", "wrong ability",
    "wrong type", "wrong stats", "wrong trainer", "wrong sprite",
    "won't evolve", "doesn't evolve", "wont evolve", "doesnt evolve",
    "can't catch", "can't use", "cannot use", "not usable",
    "not spawning", "won't spawn", "doesn't spawn",
    "evolution problem", "evolution issue", "evolve",
    "exp", "experience", "0 exp", "no exp", "level cap",
    "hm", "tm", "gym", "badge", "rival", "champion", "elite four", "e4",
    "wild encounter", "encounter rate",
    "item not", "item doesn't", "item wont",
]
MEDIUM_KW = [
    "text", "typo", "typo in", "spelling",
    "sprite", "graphic", "visual bug", "display bug",
    "palette", "color wrong", "colour wrong",
    "animation", "overlap", "z-fighting",
    "wrong name", "wrong text", "wrong dialogue", "missing text",
    "clipping", "off by", "slightly",
    "minor bug", "small bug", "little bug",
]

def severity(text: str) -> str:
    tl = text.lower()
    # Remove negated "game breaking" so it doesn't false-positive as Critical
    tl_check = re.sub(r"\b(?:not|nothing|no|isn't|isnt|wasn't|wasnt|nothing insanely)\s+(?:insanely\s+)?(?:really\s+)?game.?breaking", "", tl)
    # "Freeze-Dry" is a move name, not a game freeze — mask it before checking
    tl_check = tl_check.replace("freeze-dry", "FREEZEDRY").replace("freeze dry", "FREEZEDRY")
    for kw in CRITICAL_KW:
        if kw in tl_check:
            return "Critical"
    for kw in HIGH_KW:
        if kw in tl:
            return "High"
    for kw in MEDIUM_KW:
        if kw in tl:
            return "Medium"
    return "Medium"

# ── Category classification ────────────────────────────────────────────────────
CATEGORY_KW = {
    "Overworld": [
        "overworld", "map", "route", "town", "city", "walk", "surf", "fly",
        "bike", "door", "warp", "teleport", "taxi", "mr briney", "boat",
        "slateport", "rustboro", "petalburg", "dewford", "lavaridge",
        "fortree", "lilycove", "mossdeep", "sootopolis", "ever grande",
        "victory road", "safari zone", "trick house", "trick house quiz",
        "oldale", "verdanturf", "fallarbor", "weather institute",
        "poke mart", "pokemart", "pokemon center",
        "npc", "trainer blocked", "invisible wall",
    ],
    "Battle": [
        "battle", "fight", "move", "attack", "damage", "hp", "pp",
        "status", "faint", "tera", "terastallize", "mega", "z-move",
        "ability", "priority", "speed", "turn order", "critical hit",
        "accuracy", "evasion", "confusion", "paralysis",
        "burn ", "flinch", "recoil", "weather ", "sand ", "rain ", "sun ",
        "hail ", "snow ", "trick room", "terrain ",
    ],
    "Items": [
        "item", "held item", "key item", "bag ",
        "hm", "tm", "berry", "pokeball", "poke ball",
        "taxi ticket", "orb", "stone", "repel",
        "potion", "mart", "shop", "buy", "sell", "black glasses",
    ],
    "Scripts/Text": [
        "text", "script", "dialogue", "message box", "typo", "spelling",
        "says ", " says", "tells ", " tells", "wrong name", "wrong dialogue",
        "missing text", "speech", "caption", "trick house quiz",
        "question ", " question",
    ],
    "Graphics": [
        "sprite", "graphic", "visual", "palette", "color", "colour",
        "animation", "flicker", "overlap", "art", "icon",
        "portrait", "texture", "tile ", "model ", "overworld sprite",
    ],
    "Audio": [
        "music", "sound", "sfx", "audio", "song", "bgm", "cry",
        "volume", "silent", "mute", "noise", "crackling",
    ],
    "Pokémon/Species": [
        "evolution", "evolve", "catch", "encounter", "wild ",
        "legendary", "starter", "egg", "breed", "hatch",
        "pokedex", "dex count", "owned", "seen",
        "moveset", "learnset", "level up move",
        "zigzagoon", "lycanroc", "rockruff", "togekiss", "lusamine",
    ],
    "Follower": [
        "follower", "following pokemon", "overworld pokemon", "pokemon behind",
    ],
    "Emulator Compat": [
        "emulator", "myboy", "my boy", "mgba", "retroarch", "bizhawk",
        "visualboyadvance", "vba", "miyoo", "pizzaboy", "pizza boy",
        "compatibility", "android", "ios", "doesn't run on",
        "lag ", "speed hack", "fast forward",
    ],
}

def category(text: str) -> str:
    tl = text.lower()
    scores: dict[str, int] = defaultdict(int)
    for cat, kws in CATEGORY_KW.items():
        for kw in kws:
            if kw in tl:
                scores[cat] += 1
    if scores:
        return max(scores, key=lambda k: scores[k])
    return "Misc"

# ── Named-entity cluster seeds ─────────────────────────────────────────────────
# Each entry: (display_label, list_of_trigger_keywords)
# When 2+ top-level messages hit the same seed, they collapse into one entry.
ENTITY_SEEDS = [
    # crashes/freezes around a named entity
    ("Starter battle (Zigzagoon) crash/freeze",
     ["zigzagoon", "zigzagooon", "torchic", "torchick", "treecko", "mudkip",
      "pick my starter", "pick a starter", "picking starter", "picking my starter",
      "picking your starter", "picked my starter", "picked a starter",
      "first battle to save", "save the professor",
      "after i pick a starter", "after picking a starter",
      "when i pick my", "when i picked my"]),
    ("Lycanroc / Rockruff evolution freeze",
     ["lycanroc", "rockruff"]),
    ("Taxi Ticket softlock on Slateport Beach",
     ["taxi ticket", "taxi"]),
    ("MyBoy emulator incompatibility",
     ["myboy", "my boy"]),
    ("Miyoo Mini / hardware emulator audio issues",
     ["miyoo"]),
    ("Togekiss Calm Mind freeze",
     ["togekiss"]),
    ("Bad Egg crash (electric arena)",
     ["bad egg"]),
    ("Freeze-Dry accuracy issue (Sand Veil?)",
     ["freeze-dry", "freeze dry"]),
    ("Pokedex owned count wrong",
     ["pokedex", "pokédex", "owned but"]),
    ("EXP not gained after level 15",
     ["0 exp", "no exp", "takes 0", "exp after level", "every battle it takes"]),
    ("Wrong trainer sprite in Battle Tents",
     ["battle tent", "battle tents", "cynthia's sprite", "wrong character sprite"]),
    ("Lusamine portrait/art issue",
     ["lusamine"]),
    ("Trick House quiz typos",
     ["trick house quiz", "trick house - when", "ferris wheel", "farris wheel", "jigglybuff"]),
    ("Hidden trainer visible in 4th gym",
     ["hidden trainer", "fourth gym", "4th gym"]),
    ("Rival encounter issues",
     ["rival"]),
    ("Wallace / Champion room scripts",
     ["wallace"]),
    ("Level cap / experience formula issues",
     ["level cap", "exp cap", "experience cap"]),
    ("Wrong Pokemon in trainer teams",
     ["supposed to be a", "wrong pokemon", "wrong mon"]),
    ("Black Glasses NPC dialogue loop",
     ["black glasses"]),
    ("Sandy Shocks Gravity / Ground-move bug",
     ["sandyshocks", "sandy shocks", "sandy shock"]),
    ("Magnitude move issues",
     ["magnitude"]),
    ("Sand Veil evasion bug",
     ["sand veil"]),
]

def entity_seed(text: str):
    tl = text.lower()
    for label, triggers in ENTITY_SEEDS:
        for t in triggers:
            if t in tl:
                return label
    return None

# ── Jaccard dedup for remaining messages ──────────────────────────────────────
STOPWORDS = {
    "the","a","an","is","it","in","on","to","of","i","and","or","but","be",
    "was","are","for","with","this","that","have","not","do","did","my","me",
    "we","they","so","if","as","at","by","no","can","you","he","she","has",
    "had","will","would","could","should","when","what","where","how","been",
    "its","from","just","also","there","then","up","out","get","all","your",
    "than","more","some","any","after","before","about","into","very",
    "like","ive", "im","doesnt","dont","cant","wont","isnt","wasnt",
    "pokemon","bpe","emerald","black","pearl","game","playing","play",
    "hey","guys","anyone","anyone","does","someone","hi","hello",
}

def tokenize(text: str) -> set[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return {t for t in tokens if t not in STOPWORDS and len(t) > 2}

def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0

DEDUP_THRESHOLD = 0.30

# ── Build bug entries ──────────────────────────────────────────────────────────
class Bug:
    def __init__(self, lead_msg, override_title=None):
        self.lead = lead_msg
        self.replies = reply_map.get(lead_msg["id"], [])
        self.content = lead_msg.get("content", "").strip()
        self.title_override = override_title
        self.tokens = tokenize(self.content)
        self.reactions = reaction_count(lead_msg) + sum(reaction_count(r) for r in self.replies)
        self.confirms = sum(
            1 for r in self.replies
            if not is_staff(r) and len(r.get("content", "")) > 15
        )
        self.severity = severity(self.content)
        self.category = category(self.content)
        self.date = parse_date(lead_msg["timestamp"])
        self.author = lead_msg["author"].get("nickname") or lead_msg["author"].get("name", "?")
        self.merged_count = 1

    def weight(self) -> int:
        return self.reactions + self.confirms * 2 + (self.merged_count - 1) * 3

# ── Pass 1: filter noise ───────────────────────────────────────────────────────
valid_top = []
for m in top_level:
    content = m.get("content", "").strip()
    if not content:
        continue
    if is_noise(content):
        continue
    if is_dev_note(m, content):
        continue
    valid_top.append(m)

# ── Pass 2: entity-seed clustering ────────────────────────────────────────────
# Group messages by entity seed; the highest-reaction message in each seed becomes the lead
seed_groups: dict[str, list] = defaultdict(list)
no_seed = []

for m in valid_top:
    content = m.get("content", "").strip()
    seed = entity_seed(content)
    if seed:
        seed_groups[seed].append(m)
    else:
        no_seed.append(m)

entity_bugs: list[Bug] = []
for label, msgs in seed_groups.items():
    # Pick best lead: highest reactions, or longest content
    lead = max(msgs, key=lambda m: (reaction_count(m), len(m.get("content", ""))))
    bug = Bug(lead, override_title=label)
    bug.merged_count = len(msgs)
    # Aggregate reactions from all merged messages
    bug.reactions = sum(reaction_count(x) for x in msgs) + sum(
        reaction_count(r) for m in msgs for r in reply_map.get(m["id"], [])
    )
    # Re-derive severity/category from combined content
    combined = " ".join(m.get("content", "") for m in msgs)
    bug.severity = severity(combined)
    bug.category = category(combined)
    entity_bugs.append(bug)

# ── Pass 3: Jaccard dedup on remaining messages ───────────────────────────────
remaining_bugs = [Bug(m) for m in no_seed]
used = [False] * len(remaining_bugs)
deduped: list[Bug] = []

for i, bug in enumerate(remaining_bugs):
    if used[i]:
        continue
    head = bug
    for j in range(i + 1, len(remaining_bugs)):
        if used[j]:
            continue
        other = remaining_bugs[j]
        if jaccard(head.tokens, other.tokens) >= DEDUP_THRESHOLD:
            if other.reactions > head.reactions or (other.reactions == head.reactions and len(other.content) > len(head.content)):
                other.merged_count += head.merged_count
                other.reactions = max(other.reactions, head.reactions)
                other.confirms += head.confirms
                head = other
            else:
                head.merged_count += 1
                head.reactions = max(head.reactions, other.reactions)
                head.confirms += other.confirms
            used[j] = True
    deduped.append(head)
    used[i] = True

all_bugs = entity_bugs + deduped

# ── Sort ───────────────────────────────────────────────────────────────────────
SEV_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
all_bugs.sort(key=lambda c: (SEV_ORDER[c.severity], -c.weight()))

counts: dict[str, int] = defaultdict(int)
for b in all_bugs:
    counts[b.severity] += 1

# ── Render markdown ────────────────────────────────────────────────────────────
export_date = data.get("exportedAt", "")[:10]
msg_count = data.get("messageCount", len(messages))

def make_title(bug: Bug) -> str:
    if bug.title_override:
        return bug.title_override
    first_line = bug.content.split("\n")[0].strip()
    first_line = re.sub(r"[*_`#>]", "", first_line)
    if len(first_line) > 100:
        cut = first_line[:97].rsplit(" ", 1)[0]
        return cut + "..."
    return first_line

def make_details(content: str) -> str:
    cleaned = content.replace("\n", " ").strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    if len(cleaned) > 450:
        cut = cleaned[:447].rsplit(" ", 1)[0]
        return cut + "..."
    return cleaned

lines = []
lines.append("# BPE Emerald -- Bug Reports")
lines.append(f"_Condensed from Discord #bug-reports ({msg_count} messages, exported {export_date})_")
lines.append(f"_Distinct issues after deduplication: **{len(all_bugs)}**_")
lines.append("")
lines.append("## Summary")
lines.append("")
lines.append("| Severity | Count |")
lines.append("|----------|-------|")
for sev in ("Critical", "High", "Medium", "Low"):
    lines.append(f"| {sev} | {counts[sev]} |")
lines.append("")
lines.append("---")
lines.append("")

current_sev = None
for b in all_bugs:
    if b.severity != current_sev:
        current_sev = b.severity
        lines.append(f"## {current_sev}")
        lines.append("")

    title = make_title(b)
    lines.append(f"### {title}")

    report_parts = []
    if b.merged_count > 1:
        report_parts.append(f"{b.merged_count} similar reports")
    if b.reactions > 0:
        report_parts.append(f"{b.reactions} reactions")
    if b.confirms > 0:
        report_parts.append(f"{b.confirms} confirmations")
    report_str = ", ".join(report_parts) if report_parts else "1 report"

    lines.append(f"- **Category:** {b.category}")
    lines.append(f"- **Reports:** {report_str}")
    lines.append(f"- **First reported:** {b.date} by {b.author}")

    # Details: only if content adds info beyond the title
    title_plain = title.rstrip("...").lower().strip()
    content_summary = make_details(b.content)
    if content_summary.lower().strip() != title_plain:
        if not b.title_override or len(b.content) > 60:
            lines.append(f"- **Details:** {content_summary}")

    lines.append("")

output = "\n".join(lines)
OUTPUT_MD.write_text(output, encoding="utf-8")

print(f"Written: {OUTPUT_MD}")
print(f"Input:   {msg_count} messages -> {len(top_level)} top-level -> {len(valid_top)} after noise filter")
print(f"Output:  {len(entity_bugs)} entity-clustered + {len(deduped)} deduped = {len(all_bugs)} total bugs")
print(f"Severity: Critical={counts['Critical']}, High={counts['High']}, Medium={counts['Medium']}, Low={counts['Low']}")
