"""
Text ingestion & NLP extraction for Rural Hours.
Reads rural_hours.md, chunks by journal entry, uses GPT-4o-mini to extract
plant phenological observations, stores in raw_observations table.
"""
import json
import re
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Project paths
ROOT = Path(__file__).resolve().parent.parent
TEXT_PATH = ROOT / "rural_hours.md"
DB_PATH = ROOT / "data.sqlite"

# Journal entry pattern: *Day, Month DayOrdinal.*— or *Day, DayOrdinal.*—
ENTRY_PATTERN = re.compile(
    r"\*([A-Za-z]+, (?:(?:January|February|March|April|May|June|July|August|September|October|November|December) )?\d{1,2}(?:st|nd|rd|th|d)?\.)\*[—\-]\s*",
    re.IGNORECASE,
)

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

# Year for journal (preface: commenced spring 1848)
DEFAULT_YEAR = 1848

SYSTEM_PROMPT = """You are a precise botanical and phenological data extractor. Your task is to extract PLANT-related phenological observations from 19th-century natural history journal text.

RULES:
1. Extract ONLY observations about PLANTS (vascular plants, trees, flowers, fungi if plant-like). Ignore birds, mammals, insects, weather-only, or non-biological content.
2. For each plant observation, output a JSON object with these exact keys:
   - plant_name_mentioned: The exact common or scientific name as used in the text (e.g., "skunk-cabbage", "sugar maple", "periwinkle").
   - observation_date: ISO date YYYY-MM-DD if inferable, else null.
   - day_of_year: Integer 1-365 (Day of Year), or null if not inferable.
   - phenological_event: ONE of: "blooming", "fruiting", "leafing", "setting seed", "observed".
   - quote: A brief verbatim snippet (1-2 sentences) containing the observation.

3. phenological_event mapping:
   - blooming: flowers opening, in blossom, flowering
   - fruiting: fruit forming, berries, producing fruit
   - leafing: leaves emerging, buds swelling, foliage appearing
   - setting seed: seeds forming, going to seed
   - observed: general presence, no specific phenophase

4. Return a JSON array of objects. If no plant observations, return [].

5. One journal entry may yield 0, 1, or several observations. Be thorough but do not fabricate."""

USER_PROMPT_TEMPLATE = """Journal entry dated {date_header}:

{text}

Extract all plant phenological observations as a JSON array."""


def parse_date_from_header(header: str, prev_month: int | None) -> tuple[str | None, int | None]:
    """Parse date from entry header like 'Saturday, March 4th.' or 'Tuesday, 7th.'"""
    header = header.strip().rstrip(".")
    parts = header.split(",")
    if len(parts) < 2:
        return None, None
    date_part = parts[1].strip()
    month = None
    day = None
    for m_name, m_num in MONTHS.items():
        if m_name in date_part.lower():
            month = m_num
            break
    if month is None:
        month = prev_month
    match = re.search(r"(\d{1,2})(?:st|nd|rd|th|d)?", date_part)
    if match:
        day = int(match.group(1))
    if month and day:
        return f"{DEFAULT_YEAR}-{month:02d}-{day:02d}", month
    return None, month


def date_to_doy(year: int, month: int, day: int) -> int:
    """Convert date to Day of Year (1-365)."""
    days_in_month = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                     31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return sum(days_in_month[: month - 1]) + day


def chunk_text(text: str) -> list[tuple[str, str, int | None]]:
    """Split text into journal entries. Returns [(date_header, body, doy), ...]."""
    matches = list(ENTRY_PATTERN.finditer(text))
    chunks: list[tuple[str, str, int | None]] = []
    prev_month = 3  # March is first journal month
    for i, m in enumerate(matches):
        header = m.group(1)
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        obs_date, obs_month = parse_date_from_header(header, prev_month)
        doy = None
        if obs_date:
            y, mo, d = map(int, obs_date.split("-"))
            doy = date_to_doy(y, mo, d)
        if obs_month:
            prev_month = obs_month
        chunks.append((header, body, doy))
    return chunks


def extract_chunk(header: str, body: str, dry_run: bool = False) -> list[dict]:
    """Call OpenAI to extract observations from a chunk. Returns list of observation dicts."""
    if dry_run:
        return []
    try:
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT_TEMPLATE.format(date_header=header, text=body[:6000])},
            ],
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content
        data = json.loads(content)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            if "observations" in data:
                return data["observations"]
            for key in ("items", "extractions", "results"):
                if key in data and isinstance(data[key], list):
                    return data[key]
        return []
    except Exception as e:
        print(f"  LLM error: {e}")
        return []


def run(dry_run: bool = False, limit: int | None = None) -> None:
    """Run extraction pipeline."""
    import sqlite3
    text = TEXT_PATH.read_text(encoding="utf-8")
    chunks = chunk_text(text)
    if limit:
        chunks = chunks[:limit]
    print(f"Found {len(chunks)} journal entries")
    conn = sqlite3.connect(DB_PATH)
    try:
        for i, (header, body, doy) in enumerate(chunks):
            if not body or len(body) < 50:
                continue
            obs_list = extract_chunk(header, body, dry_run=dry_run)
            for obs in obs_list:
                plant = obs.get("plant_name_mentioned") or obs.get("plant_name")
                if not plant:
                    continue
                event = obs.get("phenological_event", "observed")
                if event not in ("blooming", "fruiting", "leafing", "setting seed", "observed"):
                    event = "observed"
                quote = obs.get("quote", "")[:500]
                obs_date = obs.get("observation_date")
                obs_doy = obs.get("day_of_year") or doy
                conn.execute(
                    """INSERT INTO raw_observations 
                       (plant_name_mentioned, observation_date, day_of_year, phenological_event, quote, chunk_source)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (plant, obs_date, obs_doy, event, quote, header),
                )
            if (i + 1) % 20 == 0:
                print(f"  Processed {i + 1}/{len(chunks)} entries")
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM raw_observations").fetchone()[0]
        print(f"Stored {count} observations in raw_observations")
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    dry = "--dry-run" in sys.argv or "-n" in sys.argv
    limit = None
    for arg in sys.argv:
        if arg.startswith("--limit="):
            limit = int(arg.split("=")[1])
    run(dry_run=dry, limit=limit)
