# Docker Command Reference

This project runs most components inside Docker containers. Here is how to execute commands and tests.

## Main Container: `master-thesis-2twin2clouds-1`

The main application code is mapped to `/app` inside the container.

### Running Python Scripts
To run Python scripts, you must set `PYTHONPATH=/app` to ensure modules are resolved correctly.

```bash
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 python py/script_name.py
```

**Example: Running Pricing Calculation**
```bash
docker exec -e PYTHONPATH=/app master-thesis-2twin2clouds-1 python py/calculate_up_to_date_pricing.py additional_debug=true
```

### Running Bash Commands
To run arbitrary bash commands:

```bash
docker exec master-thesis-2twin2clouds-1 bash -c "ls -la /app"
```

### File Paths
- **Host:** `d:\Git\master-thesis\2-twin2clouds`
- **Container:** `/app`

## Flutter
Flutter projects run locally on the host machine, not in Docker.
