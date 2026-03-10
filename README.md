# rural-hours

Compare Susan Fenimore Cooper's 19th-century phenological observations (*Rural Hours*) with historical and modern herbarium records in the Cooperstown/Otsego County, NY region—an Extended Specimen Network (ESN) application.

## Setup

```bash
# Python pipeline (venv + deps)
python -m venv venv
venv\Scripts\python -m pip install -r requirements.txt   # Windows
# . venv/bin/activate && pip install -r requirements.txt   # Unix

# Add OPENAI_API_KEY to .env (copy from .env.example)

# Frontend
cd frontend && bun install
```

## Data Pipeline

Run in order (or use `python pipeline/run_pipeline.py` for full run):

```bash
python pipeline/schema.py        # Create SQLite schema
python pipeline/extract.py       # NLP extraction from rural_hours.md (uses OpenAI)
python pipeline/harmonize.py     # GBIF taxonomic harmonization
python pipeline/occurrences.py   # GBIF occurrence retrieval (Otsego County)
python pipeline/export_data.py   # Export to frontend/public/data/
```

## Frontend

```bash
cd frontend
bun run dev
```

Static data: `observations.json` and `occurrences.geojson` in `frontend/public/data/`.
