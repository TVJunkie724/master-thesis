# AWS TwinMaker Hierarchy Format

## Overview
This file defines the entity and component structure for AWS IoT TwinMaker.

## Component Type ID Prefix
**IMPORTANT:** The `componentTypeId` values in this file will be automatically 
prefixed with `{digital_twin_name}-` at deployment time.

For example, if your `config.json` has:
```json
{"digital_twin_name": "my-factory"}
```

Then `"componentTypeId": "temperature-sensor"` becomes `"my-factory-temperature-sensor"` in AWS.

## Required Fields

### Entity
- `type`: Must be `"entity"`
- `id`: Unique entity identifier
- `children`: Array of child entities/components (optional)

### Component
- `type`: Must be `"component"`
- `name`: Component instance name (unique within parent entity)
- `componentTypeId`: **REQUIRED** - Base type ID (will be prefixed)
- `properties`: Array of time series property definitions
- `constProperties`: Array of static property definitions (makes type concrete)
- `iotDeviceId`: Optional - Links to IoT device for data ingestion

### Property Format
```json
{"name": "temperature", "dataType": "DOUBLE"}
```
Valid dataTypes: `STRING`, `DOUBLE`, `INTEGER`, `BOOLEAN`, `LONG`

### Const Property Format
```json
{"name": "sensorId", "dataType": "STRING", "value": "sensor-001"}
```

## Example
See `aws_hierarchy.json` in this directory.
