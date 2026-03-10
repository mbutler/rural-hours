"""
GBIF occurrence retrieval for Rural Hours pipeline.
For each harmonized species, fetch occurrences in Otsego County, NY:
- Historical (1840-1900) to corroborate Susan's observations
- Midcentury (1900-1980) to bridge the gap
- Modern (1980-present) for phenology comparison
"""
import json
import sqlite3
import time
from pathlib import Path

from pygbif import occurrences as gbif_occ

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data.sqlite"

# Otsego County, NY bounding box
LAT_MIN, LAT_MAX = 42.4, 42.9
LON_MIN, LON_MAX = -75.3, -74.6

# Range format for pygbif: "min,max"
LAT_RANGE = f"{LAT_MIN},{LAT_MAX}"
LON_RANGE = f"{LON_MIN},{LON_MAX}"


def fetch_occurrences_for_species(
    species_id: int,
    usage_key: int,
    conn: sqlite3.Connection,
) -> None:
    """Fetch historical and modern occurrences, store in gbif_occurrences."""
    for record_type, year_range in [
        ("historical", "1840,1900"),
        ("midcentury", "1900,1980"),
        ("modern", "1980,2025"),
    ]:
        offset = 0
        limit = 300
        while True:
            resp = gbif_occ.search(
                taxonKey=usage_key,
                decimalLatitude=LAT_RANGE,
                decimalLongitude=LON_RANGE,
                year=year_range,
                hasCoordinate=True,
                limit=limit,
                offset=offset,
            )
            results = resp.get("results", [])
            if not results:
                break

            for rec in results:
                gbif_id = str(rec.get("key", ""))
                if not gbif_id:
                    continue
                lat = rec.get("decimalLatitude")
                lon = rec.get("decimalLongitude")
                event_date = rec.get("eventDate")
                year = rec.get("year")
                doy = None
                if event_date and isinstance(event_date, str) and len(event_date) >= 10:
                    try:
                        from datetime import datetime
                        dt = datetime.strptime(event_date[:10], "%Y-%m-%d")
                        doy = dt.timetuple().tm_yday
                    except (ValueError, TypeError):
                        pass

                try:
                    conn.execute(
                        """INSERT OR IGNORE INTO gbif_occurrences 
                           (species_id, gbif_id, decimal_latitude, decimal_longitude, event_date, day_of_year, year, record_type, raw_json)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            species_id,
                            gbif_id,
                            lat,
                            lon,
                            event_date,
                            doy,
                            year,
                            record_type,
                            json.dumps(rec)[:8000] if rec else None,
                        ),
                    )
                except sqlite3.IntegrityError:
                    pass

            if len(results) < limit:
                break
            offset += limit
            time.sleep(0.3)

        time.sleep(0.2)


def run() -> None:
    """Fetch occurrences for all harmonized species with usage_key."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, plant_name_mentioned, gbif_usage_key FROM species WHERE gbif_usage_key IS NOT NULL"
    ).fetchall()

    print(f"Fetching occurrences for {len(rows)} species in Otsego County, NY...")

    for species_id, plant_name, usage_key in rows:
        if usage_key is None:
            continue
        print(f"  {plant_name} (key={usage_key})...")
        try:
            fetch_occurrences_for_species(species_id, usage_key, conn)
        except Exception as e:
            print(f"    Error: {e}")
        time.sleep(0.5)

    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM gbif_occurrences").fetchone()[0]
    print(f"Done. Total occurrences: {total}")
    conn.close()


if __name__ == "__main__":
    run()
