## Twin2Clouds: Cost‑Efficient Digital Twin Engineering — Artifact

This repository contains Twin2Clouds, accompanying our paper at EDTConf'25 [(conf.researchr.org/home/edtconf-2025)](https://conf.researchr.org/home/edtconf-2025). We will add the Title and citation information once the publication is available.

Twin2Clouds is a web application with a Python-based REST API backend for exploring cost trade‑offs of engineering a Digital Twin across major cloud providers (**AWS, Azure, and GCP**) and layers (Data Acquisition, Storage tiers, Processing, Twin Management, Visualization). It computes monthly cost estimates and suggests a cost‑efficient provider path across layers given scenario inputs.


### Quick start

**Using Docker (Recommended):**

```bash
# From the parent directory (workspace root)
docker-compose up --build

# Open in browser:
# - Web UI: http://localhost:80/ui
# - API Docs: http://localhost:80/docs
```

**Manual setup:**

```bash
# Install dependencies
pip install -r requirements.txt

# Configure credentials in config/config_credentials.json
# (See config/config_credentials.example.json for template)

# Run the API server
uvicorn rest_api:app --reload --host 0.0.0.0 --port 5003

# Open: http://localhost:5003/ui
```

### How to use

1. Open the Web UI at `/ui` in your browser
2. Either click a preset (Smart Home / Industrial / Large Building) or fill in:
   - Number of devices
   - Device sending interval (minutes)
   - Average message size (KB)
   - Storage durations (months): Hot, Cool, Archive
   - 3D model needed? If yes, number of 3D entities
   - Dashboard refreshes per hour and active hours per day
   - Monthly Grafana users: editors and viewers
3. Click "Calculate Cost"
4. Review:
   - Optimal cost path banner (e.g., `L1_GCP → L2_AWS_Hot → L2_GCP_Cool → ...`)
   - Provider costs for each layer (AWS, Azure, GCP)
   - Flip each card to see which specific services are compared

### What it compares

- **L1 Data Acquisition:** AWS IoT Core vs Azure IoT Hub vs Google Cloud Pub/Sub
- **L2 Storage tiers:** 
  - Hot: DynamoDB vs Cosmos DB vs Firestore
  - Cool: S3 Infrequent Access vs Blob Storage Cool vs Cloud Storage Nearline
  - Archive: S3 Glacier vs Blob Storage Archive vs Cloud Storage Archive
- **L3 Data Processing:** AWS Lambda vs Azure Functions vs Cloud Functions
- **L4 Twin Management:** AWS IoT TwinMaker vs Azure Digital Twins (GCP uses self-hosted solution)
- **L5 Visualization:** Amazon Managed Grafana vs Azure Managed Grafana vs self-hosted Grafana on GCP (Note: GCP self-hosted costs are currently placeholders)

Transfers between layers and clouds are modeled with tiered egress where applicable. The app computes the cheapest storage path across Hot → Cool → Archive including transfer fees.

### Architecture

**Backend (Python):**
- `rest_api.py` - FastAPI REST API serving the web UI and calculation endpoints
- `py/calculation/engine.py` - Main calculation orchestration
- `py/calculation/aws.py`, `azure.py`, `gcp.py` - Provider-specific cost calculations
- `py/calculation/decision.py` - Decision graph for optimal provider selection
- `py/calculate_up_to_date_pricing.py` - Dynamic pricing fetcher for cloud services
- `py/cloud_price_fetcher_*.py` - Provider-specific pricing API clients

**Frontend:**
- `index.html` - Web UI
- `js/api-client.js` - API communication and result display
- `js/calculation/ui.js` - UI helpers (sliders, presets, form handling)
- `css/styles.css` - Styling

**Configuration:**
- `pricing/fetched_data/pricing_dynamic.json` - Auto-generated dynamic pricing data
- `pricing/service_mapping.json` - Service name mapping across providers
- `pricing/service_calc_params.json` - Calculation parameters per service
- `config/config_credentials.json` - Cloud provider API credentials


### Pricing and Data Sources

**Dynamic Pricing (fetched from APIs):**
- **AWS:** boto3 Pricing API for IoT Core, Lambda, DynamoDB, S3, Transfer, TwinMaker
- **Azure:** Azure Retail Prices API for IoT Hub, Functions, CosmosDB, Blob Storage, Digital Twins
- **GCP:** Static defaults (dynamic fetching to be implemented). Note: L4/L5 self-hosted solutions currently use placeholder costs.

**Static Defaults:**
- Used where dynamic APIs are unavailable or for specific fields
- Logged during pricing updates with warnings for transparency
- See `py/cloud_price_fetcher_*.py` for STATIC_DEFAULTS definitions

**Update Pricing:**
```bash
# Via API endpoint
curl "http://localhost:5003/api/fetch_up_to_date_pricing"

# Or via Python script
docker exec <container> python py/calculate_up_to_date_pricing.py
```

### API Endpoints

- `GET /ui` - Web interface
- `PUT /api/calculate` - Calculate costs for given parameters
- `GET /api/fetch_up_to_date_pricing` - Fetch latest cloud pricing
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation (ReDoc)

### Repository layout

- `rest_api.py` - FastAPI application
- `index.html` - Web UI
- `py/` - Python calculation engine and pricing fetchers
- `js/` - Frontend JavaScript (API client, UI helpers)
- `css/` - Stylesheets
- `pricing/` - Pricing data and configuration
- `config/` - Credentials and configuration files
- `docs/` - Documentation HTML pages

### Reproducibility

- The app is deterministic for a given set of inputs and pricing data
- Pricing data is timestamped in `pricing_dynamic.json`
- To reproduce results, use the same preset inputs and pricing file revision
- Static defaults are clearly logged during pricing updates

Note: This code accompanies our paper accepted at EDTConf'25. The paper is not yet published; a preprint will be linked here once available.

### Citation

If you use this artifact, please cite the accompanying paper (Proceedings are not yet available).


