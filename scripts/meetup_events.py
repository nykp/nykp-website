"""Fetch NYKP's upcoming Meetup sessions into data/events.json for the website.

Run by `pixi run events`, before the Hugo build. layouts/shortcodes/
meetup-events.html renders the result on the home and Schedule pages. See the
"Upcoming sessions" section of README.md.

Two public sources, no API credentials:

- The group's iCal feed lists the upcoming events. New events appear in it
  promptly, but cancellations never do: a cancelled event stays in the feed as
  STATUS:CONFIRMED, with its original LAST-MODIFIED.
- Each event's own page carries schema.org structured data (the JSON-LD
  Meetup publishes for search engines), and that does say EventCancelled. So
  each event is checked against its page before it's listed: cancelled and
  postponed events are left out, and the page wins on title and times.

If an event page can't be read, the event is still listed as the feed has it,
which is never worse than the feed alone. If the feed itself can't be read, the
output says so and the page links to Meetup instead. Either way this exits 0:
a Meetup outage must not block an unrelated content change from deploying.

Standard library only, so the pixi environment is just Python.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

GROUP_URL = "https://www.meetup.com/nykayakpolo/"
FEED_URL = GROUP_URL + "events/ical/"
TZ = ZoneInfo("America/New_York")
USER_AGENT = "nykp-website-build (+https://nykayakpolo.org)"
TIMEOUT_SECONDS = 20
ATTEMPTS = 3

# schema.org eventStatus -> ours. EventRescheduled and EventMovedOnline are
# still happening (startDate already holds the new time), so they read as
# scheduled; the other two are left off the list.
EVENT_STATUSES = {
    "EventScheduled": "scheduled",
    "EventRescheduled": "scheduled",
    "EventMovedOnline": "scheduled",
    "EventPostponed": "postponed",
    "EventCancelled": "cancelled",
}


def warn(message):
    # Surfaces as an annotation on the workflow run, which a continue-on-error
    # step would otherwise hide.
    prefix = "::warning::" if os.environ.get("GITHUB_ACTIONS") else "warning: "
    print(prefix + message, file=sys.stderr)


def fetch(url):
    for attempt in range(1, ATTEMPTS + 1):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return response.read().decode("utf-8")
        except OSError:
            if attempt == ATTEMPTS:
                raise
            time.sleep(2 * attempt)


# --- iCal feed -----------------------------------------------------------------

# NAME;PARAM=value;PARAM="quoted:value":property value
PROPERTY_LINE = re.compile(r'^([A-Za-z0-9-]+)((?:;[^:;=]+=(?:"[^"]*"|[^:;"]*))*):(.*)$')
PARAM = re.compile(r';([^:;=]+)=("[^"]*"|[^:;"]*)')
TEXT_ESCAPE = re.compile(r"\\([\\;,nN])")


def unfold(ics):
    """Undo RFC 5545 line folding: a line starting with a space or tab continues the last."""
    lines = []
    for line in re.split(r"\r?\n", ics):
        if line[:1] in (" ", "\t") and lines:
            lines[-1] += line[1:]
        elif line:
            lines.append(line)
    return lines


def unescape_text(value):
    return TEXT_ESCAPE.sub(lambda m: "\n" if m.group(1) in "nN" else m.group(1), value)


def parse_ical_datetime(value, params):
    """A DTSTART/DTEND value as an aware datetime in the group's timezone."""
    if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", value):
        return datetime.combine(datetime.strptime(value, "%Y%m%d").date(), datetime.min.time(), TZ)
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=ZoneInfo("UTC")).astimezone(TZ)
    # Floating times (no TZID) are local to the group.
    tz = ZoneInfo(params["TZID"]) if "TZID" in params else TZ
    return datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=tz).astimezone(TZ)


def parse_feed(ics):
    """The VEVENTs in an iCal feed, as dicts with title, url, start and end."""
    # An error or bot-check page served with a 200 would otherwise parse as an
    # empty calendar, and the page would claim nothing is scheduled.
    if "BEGIN:VCALENDAR" not in ics:
        raise ValueError("response isn't an iCal calendar")
    events, current = [], None
    for line in unfold(ics):
        match = PROPERTY_LINE.match(line)
        if not match:
            continue
        name, raw_params, value = match.group(1).upper(), match.group(2), match.group(3)
        params = {k.upper(): v.strip('"') for k, v in PARAM.findall(raw_params)}
        if name == "BEGIN" and value == "VEVENT":
            current = {}
        elif name == "END" and value == "VEVENT" and current is not None:
            events.append(current)
            current = None
        elif current is None:
            continue
        elif name == "SUMMARY":
            current["title"] = unescape_text(value)
        elif name == "URL":
            current["url"] = value
        elif name == "UID":
            current["uid"] = value
        elif name in ("DTSTART", "DTEND"):
            current[name.lower()[2:]] = parse_ical_datetime(value, params)

    parsed = []
    for event in events:
        if "start" not in event:
            continue
        # Meetup always sends URL, but its UIDs (event_123@meetup.com) carry the id too.
        if "url" not in event:
            uid = re.fullmatch(r"event_(\d+)@meetup\.com", event.get("uid", ""))
            if not uid:
                continue
            event["url"] = f"{GROUP_URL}events/{uid.group(1)}/"
        event.setdefault("end", event["start"])
        event.setdefault("title", "Meetup event")
        parsed.append(event)
    return parsed


# --- Event pages -----------------------------------------------------------------

class JsonLdParser(HTMLParser):
    """Collects the contents of every <script type="application/ld+json"> on a page."""

    def __init__(self):
        super().__init__()
        self.blocks = []
        self._in_block = False

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("type") == "application/ld+json":
            self._in_block = True
            self.blocks.append("")

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_block = False

    def handle_data(self, data):
        if self._in_block:
            self.blocks[-1] += data


def page_event(html):
    """The schema.org Event on an event page (Meetup uses SportsEvent), or None."""
    parser = JsonLdParser()
    parser.feed(html)
    for block in parser.blocks:
        try:
            data = json.loads(block)
        except ValueError:
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data])
        for item in items:
            if isinstance(item, dict) and str(item.get("@type", "")).endswith("Event"):
                return item
    return None


def apply_page(event, item):
    """Overlay what the event's page says onto the feed's version of the event."""
    status = str(item.get("eventStatus", "")).rsplit("/", 1)[-1]
    if status not in EVENT_STATUSES:
        raise ValueError(f"unrecognized eventStatus {item.get('eventStatus')!r}")
    event["status"] = EVENT_STATUSES[status]
    if item.get("name"):
        event["title"] = item["name"]
    if item.get("startDate"):
        event["start"] = datetime.fromisoformat(item["startDate"]).astimezone(TZ)
        event["end"] = event["start"]
    if item.get("endDate"):
        event["end"] = datetime.fromisoformat(item["endDate"]).astimezone(TZ)
    place = item.get("location") or {}
    address = place.get("address") or {}
    event["venue"] = place.get("name")
    event["address"] = address.get("streetAddress")
    event["location"] = ", ".join(part for part in (place.get("name"), address.get("addressLocality")) if part) or None


# --- Output ---------------------------------------------------------------------

def day(d):
    return f"{d:%a}, {d:%b} {d.day}"


def clock(t, meridiem=True):
    text = f"{t.hour % 12 or 12}:{t.minute:02d}"
    return f"{text} {'am' if t.hour < 12 else 'pm'}" if meridiem else text


def when(start, end):
    """("Sat, Oct 25", "12:00–2:30 pm") -- or a date range for a multi-day event."""
    if end.date() > start.date() and end - start >= timedelta(hours=24):
        return f"{day(start)} – {day(end)}", f"starts {clock(start)}"
    if end <= start:
        return day(start), clock(start)
    same_half = (start.hour < 12) == (end.hour < 12)
    return day(start), f"{clock(start, meridiem=not same_half)}–{clock(end)}"


def to_output(event):
    date_display, time_display = when(event["start"], event["end"])
    return {
        "title": event["title"],
        "url": event["url"],
        "start": event["start"].isoformat(),
        "end": event["end"].isoformat(),
        "date_display": date_display,
        "time_display": time_display,
        "location": event.get("location"),
        # Meetup's venue name, which data/venues.yaml maps to a Google Maps
        # link, and its street address for venues that file doesn't list.
        "venue": event.get("venue"),
        "address": event.get("address"),
        # "scheduled", or "unverified" when the event page couldn't be read
        # and the event is listed as the feed has it.
        "status": event.get("status", "unverified"),
    }


def build(now, limit):
    try:
        feed = parse_feed(fetch(FEED_URL))
    # KeyError covers an unknown TZID (ZoneInfoNotFoundError).
    except (OSError, ValueError, KeyError) as e:
        warn(f"couldn't read the Meetup feed {FEED_URL}: {e}")
        return {"status": "unavailable", "events": []}

    # Check pages in date order only until the list is full, so a whole
    # season posted at once doesn't mean fetching every event page each build.
    listed = []
    for event in sorted((e for e in feed if e["end"] > now), key=lambda e: e["start"]):
        if len(listed) >= limit:
            break
        try:
            item = page_event(fetch(event["url"]))
            if item is None:
                raise ValueError("no schema.org Event on the page")
            apply_page(event, item)
        except (OSError, ValueError) as e:
            warn(f"couldn't check {event['url']} ({event['title']}), listing it as the feed has it: {e}")
        if event.get("status") in ("cancelled", "postponed"):
            print(f"Leaving out {event['status']} {event['title']} ({event['url']})")
            continue
        listed.append(event)

    # The page can move an event, so filter and sort again.
    listed = sorted((e for e in listed if e["end"] > now), key=lambda e: e["start"])
    return {"status": "ok", "events": [to_output(e) for e in listed]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--out", default="data/events.json", help="where to write the JSON")
    parser.add_argument("--limit", type=int, default=10, help="most events to list")
    args = parser.parse_args(argv)

    now = datetime.now(TZ)
    result = {
        "generated_at": now.isoformat(timespec="seconds"),
        "generated_at_display": f"{day(now)} at {clock(now)}",
        "group_url": GROUP_URL,
        "events_url": GROUP_URL + "events/",
        **build(now, args.limit),
    }

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    tmp_path = args.out + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp_path, args.out)

    counts = {}
    for event in result["events"]:
        counts[event["status"]] = counts.get(event["status"], 0) + 1
    summary = ", ".join(f"{n} {status}" for status, n in sorted(counts.items())) or "no events"
    print(f"Wrote {args.out}: {result['status']}, {summary}")


if __name__ == "__main__":
    main()
