"""
Static data export for Rural Hours ESN.
Joins raw_observations, species, and gbif_occurrences into static JSON/GeoJSON
files for the frontend.
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data.sqlite"
OUTPUT_DIR = ROOT / "frontend" / "public" / "data"

CITATION = "Cooper, Susan Fenimore. Rural Hours. 3rd ed. New York: George P. Putnam, 1850."


def parse_taxonomy_from_raw(raw_json: str | None) -> dict:
    """Extract taxonomy from GBIF occurrence raw_json."""
    if not raw_json:
        return {}
    try:
        rec = json.loads(raw_json)
        return {
            k: rec.get(k)
            for k in ("kingdom", "phylum", "class", "order", "family", "genus", "species", "scientificName")
            if rec.get(k)
        }
    except (json.JSONDecodeError, TypeError):
        return {}


def format_entry_date(observation_date: str | None, chunk_source: str | None, day_of_year: int | None) -> str:
    """Build human-readable entry date for citation."""
    if observation_date:
        try:
            dt = datetime.strptime(observation_date[:10], "%Y-%m-%d")
            return dt.strftime("%B %d, %Y").replace(" 0", " ")
        except (ValueError, TypeError):
            pass
    if day_of_year and 1 <= day_of_year <= 365:
        try:
            from datetime import timedelta
            d = datetime(1848, 1, 1) + timedelta(days=day_of_year - 1)
            return d.strftime("%B %d, %Y").replace(" 0", " ")
        except (ValueError, TypeError):
            pass
    return chunk_source or "—"


def _taxonomy_by_species(conn: sqlite3.Connection) -> dict[str, dict]:
    """Build species -> taxonomy map from first occurrence's raw_json per species."""
    rows = conn.execute("""
        SELECT s.plant_name_mentioned, g.raw_json
        FROM species s
        JOIN gbif_occurrences g ON g.species_id = s.id
        WHERE g.raw_json IS NOT NULL
    """).fetchall()
    out: dict[str, dict] = {}
    for plant, raw_json in rows:
        if plant not in out:
            out[plant] = parse_taxonomy_from_raw(raw_json)
    return out


def export_observations(conn: sqlite3.Connection) -> list[dict]:
    """Join observations with species taxonomy for observations.json."""
    taxonomy_by_species = _taxonomy_by_species(conn)
    rows = conn.execute("""
        SELECT 
            o.id,
            o.plant_name_mentioned,
            o.observation_date,
            o.day_of_year,
            o.phenological_event,
            o.quote,
            o.chunk_source,
            s.accepted_scientific_name,
            s.family,
            s.gbif_usage_key
        FROM raw_observations o
        LEFT JOIN species s ON s.plant_name_mentioned = o.plant_name_mentioned
        ORDER BY o.day_of_year, o.plant_name_mentioned
    """).fetchall()

    return [
        {
            "id": r[0],
            "plant_name_mentioned": r[1],
            "observation_date": r[2],
            "day_of_year": r[3],
            "phenological_event": r[4],
            "quote": r[5],
            "chunk_source": r[6],
            "accepted_scientific_name": r[7],
            "family": r[8],
            "gbif_usage_key": r[9],
            "citation": CITATION,
            "entry_date": format_entry_date(r[2], r[6], r[3]),
            "taxonomy": taxonomy_by_species.get(r[1]) or {},
        }
        for r in rows
    ]


def export_occurrences_geojson(conn: sqlite3.Connection) -> dict:
    """Build GeoJSON FeatureCollection for MapLibre."""
    rows = conn.execute("""
        SELECT 
            g.decimal_latitude,
            g.decimal_longitude,
            g.event_date,
            g.day_of_year,
            g.year,
            g.record_type,
            g.gbif_id,
            g.raw_json,
            s.plant_name_mentioned,
            s.accepted_scientific_name
        FROM gbif_occurrences g
        JOIN species s ON s.id = g.species_id
        WHERE g.decimal_latitude IS NOT NULL AND g.decimal_longitude IS NOT NULL
    """).fetchall()

    features = []
    for r in rows:
        lat, lon, event_date, doy, year, record_type, gbif_id, raw_json, plant, scientific = r
        taxonomy = parse_taxonomy_from_raw(raw_json)
        props = {
            "gbif_id": gbif_id,
            "plant_name": plant,
            "scientific_name": scientific,
            "event_date": event_date,
            "day_of_year": doy,
            "year": year,
            "record_type": record_type,
        }
        if taxonomy:
            props["taxonomy"] = taxonomy
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(lon), float(lat)],
            },
            "properties": props,
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


def run() -> None:
    """Export observations.json and occurrences.geojson to frontend/public/data/."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)

    obs = export_observations(conn)
    (OUTPUT_DIR / "observations.json").write_text(
        json.dumps(obs, indent=2), encoding="utf-8"
    )
    print(f"Exported {len(obs)} observations to observations.json")

    geojson = export_occurrences_geojson(conn)
    (OUTPUT_DIR / "occurrences.geojson").write_text(
        json.dumps(geojson, indent=2), encoding="utf-8"
    )
    print(f"Exported {len(geojson['features'])} occurrences to occurrences.geojson")

    conn.close()


if __name__ == "__main__":
    run()
