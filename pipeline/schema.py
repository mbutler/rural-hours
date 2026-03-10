"""
SQLite schema setup for the Rural Hours ESN pipeline.
Creates data.sqlite with raw_observations and gbif_occurrences tables.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data.sqlite"


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS raw_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_name_mentioned TEXT NOT NULL,
            observation_date TEXT,
            day_of_year INTEGER,
            phenological_event TEXT CHECK(phenological_event IN (
                'blooming', 'fruiting', 'leafing', 'setting seed', 'observed'
            )),
            quote TEXT,
            chunk_source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS species (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_name_mentioned TEXT UNIQUE NOT NULL,
            accepted_scientific_name TEXT,
            family TEXT,
            gbif_usage_key INTEGER,
            harmonized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS gbif_occurrences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            species_id INTEGER NOT NULL,
            gbif_id TEXT UNIQUE,
            decimal_latitude REAL,
            decimal_longitude REAL,
            event_date TEXT,
            day_of_year INTEGER,
            year INTEGER,
            record_type TEXT CHECK(record_type IN ('historical', 'midcentury', 'modern')),
            raw_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (species_id) REFERENCES species(id)
        );

        CREATE INDEX IF NOT EXISTS idx_raw_observations_plant 
            ON raw_observations(plant_name_mentioned);
        CREATE INDEX IF NOT EXISTS idx_species_plant 
            ON species(plant_name_mentioned);
        CREATE INDEX IF NOT EXISTS idx_species_usage_key 
            ON species(gbif_usage_key);
        CREATE INDEX IF NOT EXISTS idx_gbif_species 
            ON gbif_occurrences(species_id);
        CREATE INDEX IF NOT EXISTS idx_gbif_record_type 
            ON gbif_occurrences(record_type);
    """)


def migrate_gbif_occurrences(conn: sqlite3.Connection) -> None:
    """Recreate gbif_occurrences to allow midcentury record_type (if table exists with old schema)."""
    try:
        conn.execute("SELECT record_type FROM gbif_occurrences LIMIT 1")
    except sqlite3.OperationalError:
        return
    conn.execute("ALTER TABLE gbif_occurrences RENAME TO gbif_occurrences_old")
    conn.execute("""
        CREATE TABLE gbif_occurrences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            species_id INTEGER NOT NULL,
            gbif_id TEXT UNIQUE,
            decimal_latitude REAL,
            decimal_longitude REAL,
            event_date TEXT,
            day_of_year INTEGER,
            year INTEGER,
            record_type TEXT CHECK(record_type IN ('historical', 'midcentury', 'modern')),
            raw_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (species_id) REFERENCES species(id)
        )
    """)
    conn.execute("""
        INSERT OR IGNORE INTO gbif_occurrences 
        SELECT id, species_id, gbif_id, decimal_latitude, decimal_longitude, event_date, 
               day_of_year, year, record_type, raw_json, created_at 
        FROM gbif_occurrences_old
    """)
    conn.execute("DROP TABLE gbif_occurrences_old")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_gbif_species ON gbif_occurrences(species_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_gbif_record_type ON gbif_occurrences(record_type)")


def setup_database() -> Path:
    """Create or reset the database schema. Returns path to database."""
    conn = sqlite3.connect(DB_PATH)
    try:
        create_schema(conn)
        migrate_gbif_occurrences(conn)
        conn.commit()
        return DB_PATH
    finally:
        conn.close()


if __name__ == "__main__":
    path = setup_database()
    print(f"Schema created: {path}")
