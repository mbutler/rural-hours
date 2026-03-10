"""
Taxonomic harmonization for Rural Hours pipeline.
For each unique plant_name_mentioned, query GBIF name_backbone to get
accepted scientific name, family, and usageKey. Store in species table.
"""
import os
import sqlite3
import time
from pathlib import Path

from pygbif import species as gbif_species

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data.sqlite"

# Otsego County, NY bounding box (for reference; used in occurrences)
LAT_MIN, LAT_MAX = 42.4, 42.9
LON_MIN, LON_MAX = -75.3, -74.6

# Common name -> scientific name mapping for names GBIF backbone doesn't resolve
COMMON_TO_SCIENTIFIC = {
    "skunk-cabbage": "Symplocarpus foetidus",
    "skunk cabbage": "Symplocarpus foetidus",
    "garden hyacinths": "Hyacinthus orientalis",
    "blue hyacinths": "Hyacinthus orientalis",
    "hyacinth": "Hyacinthus orientalis",
    "periwinkle": "Vinca minor",
    "snow-drop": "Galanthus nivalis",
    "snowdrop": "Galanthus nivalis",
    "maple": "Acer saccharum",
    "sugar maple": "Acer saccharum",
    "scarlet maple": "Acer rubrum",
    "red maple": "Acer rubrum",
    "elm": "Ulmus americana",
    "sallows": "Salix caprea",
    "alders": "Alnus incana",
    "chestnuts": "Castanea dentata",
    "birches": "Betula papyrifera",
    "maples": "Acer saccharum",
    "ground laurel": "Kalmia latifolia",
    "locust": "Robinia pseudoacacia",
    "apple-trees": "Malus domestica",
    "apple trees": "Malus domestica",
    "pines": "Pinus strobus",
    "hemlocks": "Tsuga canadensis",
    "daffodils": "Narcissus pseudonarcissus",
    "tulips": "Tulipa gesneriana",
    "Virginia creepers": "Parthenocissus quinquefolia",
    "Virginia creeper": "Parthenocissus quinquefolia",
    "partridge berry": "Mitchella repens",
    "partridge plant": "Mitchella repens",
    "squaw-vine": "Mitchella repens",
    "squaw vine": "Mitchella repens",
}


def resolve_to_scientific(plant_name: str) -> str | None:
    """Convert common name to scientific for GBIF lookup."""
    normalized = plant_name.strip().lower()
    return COMMON_TO_SCIENTIFIC.get(normalized) or COMMON_TO_SCIENTIFIC.get(
        normalized.replace("-", " ")
    )


def harmonize_name(plant_name: str) -> dict | None:
    """
    Query GBIF name_backbone. Returns dict with usageKey, canonicalName, family,
    or None if no match.
    """
    # Try as-is first (in case it's already scientific)
    scientific = plant_name.strip()
    result = gbif_species.name_backbone(scientificName=scientific)

    if result.get("diagnostics", {}).get("matchType") == "NONE":
        # Try common name mapping
        alt = resolve_to_scientific(plant_name)
        if alt:
            scientific = alt
            result = gbif_species.name_backbone(scientificName=scientific)

    if result.get("diagnostics", {}).get("matchType") == "NONE":
        return None

    usage = result.get("usage") or {}
    classification = result.get("classification") or []
    family = None
    for rank in classification:
        if isinstance(rank, dict) and rank.get("rank") == "FAMILY":
            family = rank.get("name")
            break
    if not family and isinstance(classification, list):
        for item in classification:
            if isinstance(item, dict) and "family" in str(item).lower():
                family = item.get("name")
                break

    usage_key = usage.get("key") or usage.get("usageKey")
    canonical = usage.get("canonicalName") or usage.get("scientificName")

    if usage_key and canonical:
        return {
            "usageKey": int(usage_key),
            "canonicalName": canonical,
            "family": family,
        }
    return None


def run() -> None:
    """Run harmonization for all unique plant names in raw_observations."""
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA busy_timeout = 60000")
    plants = [
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT plant_name_mentioned FROM raw_observations"
        ).fetchall()
    ]
    print(f"Harmonizing {len(plants)} unique plant names...")

    for plant in plants:
        existing = conn.execute(
            "SELECT id, gbif_usage_key FROM species WHERE plant_name_mentioned = ?",
            (plant,),
        ).fetchone()
        if existing and existing[1] is not None:
            print(f"  Skip (existing): {plant}")
            continue

        h = harmonize_name(plant)
        if h:
            if existing:
                conn.execute(
                    """UPDATE species SET accepted_scientific_name=?, family=?, gbif_usage_key=?
                       WHERE plant_name_mentioned=?""",
                    (h["canonicalName"], h["family"], h["usageKey"], plant),
                )
            else:
                conn.execute(
                    """INSERT INTO species (plant_name_mentioned, accepted_scientific_name, family, gbif_usage_key)
                       VALUES (?, ?, ?, ?)""",
                    (plant, h["canonicalName"], h["family"], h["usageKey"]),
                )
            print(f"  OK: {plant} -> {h['canonicalName']} ({h['family'] or '?'})")
        else:
            if not existing:
                conn.execute(
                    "INSERT INTO species (plant_name_mentioned) VALUES (?)",
                    (plant,),
                )
            print(f"  No match: {plant}")
        time.sleep(0.2)  # Rate limit GBIF

    conn.commit()
    conn.close()
    print("Done.")


if __name__ == "__main__":
    run()
