"""
parse_suggestions.py
Reads the Discord #suggestions JSON export and produces a prioritized SUGGESTIONS.md.

Run from expansion root:
    py BPETools/parse_suggestions.py
"""

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
MESSAGES_DIR = ROOT / "discord messages"
SUGG_JSON = MESSAGES_DIR / "Pokemon Black Pearl Emerald - Text Channels - suggestions [1276579601555918920].json"
OUTPUT_MD = MESSAGES_DIR / "SUGGESTIONS.md"

# ── Load ───────────────────────────────────────────────────────────────────────
with open(SUGG_JSON, encoding="utf-8") as f:
    data = json.load(f)

messages = data["messages"]
msg_map = {m["id"]: m for m in messages}

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
NOISE_PREFIXES = (
    "thank", "thanks", "ty ", "ty!", "lol", "lmao", "haha",
    "nice", "cool", "ok ", "okay", "yep", "yeah,", "yeah ",
    "all good", "alright", "gotcha", "got it", "makes sense",
    "same here", "same!", "me too", "noted", "understood",
    "will do", "np ", "no problem", "fair enough", "agreed",
    "sounds good", "great", "perfect", "good to know",
    "also i have", "i have another",
)
NOISE_EXACT = {
    "same", "noted", "thanks", "thank you", "ty", "ok", "okay", "yep",
    "yeah", "lol", "nice", "great", "cool", "np", "agreed", "true",
    "understood", "gotcha", "alright", "sure", "nope", "yes", "no",
    "haha", "lmao", "wow", "oh", "ah", "hmm", "oof", "rip",
    "fix this", "please", "pls",
}
NOISE_TOO_VAGUE = (
    "fix this",
    "also i have another",
    "i have another one",
    "steamrolling gyms",       # follow-up context, not standalone suggestion
    "or intentionally hard",   # partial follow-up
    "or intentionally ",
    "nothing is better than",  # off-topic comment
    "pat yourself on the back",
    "rules channel",           # Discord server meta, not game suggestion
    "idk if there's a more appropriate",  # "review" not suggestion
)

def is_noise(content: str) -> bool:
    stripped = content.strip().lower()
    # Strip leading emoji characters before checking
    stripped_no_emoji = re.sub(r"^[\U00010000-\U0010ffff\U00002600-\U000027ff\s]+", "", stripped).strip()
    if stripped_no_emoji in NOISE_EXACT or stripped in NOISE_EXACT:
        return True
    if stripped.startswith(NOISE_PREFIXES) or stripped_no_emoji.startswith(NOISE_PREFIXES):
        return True
    for p in NOISE_TOO_VAGUE:
        if stripped.startswith(p) or stripped_no_emoji.startswith(p):
            return True
    if len(stripped) < 10:
        return True
    return False

def is_staff_comment(msg, content: str) -> bool:
    """Staff replies/clarifications that aren't suggestions themselves."""
    if not is_staff(msg):
        return False
    c = content.lower()
    comment_patterns = [
        "actually,", "actually ", "that's already", "this is already",
        "we already", "already implemented", "already in the game",
        "not planned", "won't be adding", "wont be adding",
        "noted,", "good idea", "will consider", "considering",
        "maybe in", "possibly in", "steamrolling",
    ]
    for p in comment_patterns:
        if c.startswith(p):
            return True
    if len(content) < 60 and not any(kw in c for kw in ("add", "include", "implement", "change", "allow", "option", "feature", "new", "more")):
        return True
    return False

# ── Category classification ────────────────────────────────────────────────────
CATEGORY_KW = {
    "New Content/Areas": [
        "add", "abandoned ship", "new area", "new location", "new region",
        "new town", "new route", "new dungeon", "new cave", "post game",
        "post-game", "endgame", "end game", "legendary", "mythical",
        "shaymin", "arceus", "mew", "mewtwo", "jirachi", "deoxys",
        "dialga", "palkia", "giratina", "extra content",
    ],
    "Pokémon/Roster": [
        "pokemon", "mon ", " mon,", "species", "starter", "roster",
        "encounter", "wild", "evo line", "evolution line", "add more pokemon",
        "catch", "obtainable", "dex", "form ", "regional form",
        "hisuian", "galarian", "alolan", "paldean",
        "paradox", "ultra beast",
    ],
    "QoL / Accessibility": [
        "qol", "quality of life", "option", "toggle", "setting", "mode",
        "skip", "speed up", "fast", "repel", "infinite repel",
        "level cap", "exp cap", "xp cap", "remove the cap",
        "no cap", "without cap", "optional", "accessibility",
        "easier", "less grindy", "grind", "rng",
        "casual", "nuzlocke", "nuzlocke mode",
    ],
    "Balance/Moves": [
        "balance", "move", "accuracy", "buff", "nerf", "op ", "overpowered",
        "too strong", "too weak", "underpowered", "broken", "unfair",
        "difficulty", "hard", "harder", "easier",
        "gym", "boss", "trainer team", "team composition",
        "zen headbutt", "air slash", "sub 100", "inaccurate",
        "base power", "bp ", "stat ", "stats",
    ],
    "Items/TMs": [
        "item", "tm", "hm", "held item", "key item", "bag",
        "nature changer", "nature mint", "mint", "repel",
        "infinite repel", "move reminder", "move deleter",
        "shop", "mart", "buy", "sell", "price", "cost",
        "master ball", "rare candy",
    ],
    "Features/Systems": [
        "feature", "system", "mechanic", "dexnav", "pokeradar", "radar",
        "running shoes", "poketch", "following", "follower",
        "nuzlocke", "randomizer", "wondertrade", "wonder trade",
        "battle frontier", "safari", "contest",
        "nature changer", "ev training", "ev ", "iv ",
        "shiny", "shiny charm", "shiny odds", "shiny rate",
    ],
    "Graphics/Sprites": [
        "sprite", "graphic", "visual", "art", "overworld sprite",
        "model", "animation", "palette", "color", "colour",
        "portrait", "icon", "tile", "map visual",
    ],
    "Story/Scripts": [
        "story", "plot", "script", "dialogue", "lore",
        "character", "rival", "champion", "gym leader",
        "pokepaste", "pokerogue", "difficulty narrative",
        "text", "flavor text",
    ],
    "Audio": [
        "music", "sound", "sfx", "audio", "song", "bgm",
        "cry", "soundtrack", "ost",
    ],
    "Documentation": [
        "doc", "docs", "documentation", "wiki", "guide", "readme",
        "pokepaste", "spreadsheet", "list of", "changelog",
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
    return "General"

# ── Priority based on reactions + community weight ─────────────────────────────
def priority_tier(reactions: int, merged: int, confirms: int) -> str:
    score = reactions + (merged - 1) * 3 + confirms * 2
    if score >= 8:
        return "Popular"
    if score >= 3:
        return "Requested"
    return "Noted"

# ── Named-entity cluster seeds ─────────────────────────────────────────────────
ENTITY_SEEDS = [
    ("Level cap removal / optional toggle",
     ["level cap", "exp cap", "xp cap", "remove the cap", "remove cap",
      "no level cap", "without level cap", "optional level cap",
      "a non level cap", "overlevel", "over level"]),
    ("Abandoned Ship area",
     ["abandoned ship"]),
    ("Infinite Repel / Repel Key Item",
     ["infinite repel", "repel key", "repel item", "repel as a key"]),
    ("DexNav feature",
     ["dexnav", "dex nav", "pokeradar", "poke radar"]),
    ("Nature Changer NPC / item",
     ["nature changer", "nature mint", "change nature", "change my nature"]),
    ("Pokepastes / team docs for gym leaders",
     ["pokepaste", "poke paste", "gym leader team", "rival team doc"]),
    ("Shaymin / Shaymin-Sky obtainability",
     ["shaymin"]),
    ("Move accuracy fixes (Zen Headbutt / Air Slash)",
     ["zen headbutt", "air slash", "sub 100", "inaccurate move",
      "unnecessarily inaccurate"]),
    ("Shiny odds / Shiny Charm",
     ["shiny charm", "shiny odds", "shiny rate", "shiny chance"]),
    ("Battle Frontier / post-game content",
     ["battle frontier", "post-game", "post game content", "endgame content", "post game area"]),
    ("EV / IV training tools",
     ["ev training", "ev room", "iv checker", "iv check", " ev ", " iv "]),
    ("Nuzlocke mode / built-in support",
     ["nuzlocke mode", "nuzlocke support", "built-in nuzlocke"]),
    ("Poketch / town map QoL",
     ["poketch", "town map", "map upgrade"]),
    ("Follower Pokémon improvements",
     ["follower", "following pokemon", "pokemon follow"]),
    ("Wonder Trade",
     ["wonder trade", "wondertrade"]),
    ("Contest improvements",
     ["contest", "pokemon contest"]),
    ("Hard mode / difficulty option",
     ["hard mode", "difficulty option", "difficulty setting", "difficulty toggle",
      "harder", "more difficult", "challenge mode"]),
    ("Safari Zone improvements",
     ["safari zone", "safari"]),
    ("Pokémon Randomizer",
     ["randomizer", "random mode", "random pokemon"]),
]

def entity_seed(text: str):
    tl = text.lower()
    for label, triggers in ENTITY_SEEDS:
        for t in triggers:
            if t in tl:
                return label
    return None

# ── Jaccard dedup ──────────────────────────────────────────────────────────────
STOPWORDS = {
    "the","a","an","is","it","in","on","to","of","i","and","or","but","be",
    "was","are","for","with","this","that","have","not","do","did","my","me",
    "we","they","so","if","as","at","by","no","can","you","he","she","has",
    "had","will","would","could","should","when","what","where","how","been",
    "its","from","just","also","there","then","up","out","get","all","your",
    "than","more","some","any","after","before","about","into","very",
    "like","ive", "im","doesnt","dont","cant","wont","isnt","wasnt",
    "pokemon","bpe","emerald","black","pearl","game","playing","play",
    "hey","guys","anyone","does","someone","hi","hello","please","pls",
    "add","think","would","really","maybe","could","should",
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

# ── Build suggestion entries ───────────────────────────────────────────────────
class Suggestion:
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
        self.category = category(self.content)
        self.date = parse_date(lead_msg["timestamp"])
        self.author = lead_msg["author"].get("nickname") or lead_msg["author"].get("name", "?")
        self.merged_count = 1

    def weight(self) -> int:
        return self.reactions + (self.merged_count - 1) * 3 + self.confirms * 2

    def priority(self) -> str:
        return priority_tier(self.reactions, self.merged_count, self.confirms)

# ── Pass 1: filter noise ───────────────────────────────────────────────────────
valid_top = []
for m in top_level:
    content = m.get("content", "").strip()
    if not content:
        continue
    if is_noise(content):
        continue
    if is_staff_comment(m, content):
        continue
    valid_top.append(m)

# ── Pass 2: entity-seed clustering ────────────────────────────────────────────
seed_groups: dict[str, list] = defaultdict(list)
no_seed = []

for m in valid_top:
    seed = entity_seed(m.get("content", ""))
    if seed:
        seed_groups[seed].append(m)
    else:
        no_seed.append(m)

entity_suggs: list[Suggestion] = []
for label, msgs in seed_groups.items():
    # Prefer non-staff messages; among those, pick highest reactions then most detailed
    non_staff = [m for m in msgs if not is_staff(m)] or msgs
    lead = max(non_staff, key=lambda m: (reaction_count(m), len(m.get("content", ""))))
    s = Suggestion(lead, override_title=label)
    s.merged_count = len(msgs)
    s.reactions = sum(reaction_count(x) for x in msgs) + sum(
        reaction_count(r) for m in msgs for r in reply_map.get(m["id"], [])
    )
    combined = " ".join(m.get("content", "") for m in msgs)
    s.category = category(combined)
    entity_suggs.append(s)

# ── Pass 3: Jaccard dedup on remaining ────────────────────────────────────────
remaining = [Suggestion(m) for m in no_seed]
used = [False] * len(remaining)
deduped: list[Suggestion] = []

for i, s in enumerate(remaining):
    if used[i]:
        continue
    head = s
    for j in range(i + 1, len(remaining)):
        if used[j]:
            continue
        other = remaining[j]
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

all_suggs = entity_suggs + deduped

# Sort by weight descending (reactions + merged count)
all_suggs.sort(key=lambda s: -s.weight())

# Group into priority tiers
tiers: dict[str, list[Suggestion]] = {"Popular": [], "Requested": [], "Noted": []}
for s in all_suggs:
    tiers[s.priority()].append(s)

# ── Render markdown ────────────────────────────────────────────────────────────
export_date = data.get("exportedAt", "")[:10]
msg_count = data.get("messageCount", len(messages))

def make_title(s: Suggestion) -> str:
    if s.title_override:
        return s.title_override
    first_line = s.content.split("\n")[0].strip()
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
lines.append("# BPE Emerald -- Suggestions")
lines.append(f"_Condensed from Discord #suggestions ({msg_count} messages, exported {export_date})_")
lines.append(f"_Distinct suggestions after deduplication: **{len(all_suggs)}**_")
lines.append("")
lines.append("## Summary")
lines.append("")
lines.append("| Priority | Count |")
lines.append("|----------|-------|")
for tier in ("Popular", "Requested", "Noted"):
    lines.append(f"| {tier} | {len(tiers[tier])} |")
lines.append("")
lines.append("---")
lines.append("")

TIER_DESCRIPTIONS = {
    "Popular": "High community interest (many reactions / repeated requests)",
    "Requested": "Some community support",
    "Noted": "Single suggestions, no reactions",
}

for tier in ("Popular", "Requested", "Noted"):
    if not tiers[tier]:
        continue
    lines.append(f"## {tier}")
    lines.append(f"_{TIER_DESCRIPTIONS[tier]}_")
    lines.append("")

    for s in tiers[tier]:
        title = make_title(s)
        lines.append(f"### {title}")

        support_parts = []
        if s.merged_count > 1:
            support_parts.append(f"{s.merged_count} similar requests")
        if s.reactions > 0:
            support_parts.append(f"{s.reactions} reactions")
        if s.confirms > 0:
            support_parts.append(f"{s.confirms} follow-ups")
        support_str = ", ".join(support_parts) if support_parts else "1 request"

        lines.append(f"- **Category:** {s.category}")
        lines.append(f"- **Support:** {support_str}")
        lines.append(f"- **Suggested:** {s.date} by {s.author}")

        title_plain = title.rstrip("...").lower().strip()
        content_summary = make_details(s.content)
        if content_summary.lower().strip() != title_plain:
            if not s.title_override or len(s.content) > 60:
                lines.append(f"- **Details:** {content_summary}")

        lines.append("")

output = "\n".join(lines)
OUTPUT_MD.write_text(output, encoding="utf-8")

print(f"Written: {OUTPUT_MD}")
print(f"Input:   {msg_count} messages -> {len(top_level)} top-level -> {len(valid_top)} after noise filter")
print(f"Output:  {len(entity_suggs)} entity-clustered + {len(deduped)} deduped = {len(all_suggs)} total")
print(f"Tiers:   Popular={len(tiers['Popular'])}, Requested={len(tiers['Requested'])}, Noted={len(tiers['Noted'])}")
