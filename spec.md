# Project Specification: Susan's Rural Hours Phenology & ESN

## 1. Project Overview
This project is an Extended Specimen Network (ESN) application that compares the 19th-century phenological observations of natural history writer Susan Fenimore Cooper (from her book *Rural Hours*) with historical and modern herbarium records. 

The goal is to visualize how plant communities and their behaviors (blooming, setting seed, etc.) have shifted over time in the Cooperstown/Otsego County, New York region. The project consists of a Python-based data ingestion/processing pipeline and a lightweight, client-rendered React dashboard.

## 2. System Architecture


* **Data Pipeline:** Python scripts that read a local Markdown file, use an LLM for entity extraction, query biodiversity APIs for taxonomy and occurrence data, manage state in a local SQLite database, and export final static data files.
* **Frontend Application:** A purely client-side Single Page Application (SPA) built with React, Vite, and Bun. It consumes the static JSON data to render an interactive map and phenology charts. There is no runtime backend server.

## 3. Phase 1: Python Data Pipeline
**Tech Stack:** Python 3.x, `sqlite3`, `openai`, `pygbif`, `python-dotenv`, `pandas`.

The pipeline must execute the following steps:

### A. Text Ingestion & NLP Extraction
1.  **Input:** Read a provided `rural_hours.md` file.
2.  **Chunking:** Split the text by date/entry (Susan's book is organized like a journal).
3.  **LLM Extraction:** Use the `openai` library with the `gpt-4o-mini` model. Provide a strict system prompt instructing the model to extract:
    * `plant_name_mentioned`: The exact common or scientific name used in the text.
    * `observation_date`: The journal entry date (converted to an estimated Day of Year - DOY).
    * `phenological_event`: Categorized as 'blooming', 'fruiting', 'leafing', 'setting seed', or 'observed'.
    * `quote`: A brief snippet of the context.
4.  **Storage:** Save these raw extractions into a local `data.sqlite` database (Table: `raw_observations`).

### B. Taxonomic Harmonization
1.  **Query GBIF:** For each unique `plant_name_mentioned`, use `pygbif.species.name_backbone()` to find the accepted modern scientific name, family, and GBIF `usageKey`.
2.  **Storage:** Update `data.sqlite` with the harmonized taxonomic data. 

### C. GBIF Occurrence Retrieval
1.  **Scope:** Define a geographic bounding box for Otsego County, NY (approx. `decimalLatitude`: 42.4 to 42.9, `decimalLongitude`: -75.3 to -74.6).
2.  **Query:** For each harmonized species, query the GBIF Occurrence API (`pygbif.occurrences.search()`) restricted to the bounding box.
3.  **Filtering:** Retrieve both historical records (1840-1900) to corroborate Susan's presence, and modern records (1980-Present) that contain phenology/reproductive condition metadata if available, or just occurrence dates.
4.  **Storage:** Save results to `data.sqlite` (Table: `gbif_occurrences`).

### D. Static Data Export
1.  **Export:** Run a final script to join the database tables and export them as static files into the Vite frontend's `public/data/` directory:
    * `observations.json`: Susan's extracted observations linked to modern taxonomy.
    * `occurrences.geojson`: GBIF occurrence data formatted for MapLibre GL JS.

## 4. Phase 2: Frontend Dashboard
**Tech Stack:** Bun 1.3.10, React, Vite, MapLibre GL JS (mapping), Recharts (data visualization), Tailwind CSS (styling).

### A. Application Structure
* Must be a strictly client-side application. No SSR (Server-Side Rendering) dependencies.
* State management should be handled natively with React Hooks (`useState`, `useMemo`, `useEffect` for fetching the local JSON files).

### B. UI Components
1.  **Header:** Title and brief project description explaining the Extended Specimen Network concept.
2.  **Sidebar (Controls & Context):**
    * Species selector (dropdown or list) to filter the map and charts.
    * When a species is selected, display Susan's original journal quote, the historical observation date, and the modern accepted taxonomy.
3.  **Interactive Map (MapLibre GL JS):**
    * Display the Cooperstown bounding box.
    * Plot GBIF herbarium occurrences as styled vector points.
    * Differentiate historical (1800s) vs. modern (1900s+) records using color coding.
4.  **Phenology Visualization (Recharts):**
    * A scatter plot or timeline chart comparing the 'Day of Year' (1-365) of Susan's recorded phenological events against the 'Day of Year' of modern GBIF occurrences for the selected species.

### C. Aesthetic Guidelines: "Modern Naturalist"
* **Color Palette:** Clean white/off-white backgrounds (`#FAFAFA`), deep forest green accents (`#2C5530`), and muted earth tones for map data points (e.g., ochre, terracotta).
* **Typography:** Use a crisp, modern sans-serif (e.g., Inter or Roboto) for UI elements, labels, and charts to maintain a scientific dashboard feel. Use a high-quality serif (e.g., Merriweather or Playfair Display) exclusively for Susan Fenimore Cooper's direct quotes to hint at the 19th-century origins.
* **Layout:** Clean grid structure using Tailwind CSS. 

## 5. Execution Steps for the Agent
1.  Initialize the Vite+React project using Bun.
2.  Set up the Python virtual environment and `requirements.txt`.
3.  Write the SQLite schema setup script.
4.  Write the OpenAI NLP extraction script (stubbing the API call for testing).
5.  Write the GBIF harmonization and data export scripts.
6.  Build the React UI components and wire up the MapLibre and Recharts implementations using dummy data until the Python pipeline is run.