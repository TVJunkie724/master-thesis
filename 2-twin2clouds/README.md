## Twin2Clouds: Cost‑Efficient Digital Twin Engineering — Artifact

This repository contains the Twin2Clouds, accompanying our paper at EDTConf'25 [(conf.researchr.org/home/edtconf-2025)](https://conf.researchr.org/home/edtconf-2025). We will add the Title and citation information once the publication is available.

Twin2Clouds is a small, client‑side web app for exploring cost trade‑offs of engineering a Digital Twin across major cloud providers (AWS, Azure) and layers (Data Acquisition, Storage tiers, Processing, Twin Management, Visualization). It computes monthly cost estimates and suggests a cost‑efficient provider path across layers given scenario inputs.


### Quick start

- Serve the folder with any static web server. Examples:

```bash
# From the repo root
python3 -m http.server 8000
# then open: http://localhost:8000/index.html
```

```bash
# Or with Node.js
npx --yes serve .
# then open the URL shown, e.g.: http://localhost:3000/index.html
```

### How to use

1. Open `index.html` in your browser via the local server.
2. Either click a preset (Smart Home / Industrial / Large Building) or fill in:
   - Number of devices
   - Device sending interval (minutes)
   - Average message size (KB)
   - Storage durations (months): Hot, Cool, Archive
   - 3D model needed? If yes, number of 3D entities
   - Dashboard refreshes per hour and active hours per day
   - Monthly Grafana users: editors and viewers
3. Click “Calculate Cost”.
4. Review:
   - Optimal cost path banner (e.g., `L1_AWS → L2_Azure_Hot → …`)
   - Flip each card to see which specific services are compared and links to providers

### What it compares

- L1 Data Acquisition: AWS IoT Core vs Azure IoT Hub
- L2 Storage tiers: Hot (DynamoDB vs Cosmos DB), Cool (S3 Infrequent Access vs Blob Storage Cool), Archive (S3 Glacier Deep Archive vs Blob Storage Archive)
- L3 Data Processing: AWS Lambda vs Azure Functions
- L4 Twin Management: AWS IoT TwinMaker or Azure Digital Twins (depending on 3D model need)
- L5 Visualization: Amazon Managed Grafana vs Azure Managed Grafana

Transfers between layers and clouds are modeled with tiered egress where applicable; the app computes a cheapest storage path across Hot → Cool → Archive including transfer fees.

### Pricing and assumptions

- All pricing and thresholds are defined in `pricing.json`. Update values there to align with current provider pricing.
- Some calculations make clearly stated simplifications (e.g., tiered egress, request units, message size thresholds, minimum storage durations). See the inline comments in `layer_*.js` files.

### Repository layout

- `index.html`: UI and script inclusion
- `styles.css`: styling
- `ui.js`: UI helpers (sliders, presets, conditional inputs)
- `pricing.json`: provider pricing and tiers used by the calculators
- `data_transfer.js`: cross‑layer/cloud transfer cost helpers
- `layer_data_acquisition.js`: L1 calculators
- `layer_data_storage.js`: L2 (Hot/Cool/Archive) calculators
- `layer_data_processing.js`: L3 calculators
- `layer_twin_management.js`: L4 calculators
- `layer_data_visualization.js`: L5 calculators
- `cost_calculation.js`: orchestrates inputs, calls calculators, builds results, and suggests the optimal path
- `EDT_25__CloudDT_engineering (3).pdf`: accepted manuscript

### Reproducibility

- The app is deterministic for a given set of inputs and `pricing.json`.
- To reproduce figures or numbers from the paper, use the presets and note the exact `pricing.json` revision used.

Note: This code accompanies our paper accepted at [Conference/Journal]. The paper is not yet published; a preprint will be linked here once available.

### Citation

If you use this artifact, please cite the accompanying paper (Proceedings are not yet available).


