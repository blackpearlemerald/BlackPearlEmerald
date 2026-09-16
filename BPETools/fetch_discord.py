"""
fetch_discord.py
Fetches messages from the project's Discord channels through the OFFICIAL Discord
Bot API and writes JSON in the same shape the existing parsers already consume.

This talks to the Bot API with a bot token only. Every request sends
"Authorization: Bot <token>", which Discord accepts only from a real bot account,
so this script structurally cannot drive a personal user account. Automating a
user account is against Discord's Terms of Service; this is the supported path.

Setup (one time, done by the maintainer):
  1. https://discord.com/developers/applications -> New Application -> Bot.
  2. Enable the "Message Content Intent" under the bot's Privileged Gateway Intents.
  3. Invite the bot to the server with "View Channel" and "Read Message History".
  4. Put the bot token in the DISCORD_BOT_TOKEN environment variable, or in
     BPETools/discord.local.json (gitignored). Never commit the token.

Run from the repository root:
    python BPETools/fetch_discord.py --check
    python BPETools/fetch_discord.py --list-channels
    python BPETools/fetch_discord.py --all
    python BPETools/fetch_discord.py --channel bug-reports --days 120
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "https://discord.com/api/v10"
USER_AGENT = "DiscordBot (https://github.com/blackpearlemerald/BlackPearlEmerald, 1.0)"

ROOT = Path(__file__).parent
CONFIG_PATH = ROOT / "discord.local.json"
MESSAGES_DIR = ROOT / "discord messages"

# Discord message type ints -> the names the existing exports use.
# The parsers only branch on "Reply", the rest are for schema fidelity.
MESSAGE_TYPES = {
    0: "Default",
    1: "RecipientAdd",
    2: "RecipientRemove",
    3: "Call",
    4: "ChannelNameChange",
    5: "ChannelIconChange",
    6: "ChannelPinnedMessage",
    7: "GuildMemberJoin",
    19: "Reply",
    20: "ChatInputCommand",
    21: "ThreadStarterMessage",
    23: "ContextMenuCommand",
}

CHANNEL_TYPES = {
    0: "GuildTextChat",
    2: "GuildVoiceChat",
    4: "GuildCategory",
    5: "GuildNews",
    15: "GuildForum",
}


class DiscordError(RuntimeError):
    pass


# -- config -------------------------------------------------------------------

def load_config():
    """Token from the environment first, then the gitignored local file."""
    config = {}
    if CONFIG_PATH.exists():
        try:
            config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DiscordError(f"{CONFIG_PATH.name} is not valid JSON: {exc}") from exc

    token = os.environ.get("DISCORD_BOT_TOKEN") or config.get("token") or ""
    token = token.strip()
    if not token or token.startswith("PASTE"):
        raise DiscordError(
            "No bot token found. Set the DISCORD_BOT_TOKEN environment variable, or put\n"
            f'  {{"token": "<bot token>"}}\n'
            f"in {CONFIG_PATH}. That file is gitignored. Never commit a token."
        )
    if token.lower().startswith("bot "):
        token = token[4:].strip()
    config["token"] = token
    return config


# -- http ---------------------------------------------------------------------

def api_get(path, token, params=None, allow_404=False):
    """One GET against the Bot API, retrying on rate limits and transient errors."""
    url = f"{API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    for attempt in range(6):
        request = urllib.request.Request(url, method="GET")
        request.add_header("Authorization", f"Bot {token}")
        request.add_header("User-Agent", USER_AGENT)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                body = {}
                try:
                    body = json.loads(exc.read().decode("utf-8"))
                except Exception:
                    pass
                wait = float(body.get("retry_after", 2)) + 0.3
                print(f"    rate limited, waiting {wait:.1f}s", file=sys.stderr)
                time.sleep(wait)
                continue
            if exc.code == 401:
                raise DiscordError(
                    "Discord rejected the token (401). Check that it is a BOT token from the\n"
                    "Developer Portal, that it was copied whole, and that it was not reset."
                ) from exc
            if exc.code == 403:
                raise DiscordError(
                    f"Forbidden (403) for {path}. The bot is missing permission here. It needs\n"
                    "'View Channel' and 'Read Message History' on the channel."
                ) from exc
            if exc.code == 404:
                if allow_404:
                    return None
                raise DiscordError(
                    f"Not found (404) for {path}. Check the id, and that the bot is in that server."
                ) from exc
            if exc.code >= 500 and attempt < 5:
                time.sleep(2 ** attempt)
                continue
            raise DiscordError(f"Discord returned HTTP {exc.code} for {path}") from exc
        except urllib.error.URLError as exc:
            if attempt < 5:
                time.sleep(2 ** attempt)
                continue
            raise DiscordError(f"Could not reach Discord: {exc.reason}") from exc
    raise DiscordError(f"Gave up after repeated rate limits on {path}")


# -- conversion ---------------------------------------------------------------

def role_lookup(token, guild_id):
    """Map role id -> role record, so author roles carry names the parsers match on."""
    roles = api_get(f"/guilds/{guild_id}/roles", token)
    return {
        r["id"]: {
            "id": r["id"],
            "name": r["name"],
            "color": f"#{r['color']:06X}" if r.get("color") else None,
            "position": r.get("position", 0),
        }
        for r in roles
    }


def convert_author(message, roles, members, token, guild_id):
    user = message.get("author", {})
    member = message.get("member")
    user_id = user.get("id")

    if member is None and user_id and guild_id and user_id not in members:
        # Not every message object carries member data; look it up once per user.
        member = api_get(f"/guilds/{guild_id}/members/{user_id}", token, allow_404=True)
        members[user_id] = member
    elif member is None:
        member = members.get(user_id)

    role_ids = (member or {}).get("roles", []) or []
    author_roles = [roles[rid] for rid in role_ids if rid in roles]
    author_roles.sort(key=lambda r: r.get("position", 0), reverse=True)

    color = next((r["color"] for r in author_roles if r.get("color")), None)
    nickname = (member or {}).get("nick") or user.get("global_name") or user.get("username")

    return {
        "id": user_id,
        "name": user.get("username"),
        "discriminator": user.get("discriminator", "0000"),
        "nickname": nickname,
        "color": color,
        "isBot": bool(user.get("bot", False)),
        "roles": author_roles,
        "avatarUrl": (
            f"https://cdn.discordapp.com/avatars/{user_id}/{user['avatar']}.png?size=512"
            if user.get("avatar") else None
        ),
    }


def convert_message(message, roles, members, token, guild_id):
    reference = None
    ref = message.get("message_reference")
    if ref:
        reference = {
            "type": "Default",
            "messageId": ref.get("message_id"),
            "channelId": ref.get("channel_id"),
            "guildId": ref.get("guild_id"),
        }

    reactions = []
    for reaction in message.get("reactions", []) or []:
        emoji = reaction.get("emoji", {}) or {}
        reactions.append({
            "emoji": {
                "id": emoji.get("id") or "",
                "name": emoji.get("name") or "",
                "code": emoji.get("name") or "",
                "isAnimated": bool(emoji.get("animated", False)),
            },
            "count": reaction.get("count", 0),
            "users": [],
        })

    attachments = [
        {
            "id": a.get("id"),
            "url": a.get("url"),
            "fileName": a.get("filename"),
            "fileSizeBytes": a.get("size", 0),
        }
        for a in message.get("attachments", []) or []
    ]

    converted = {
        "id": message.get("id"),
        "type": MESSAGE_TYPES.get(message.get("type", 0), "Default"),
        "timestamp": message.get("timestamp"),
        "timestampEdited": message.get("edited_timestamp"),
        "callEndedTimestamp": None,
        "isPinned": bool(message.get("pinned", False)),
        "content": message.get("content", ""),
        "author": convert_author(message, roles, members, token, guild_id),
        "attachments": attachments,
        "embeds": message.get("embeds", []) or [],
        "stickers": message.get("sticker_items", []) or [],
        "reactions": reactions,
        "mentions": [
            {
                "id": u.get("id"),
                "name": u.get("username"),
                "discriminator": u.get("discriminator", "0000"),
                "nickname": u.get("global_name") or u.get("username"),
                "isBot": bool(u.get("bot", False)),
            }
            for u in message.get("mentions", []) or []
        ],
        "inlineEmojis": [],
    }
    # Only replies carry this key in the export format, and the parsers walk it
    # to chain follow-ups onto the report they answer.
    if reference:
        converted["reference"] = reference
    return converted


# -- fetching -----------------------------------------------------------------

def fetch_messages(token, channel_id, cutoff=None):
    """Page backwards through a channel. Returns raw API messages, oldest first."""
    collected = []
    before = None
    while True:
        params = {"limit": 100}
        if before:
            params["before"] = before
        batch = api_get(f"/channels/{channel_id}/messages", token, params)
        if not batch:
            break

        stop = False
        for message in batch:
            if cutoff:
                stamp = message.get("timestamp")
                if stamp and datetime.fromisoformat(stamp) < cutoff:
                    stop = True
                    continue
            collected.append(message)

        print(f"    fetched {len(collected)} messages", file=sys.stderr)
        if stop or len(batch) < 100:
            break
        before = batch[-1]["id"]
        time.sleep(0.3)

    collected.sort(key=lambda m: int(m["id"]))
    return collected


def export_filename(guild_name, category, channel_name, channel_id):
    parts = [guild_name]
    if category:
        parts.append(category)
    parts.append(f"{channel_name} [{channel_id}]")
    name = " - ".join(parts) + ".json"
    for bad in '<>:"/\\|?*':
        name = name.replace(bad, "_")
    return name


def export_channel(token, channel_id, days=None, out_dir=MESSAGES_DIR):
    channel = api_get(f"/channels/{channel_id}", token)
    guild_id = channel.get("guild_id")
    if not guild_id:
        raise DiscordError("That channel is not in a server. Only guild channels are supported.")

    guild = api_get(f"/guilds/{guild_id}", token)
    roles = role_lookup(token, guild_id)

    category = None
    if channel.get("parent_id"):
        parent = api_get(f"/channels/{channel['parent_id']}", token, allow_404=True)
        category = (parent or {}).get("name")

    cutoff = None
    if days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    print(f"  #{channel.get('name')} ({channel_id})", file=sys.stderr)
    raw = fetch_messages(token, channel_id, cutoff)

    members = {}
    messages = [convert_message(m, roles, members, token, guild_id) for m in raw]

    payload = {
        "guild": {
            "id": guild_id,
            "name": guild.get("name"),
            "iconUrl": (
                f"https://cdn.discordapp.com/icons/{guild_id}/{guild['icon']}.png?size=512"
                if guild.get("icon") else None
            ),
        },
        "channel": {
            "id": channel_id,
            "type": CHANNEL_TYPES.get(channel.get("type", 0), "GuildTextChat"),
            "categoryId": channel.get("parent_id"),
            "category": category,
            "name": channel.get("name"),
            "topic": channel.get("topic"),
        },
        "dateRange": {
            "after": cutoff.isoformat() if cutoff else None,
            "before": None,
        },
        "exportedAt": datetime.now().astimezone().isoformat(),
        "messages": messages,
        "messageCount": len(messages),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / export_filename(
        guild.get("name"), category, channel.get("name"), channel_id
    )
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8", newline=""
    )
    print(f"    wrote {len(messages)} messages -> {path.name}", file=sys.stderr)
    return path


# -- commands -----------------------------------------------------------------

def cmd_check(token):
    me = api_get("/users/@me", token)
    if not me.get("bot"):
        raise DiscordError(
            "That token belongs to a user account, not a bot. Automating a user account\n"
            "breaks Discord's Terms of Service. Create a bot in the Developer Portal."
        )
    print(f"Authenticated as bot: {me.get('username')} ({me.get('id')})")
    guilds = api_get("/users/@me/guilds", token)
    if not guilds:
        print("The bot is not in any server yet. Invite it, then re-run --check.")
    for guild in guilds:
        print(f"  server: {guild.get('name')} ({guild.get('id')})")
    return 0


def cmd_list_channels(token, guild_id):
    if not guild_id:
        guilds = api_get("/users/@me/guilds", token)
        if len(guilds) != 1:
            raise DiscordError("Pass --guild <id>; the bot is in more than one server.")
        guild_id = guilds[0]["id"]

    channels = api_get(f"/guilds/{guild_id}/channels", token)
    categories = {c["id"]: c["name"] for c in channels if c.get("type") == 4}
    for channel in sorted(channels, key=lambda c: c.get("position", 0)):
        if channel.get("type") not in (0, 5, 15):
            continue
        category = categories.get(channel.get("parent_id"), "-")
        print(f"  {channel['id']}  #{channel['name']:<24} ({category})")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Fetch Discord messages through the official Bot API."
    )
    parser.add_argument("--check", action="store_true",
                        help="verify the token and show which servers the bot is in")
    parser.add_argument("--list-channels", action="store_true",
                        help="list channel ids the bot can see")
    parser.add_argument("--channel", action="append", default=[],
                        help="channel id, or a name from discord.local.json; repeatable")
    parser.add_argument("--all", action="store_true",
                        help="fetch every channel listed in discord.local.json")
    parser.add_argument("--days", type=int,
                        help="only fetch messages newer than this many days")
    parser.add_argument("--guild", help="server id (defaults to config, or the only server)")

    args = parser.parse_args()

    try:
        config = load_config()
        token = config["token"]
        guild_id = args.guild or config.get("guildId")

        if args.check:
            return cmd_check(token)
        if args.list_channels:
            return cmd_list_channels(token, guild_id)

        named = config.get("channels", {}) or {}
        targets = []
        if args.all:
            if not named:
                raise DiscordError('No "channels" in discord.local.json to fetch.')
            targets = list(named.values())
        for channel in args.channel:
            targets.append(named.get(channel, channel))

        if not targets:
            parser.print_help()
            return 1

        for channel_id in targets:
            export_channel(token, str(channel_id), args.days)

        print("\nNext, rebuild the prioritized markdown:", file=sys.stderr)
        print("  python BPETools/parse_bug_reports.py", file=sys.stderr)
        print("  python BPETools/parse_suggestions.py", file=sys.stderr)
        return 0

    except DiscordError as exc:
        print(f"\nerror: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
