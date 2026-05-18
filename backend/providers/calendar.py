"""Economic calendar — high-impact USD events via ForexFactory public feed."""
import requests
from datetime import datetime, timedelta, timezone
import pytz

NY_TZ = pytz.timezone("America/New_York")
_CACHE: dict = {"data": None, "at": None}
_TTL_HOURS = 4

FF_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"


def _fetch() -> list:
    try:
        r = requests.get(FF_URL, timeout=6, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        raw = r.json()
        out = []
        for ev in raw:
            if ev.get("country") != "USD":
                continue
            if ev.get("impact", "").lower() not in ("high",):
                continue
            out.append({
                "title":    ev.get("title", ""),
                "date":     ev.get("date", ""),
                "time":     ev.get("time", ""),
                "impact":   ev.get("impact", ""),
                "forecast": ev.get("forecast", ""),
                "previous": ev.get("previous", ""),
            })
        return out
    except Exception:
        return []


def get_economic_calendar() -> list:
    global _CACHE
    now = datetime.now(NY_TZ)
    if _CACHE["data"] is not None and _CACHE["at"]:
        age = (now - _CACHE["at"]).total_seconds() / 3600
        if age < _TTL_HOURS:
            return _CACHE["data"]
    data = _fetch()
    _CACHE = {"data": data, "at": now}
    return data


def get_today_events() -> dict:
    events = get_economic_calendar()
    today = datetime.now(NY_TZ).date()
    tomorrow = today + timedelta(days=1)

    today_ev, tomorrow_ev = [], []
    for ev in events:
        raw = ev.get("date", "")
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%m-%d-%Y", "%m/%d/%Y"):
            try:
                d = datetime.strptime(raw[:len(fmt)], fmt).date()
                if d == today:
                    today_ev.append(ev)
                elif d == tomorrow:
                    tomorrow_ev.append(ev)
                break
            except Exception:
                continue

    return {
        "today":    today_ev,
        "tomorrow": tomorrow_ev,
        "has_high_impact_today": len(today_ev) > 0,
        "has_high_impact_tomorrow": len(tomorrow_ev) > 0,
        "warning": (
            f"HIGH IMPACT TODAY: {', '.join(e['title'] for e in today_ev)}"
            if today_ev else None
        ),
    }
