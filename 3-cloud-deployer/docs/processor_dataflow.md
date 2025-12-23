# Processor Architecture - Dataflow Documentation

**Last Updated:** December 23, 2025

## Overview

This document describes the complete dataflow for processor functions across AWS, GCP, and Azure. The architecture uses a **Dispatcher → Wrapper → User Processor** pattern.

---

## Naming Convention

All naming is based on **Device ID from `config_iot_devices.json`**:

| Component | Naming Pattern |
|-----------|----------------|
| Processor Folder | `processors/{device_id}/` |
| ZIP File | `processor-{device_id}.zip` |
| Terraform Resource | `{twin}-{device_id}-processor` |
| Runtime Invocation | `{twin}-{device_id}-processor` |

---

## Dataflow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            BUILD TIME                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  config_iot_devices.json                                                    │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────┐                                                    │
│  │  package_builder.py │ ─── Reads device["id"]                            │
│  │  (line 813)         │                                                    │
│  └─────────┬───────────┘                                                    │
│            │                                                                │
│            ▼                                                                │
│  ┌─────────────────────────────────────────┐                               │
│  │ Looks for: processors/{device_id}/      │                               │
│  │ Creates:   processor-{device_id}.zip    │                               │
│  └─────────┬───────────────────────────────┘                               │
│            │                                                                │
│            ▼                                                                │
│  ┌─────────────────────┐                                                    │
│  │ tfvars_generator.py │ ─── Also reads device["id"]                       │
│  │ (lines 260, 324)    │                                                    │
│  └─────────┬───────────┘                                                    │
│            │                                                                │
│            ▼                                                                │
│  ┌─────────────────────────────────────────┐                               │
│  │ Finds: processor-{device_id}.zip        │                               │
│  │ Outputs: { name: device_id, zip_path }  │                               │
│  └─────────────────────────────────────────┘                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                           DEPLOY TIME                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────┐     ┌─────────────────────┐                       │
│  │  gcp_compute.tf     │     │  aws_compute.tf     │                       │
│  │  (line 353)         │     │  (line 274)         │                       │
│  └─────────┬───────────┘     └─────────┬───────────┘                       │
│            │                           │                                    │
│            ▼                           ▼                                    │
│  ┌───────────────────────────────────────────────────────────┐             │
│  │  Creates: {twin}-{device_id}-processor                    │             │
│  │  Using:   ${var.digital_twin_name}-${each.value.name}     │             │
│  └───────────────────────────────────────────────────────────┘             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                           RUN TIME                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  IoT Event (contains iotDeviceId)                                           │
│         │                                                                   │
│         ▼                                                                   │
│  ┌─────────────────────┐                                                    │
│  │     Dispatcher      │ ─── Routes to {twin}-processor (wrapper)          │
│  └─────────┬───────────┘                                                    │
│            │                                                                │
│            ▼                                                                │
│  ┌─────────────────────┐                                                    │
│  │  Processor Wrapper  │ ─── Extracts device_id from event                 │
│  │  (lines 49-52)      │                                                    │
│  └─────────┬───────────┘                                                    │
│            │                                                                │
│            ▼                                                                │
│  ┌───────────────────────────────────────────────────────────┐             │
│  │  Invokes: {twin}-{device_id}-processor                    │             │
│  │  (User processor deployed by Terraform)                   │             │
│  └─────────┬─────────────────────────────────────────────────┘             │
│            │                                                                │
│            ▼                                                                │
│  ┌─────────────────────┐                                                    │
│  │     Persister       │ ─── Stores processed data                         │
│  └─────────────────────┘                                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Source Files Reference

| Step | AWS | GCP | Azure |
|------|-----|-----|-------|
| **Wrapper** | `processor_wrapper/lambda_function.py` | `processor_wrapper/main.py` | `processor_wrapper/function_app.py` |
| **Dispatcher** | `dispatcher/lambda_function.py` | `dispatcher/main.py` | `dispatcher/function_app.py` |
| **Terraform** | `aws_compute.tf:274` | `gcp_compute.tf:353` | N/A (bundled) |
| **tfvars** | `tfvars_generator.py:324` | `tfvars_generator.py:260` | N/A (bundled) |

---

## December 2025 Fixes Applied

1. **Dispatcher routing** - Changed from `{twin}-{device_id}-processor` to `{twin}-processor` (wrapper)
2. **tfvars_generator GCP** - Fixed to use `device.get("id")` not `device.get("processor")`
3. **tfvars_generator AWS** - Added `_get_aws_user_function_vars()` function
4. **package_builder** - Fixed processor ZIP naming to use `device_id`
5. **Terraform GCP** - Fixed user processor naming from `{twin}-processor-{name}` to `{twin}-{name}-processor`
6. **Terraform AWS** - Added user processor and wrapper Lambda resources
7. **Tests** - Cleaned up obsolete GCP/AWS renaming tests

---

## Known Remaining Issues

> [!CAUTION]
> **Azure Processor Renaming Not Integrated**
> 
> The `_rewrite_azure_function_names` function exists but is NOT called by `_add_azure_function_app_directly`.
> Azure processors will deploy with their original names, not `{twin}-{device_id}-processor`.
> This will cause the Azure wrapper to fail at runtime.
