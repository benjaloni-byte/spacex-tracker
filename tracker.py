"""
SpaceX Launch Tracker - GitHub Actions Edition
Checks for new SpaceX launches and posts to Discord with monthly counts.
"""

import os
import json
import logging
import requests
from datetime import datetime, timezone
from pathlib import Path

# ── CONFIG ────────────────────────────────────────────────────────────────────
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK")
API_BASE        = "https://ll.thespacedevs.com/2.3.0"
SEEN_FILE       = Path("seen_ids.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("spacex-tracker")

# ── PERSISTENCE ───────────────────────────────────────────────────────────────
def load_seen() -> set:
    try:
        if SEEN_FILE.exists():
            return set(json.loads(SEEN_FILE.read_text()))
    except Exception as e:
        log.warning(f"Could not load seen IDs: {e}")
    return set()

def save_seen(seen: set):
    try:
        SEEN_FILE.write_text(json.dumps(sorted(list(seen)), indent=2))
    except Exception as e:
        log.error(f"Could not save seen IDs: {e}")

# ── DATE HELPERS ──────────────────────────────────────────────────────────────
def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def month_window() -> tuple[str, str]:
    """Return ISO strings for the start and end of the current UTC month."""
    now   = utc_now()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if now.month == 12:
        end = start.replace(year=now.year + 1, month=1)
    else:
        end = start.replace(month=now.month + 1)
    return start.isoformat().replace("+00:00", "Z"), end.isoformat().replace("+00:00", "Z")

def format_dt(iso: str | None) -> str:
    if not iso:
        return "TBD"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y at %I:%M %p UTC").replace(" 0", " ")
    except:
        return iso

def ordinal(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    suffix = ['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]
    return f"{n}{suffix}"

# ── API CALLS ─────────────────────────────────────────────────────────────────
def api_get(url: str) -> list:
    """GET a LL2 API URL, return results list. Returns [] on error."""
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "SpaceX-Tracker-GHA/1.0"})
        if r.status_code == 429:
            log.warning("Rate limited by LL2 API")
            return []
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception as e:
        log.error(f"API request failed: {e}")
        return []

def fetch_upcoming() -> list:
    """Fetch upcoming SpaceX launches."""
    url = (
        f"{API_BASE}/launches/upcoming/"
        f"?limit=30&mode=detailed&ordering=net"
        f"&lsp__name=SpaceX"
    )
    return api_get(url)

def fetch_month_launches() -> list:
    """Fetch all SpaceX launches (past + upcoming) in the current UTC month."""
    start, end = month_window()
    results = []

    # Past launches this month
    past_url = (
        f"{API_BASE}/launches/previous/"
        f"?limit=50&ordering=net"
        f"&lsp__name=SpaceX"
        f"&net__gte={start}&net__lt={end}"
    )
    results.extend(api_get(past_url))

    # Upcoming launches this month
    upcoming_url = (
        f"{API_BASE}/launches/upcoming/"
        f"?limit=50&ordering=net"
        f"&lsp__name=SpaceX"
        f"&net__gte={start}&net__lt={end}"
    )
    results.extend(api_get(upcoming_url))

    # Dedupe and sort by NET
    seen_ids = set()
    unique = []
    for launch in results:
        if launch["id"] not in seen_ids:
            seen_ids.add(launch["id"])
            unique.append(launch)
    unique.sort(key=lambda l: l.get("net") or "")
    return unique

# ── MONTHLY STATS ─────────────────────────────────────────────────────────────
LAUNCHED_STATUSES = {"Success", "Failure", "Partial Failure", "In Flight"}

def is_launched(launch: dict) -> bool:
    status = launch.get("status") or {}
    return status.get("name") in LAUNCHED_STATUSES or status.get("abbrev") in LAUNCHED_STATUSES

def month_stats(month_launches: list) -> dict:
    scheduled = len(month_launches)
    launched  = sum(1 for l in month_launches if is_launched(l))
    now       = utc_now()
    month_name = now.strftime("%B %Y")
    return {"scheduled": scheduled, "launched": launched, "month_name": month_name}

def launch_month_index(launch_id: str, month_launches: list) -> int | None:
    """Find the 1-based position of a launch within the month."""
    for i, launch in enumerate(month_launches):
        if launch["id"] == launch_id:
            return i + 1
    return None

# ── DISCORD ───────────────────────────────────────────────────────────────────
def send_discord(launch: dict, month_idx: int | None, stats: dict):
    """Send a rich embed to Discord for a new launch."""
    if not DISCORD_WEBHOOK:
        log.warning("DISCORD_WEBHOOK not set — skipping notification")
        return

    status  = (launch.get("status") or {})
    s_name  = status.get("name") or status.get("abbrev") or "Unknown"
    rocket  = ((launch.get("rocket") or {}).get("configuration") or {}).get("name") or "Unknown"
    pad     = (launch.get("pad") or {}).get("name") or ""
    net     = format_dt(launch.get("net"))
    mission = (launch.get("mission") or {}).get("description") or ""
    orbit   = ((launch.get("mission") or {}).get("orbit") or {}).get("name") or ""
    vids    = launch.get("vidURLs") or []

    count_str = ordinal(month_idx) if month_idx else "upcoming"
    description = (
        f"**{launch['name']}**\n"
        f"*{count_str} SpaceX launch scheduled in {stats['month_name']}*"
    )

    fields = [
        {"name": "Vehicle", "value": rocket, "inline": True},
        {"name": "Status", "value": s_name, "inline": True},
        {
            "name": "Monthly Count",
            "value": (
                f"**{count_str}** of **{stats['scheduled']}** scheduled · "
                f"**{stats['launched']}** already launched"
            ),
            "inline": False,
        },
        {"name": "Launch Time (NET)", "value": net, "inline": False},
    ]

    if pad:
        fields.append({"name": "Pad", "value": pad, "inline": False})
    if orbit:
        fields.append({"name": "Orbit", "value": orbit, "inline": True})
    if mission:
        snippet = mission[:300] + "…" if len(mission) > 300 else mission
        fields.append({"name": "Mission", "value": snippet, "inline": False})
    if vids:
        links = " · ".join(f"[{v.get('title') or 'Watch'}]({v['url']})" for v in vids[:3])
        fields.append({"name": "Streams", "value": links, "inline": False})

    payload = {
        "embeds": [{
            "title": "🚀 New SpaceX Launch Detected",
            "description": description,
            "color": 0xFFFFFF,
            "fields": fields,
            "footer": {"text": "SpaceX Tracker · The Space Devs LL2 API"},
            "timestamp": utc_now().isoformat(),
        }]
    }

    try:
        r = requests.post(DISCORD_WEBHOOK, json=payload, timeout=15)
        if r.status_code in (200, 204):
            log.info(f"✓ Discord notified: {launch['name']}")
        else:
            log.error(f"Discord error {r.status_code}: {r.text[:200]}")
    except Exception as e:
        log.error(f"Discord request failed: {e}")

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    log.info("SpaceX Launch Tracker - checking for new launches…")

    # Load previously seen launch IDs
    seen = load_seen()
    first_run = len(seen) == 0
    log.info(f"Loaded {len(seen)} previously seen launch IDs")

    # Fetch data
    log.info("Fetching SpaceX launches from LL2 API…")
    upcoming = fetch_upcoming()
    month_launches = fetch_month_launches()
    stats = month_stats(month_launches)

    log.info(
        f"Found {len(upcoming)} upcoming SpaceX launches · "
        f"{stats['month_name']}: {stats['scheduled']} scheduled, {stats['launched']} launched"
    )

    # Detect new launches
    new_launches = [l for l in upcoming if l["id"] not in seen]

    if new_launches and not first_run:
        log.info(f"🚀 {len(new_launches)} new launch(es) detected!")
        for launch in new_launches:
            idx = launch_month_index(launch["id"], month_launches)
            log.info(f"  → {launch['name']} (#{idx} this month)")
            send_discord(launch, idx, stats)
    elif new_launches and first_run:
        log.info(f"First run — seeding {len(new_launches)} launches without notifying")
    else:
        log.info("No new launches detected")

    # Update seen IDs
    for launch in upcoming:
        seen.add(launch["id"])
    save_seen(seen)
    log.info(f"Saved {len(seen)} total seen IDs")

if __name__ == "__main__":
    main()
