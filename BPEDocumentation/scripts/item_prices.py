"""What items cost in the game, read from the game source.

src/data/items.h writes many prices as config expressions (`(I_PRICE >= GEN_7)
? 3000 : 2100`), shared macros chosen by `#if` blocks (GEM_PRICE) or products
(`2000 * TREASURE_FACTOR`), so a price is only right once the preprocessor
branches and the expression are evaluated with the game's own config. This
module does that with a small C preprocessor and expression evaluator.

Since 2.2.3 the Verdanturf mart has its own, capped prices, and everything it
sells also sells back at a fraction of that capped price (GetVerdanturfMartPrice
and GetItemSellPrice in src/item.c). Older sources have neither, which
verdanturf_rules() reports as None.
"""
import re
from pathlib import Path

import common as C

REPO = Path(C.SRC_ROOT)


class Unknown(Exception):
    """An identifier the evaluator has no value for."""


# ── Source text ────────────────────────────────────────────────────────────────

def read_source(path):
    """File text with line continuations joined and comments removed."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    text = text.replace("\\\n", " ")
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


# ── C expressions ──────────────────────────────────────────────────────────────

TOKEN_RE = re.compile(r"\s*(0[xX][0-9A-Fa-f]+|\d+|[A-Za-z_]\w*|"
                      r"\|\||&&|==|!=|<=|>=|<<|>>|[-+*/%()<>!~?:|&^])")


def tokenize(expr):
    tokens, pos = [], 0
    expr = expr.rstrip()
    while pos < len(expr):
        m = TOKEN_RE.match(expr, pos)
        if not m:
            raise Unknown(expr[pos:])
        tokens.append(m.group(1))
        pos = m.end()
    return tokens


BINARY = [("||",), ("&&",), ("|",), ("^",), ("&",), ("==", "!="),
          ("<", "<=", ">", ">="), ("<<", ">>"), ("+", "-"), ("*", "/", "%")]


def evaluate(expr, macros, depth=0):
    """Integer value of a C constant expression. Identifiers are expanded
    through `macros` ({name: replacement text}); `defined X` is supported. An
    identifier with no value raises Unknown."""
    if depth > 32:
        raise Unknown(expr)
    tokens = tokenize(expr)
    pos = 0

    def peek():
        return tokens[pos] if pos < len(tokens) else None

    def take(expected=None):
        nonlocal pos
        token = peek()
        if token is None or (expected and token != expected):
            raise Unknown(expr)
        pos += 1
        return token

    def primary():
        token = take()
        if token == "(":
            value = ternary()
            take(")")
            return value
        if token in ("!", "~", "-", "+"):
            value = primary()
            return {"!": int(not value), "~": ~value, "-": -value, "+": value}[token]
        if token == "defined":
            paren = peek() == "("
            if paren:
                take("(")
            name = take()
            if paren:
                take(")")
            return int(name in macros)
        if token[0].isdigit():
            return int(token, 0)
        if token in macros:
            return evaluate(macros[token], macros, depth + 1)
        raise Unknown(token)

    def binary(level):
        if level == len(BINARY):
            return primary()
        value = binary(level + 1)
        while peek() in BINARY[level]:
            op = take()
            rhs = binary(level + 1)
            if op in ("/", "%") and rhs == 0:
                raise Unknown(expr)
            value = {
                "||": lambda a, b: int(bool(a) or bool(b)),
                "&&": lambda a, b: int(bool(a) and bool(b)),
                "|": lambda a, b: a | b, "^": lambda a, b: a ^ b,
                "&": lambda a, b: a & b,
                "==": lambda a, b: int(a == b), "!=": lambda a, b: int(a != b),
                "<": lambda a, b: int(a < b), "<=": lambda a, b: int(a <= b),
                ">": lambda a, b: int(a > b), ">=": lambda a, b: int(a >= b),
                "<<": lambda a, b: a << b, ">>": lambda a, b: a >> b,
                "+": lambda a, b: a + b, "-": lambda a, b: a - b,
                "*": lambda a, b: a * b,
                "/": lambda a, b: int(a / b), "%": lambda a, b: a % b,
            }[op](value, rhs)
        return value

    def ternary():
        condition = binary(0)
        if peek() != "?":
            return condition
        take("?")
        yes = ternary()
        take(":")
        no = ternary()
        return yes if condition else no

    value = ternary()
    if pos != len(tokens):
        raise Unknown(expr)
    return value


# ── Preprocessor ───────────────────────────────────────────────────────────────

DEFINE_RE = re.compile(r"\s*#\s*define\s+(\w+)(?!\()\s*(.*)")
DIRECTIVE_RE = re.compile(r"\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b\s*(.*)")


def preprocess(text, macros):
    """Keep the lines of `text` that the game compiles, collecting object-like
    #defines into `macros` as it goes. A condition the evaluator cannot decide
    keeps every branch, so nothing is lost when a config is not known."""
    out, frames = [], []
    active = True
    for line in text.splitlines():
        directive = DIRECTIVE_RE.match(line)
        if directive:
            kind, expression = directive.groups()
            if kind in ("if", "ifdef", "ifndef"):
                if kind == "if":
                    try:
                        result = bool(evaluate(expression, macros))
                    except Unknown:
                        result = None
                else:
                    defined = expression.split()[0] in macros if expression.split() else False
                    result = defined if kind == "ifdef" else not defined
                frames.append({"parent": active, "known": result is not None,
                               "taken": bool(result)})
                active = active and (result is not False)
            elif kind == "elif" and frames:
                frame = frames[-1]
                if frame["known"]:
                    try:
                        result = bool(evaluate(expression, macros))
                    except Unknown:
                        result = True
                    active = frame["parent"] and not frame["taken"] and result
                    frame["taken"] = frame["taken"] or result
                else:
                    active = frame["parent"]
            elif kind == "else" and frames:
                frame = frames[-1]
                active = frame["parent"] and (not frame["taken"] if frame["known"] else True)
            elif kind == "endif" and frames:
                active = frames.pop()["parent"]
            continue
        if not active:
            continue
        define = DEFINE_RE.match(line)
        if define:
            macros.setdefault(define.group(1), define.group(2).strip())
            continue
        out.append(line)
    return "\n".join(out)


def config_macros(repo=None):
    """The game's config defines (GEN_*, TRUE/FALSE, include/config/*.h)."""
    repo = Path(repo or REPO)
    macros = {"TRUE": "1", "FALSE": "0"}
    paths = [repo / "include/config/general.h"]
    paths += sorted((repo / "include/config").glob("*.h")) if (repo / "include/config").is_dir() else []
    paths += [repo / "include/config.h", repo / "include/constants/global.h"]
    for path in paths:
        if path.is_file():
            preprocess(read_source(path), macros)
    return macros


# ── Items ──────────────────────────────────────────────────────────────────────

def item_blocks(text):
    """[(key, block)] for each [ITEM_KEY] = { ... } entry of gItemsInfo[]."""
    array = re.search(r"const struct Item(?:Info)? gItemsInfo\[\]\s*=\s*\{", text)
    if not array:
        raise ValueError("gItemsInfo[] not found in items.h")
    body, blocks = text[array.end():], []
    for m in re.finditer(r"\[ITEM_(\w+)\]\s*=\s*\{", body):
        depth, i = 1, m.end()
        while i < len(body) and depth:
            depth += {"{": 1, "}": -1}.get(body[i], 0)
            i += 1
        blocks.append((m.group(1), body[m.end():i - 1]))
    return blocks


def field(block, name):
    m = re.search(r"\.%s\s*=\s*([^,\n]+)" % name, block)
    return m.group(1).strip() if m else None


def load_items(repo=None):
    """{ITEM_KEY: {price, pocket, importance, fieldUseFunc}} as compiled."""
    repo = Path(repo or REPO)
    macros = config_macros(repo)
    text = preprocess(read_source(repo / "src/data/items.h"), macros)
    items = {}
    for key, block in item_blocks(text):
        if key in items:
            continue
        price = field(block, "price")
        try:
            price = evaluate(price, macros) if price else 0
        except Unknown:
            print(f"  ! cannot read the price of ITEM_{key}: {price}")
            price = 0
        importance = field(block, "importance")
        try:
            importance = evaluate(importance, macros) if importance else 0
        except Unknown:
            importance = 1
        func = field(block, "fieldUseFunc")
        while func in macros and macros[func] != func:   # EVO_HELD_ITEM_FIELD_FUNC
            func = macros[func]
        items[key] = {"price": max(price, 0), "pocket": field(block, "pocket"),
                      "importance": importance, "fieldUseFunc": func}
    return items, macros


# ── Shops ──────────────────────────────────────────────────────────────────────

def function_body(text, name):
    m = re.search(r"\b%s\s*\([^)]*\)\s*\{" % re.escape(name), text)
    if not m:
        return None
    depth, i = 1, m.end()
    while i < len(text) and depth:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    return text[m.end():i - 1]


def verdanturf_rules(repo=None):
    """The Verdanturf mart's caps as written in src/item.c, or None for a
    source without them: {cap, coin, berries, evolution, sweets, lists}."""
    repo = Path(repo or REPO)
    path = repo / "src/item.c"
    if not path.is_file():
        return None
    text = read_source(path)
    body = function_body(text, "GetVerdanturfMartPrice")
    if body is None:
        return None
    rules = {}
    m = re.search(r"\bcap\s*=\s*(\d+)\s*;", body)
    coin = re.search(r"itemId\s*==\s*ITEM_GIMMIGHOUL_COIN\s*\)\s*cap\s*=\s*(\d+)", body)
    berries = re.search(r"POCKET_BERRIES\s*\)\s*cap\s*=\s*(\d+)", body)
    evolution = re.search(r"IsEvolutionItem\(itemId\)\s*\)\s*cap\s*=\s*(\d+)", body)
    if not (m and coin and berries and evolution):
        # The rules changed shape; refuse rather than publish wrong prices.
        raise ValueError("GetVerdanturfMartPrice in src/item.c no longer matches item_prices.py")
    rules.update(cap=int(m.group(1)), coin=int(coin.group(1)),
                 berries=int(berries.group(1)), evolution=int(evolution.group(1)))
    rules["sweets"] = set(re.findall(r"case\s+ITEM_(\w+)\s*:",
                                     function_body(text, "IsEvolutionItem") or ""))
    lists = re.search(r"sVerdanturfMartLists\[\]\s*=\s*\{(.*?)\}", text, re.S)
    rules["lists"] = re.findall(r"\w+", lists.group(1)) if lists else []
    sell = function_body(text, "GetItemSellPrice") or ""
    rules["sellUsesVerdanturf"] = "IsSoldInVerdanturfMart" in sell
    return rules


def mart_list_items(repo, labels):
    """Every item on the named `pokemart` lists in data/maps/*/scripts.inc."""
    wanted, items = set(labels), set()
    if not wanted:
        return items
    for path in Path(repo, "data/maps").glob("*/scripts.inc"):
        text = path.read_text(encoding="utf-8", errors="replace")
        labels = list(re.finditer(r"^(\w+):{1,2}", text, re.M))
        for m, end in zip(labels, labels[1:] + [None]):
            if m.group(1) in wanted:
                body = text[m.end():end.start() if end else len(text)]
                items.update(re.findall(r"\.2byte\s+ITEM_(\w+)", body))
    return items


class Prices:
    """Buy and sell prices of every item, matching GetItemPrice,
    GetMartItemPrice and GetItemSellPrice."""

    def __init__(self, repo=None):
        repo = Path(repo or REPO)
        self.items, macros = load_items(repo)
        # ITEM_SELL_FACTOR moved from src/item_menu.c (1.0.1) to the constants.
        self.sell_factor = 2
        for path in (repo / "include/constants/item.h", repo / "src/item_menu.c"):
            m = path.is_file() and re.search(r"#define\s+ITEM_SELL_FACTOR\s+(.+)", read_source(path))
            if m:
                self.sell_factor = evaluate(m.group(1), macros)
                break
        # BPE 2.2.3 made a cheap sellable item sell for at least 1.
        item_c = repo / "src/item.c"
        sell = function_body(read_source(item_c), "GetItemSellPrice") if item_c.is_file() else None
        self.sell_minimum = bool(sell and "price < ITEM_SELL_FACTOR" in sell)
        self.verdanturf = verdanturf_rules(repo)
        self.verdanturf_items = (mart_list_items(repo, self.verdanturf["lists"])
                                 if self.verdanturf else set())

    def price(self, key):
        """What a normal mart charges (GetItemPrice)."""
        return self.items.get(key, {}).get("price", 0)

    def verdanturf_price(self, key):
        """What the Verdanturf mart charges, or None without its own prices."""
        if not self.verdanturf:
            return None
        rules, item = self.verdanturf, self.items.get(key, {})
        if key == "GIMMIGHOUL_COIN":
            cap = rules["coin"]
        elif item.get("pocket") == "POCKET_BERRIES":
            cap = rules["berries"]
        elif (item.get("fieldUseFunc") == "ItemUseOutOfBattle_EvolutionStone"
              or key in rules["sweets"]):
            cap = rules["evolution"]
        else:
            cap = rules["cap"]
        return min(self.price(key), cap)

    def mart_price(self, key, map_id):
        """What the mart on map_id charges (GetMartItemPrice)."""
        if map_id == "MAP_VERDANTURF_TOWN_MART" and self.verdanturf:
            return self.verdanturf_price(key)
        return self.price(key)

    def sell_price(self, key):
        """What the player gets for one, or 0 when it cannot be sold."""
        item = self.items.get(key, {})
        if not self.price(key) or item.get("importance"):
            return 0
        price = self.price(key)
        if (self.verdanturf and self.verdanturf["sellUsesVerdanturf"]
                and key in self.verdanturf_items):
            price = self.verdanturf_price(key)
        if self.sell_minimum and price and price < self.sell_factor:
            return 1
        return price // self.sell_factor
