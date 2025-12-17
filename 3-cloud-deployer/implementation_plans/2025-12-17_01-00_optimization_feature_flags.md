# Optimization Feature Flags Implementation

## 1. Executive Summary

### The Problem
Terraform had no way to conditionally deploy optional features based on user configuration in `config_optimization.json`.

### The Solution
Add feature flag variables to Terraform and load them from `config_optimization.json` via `tfvars_generator.py`.

### Impact
Terraform can now conditionally deploy resources based on:
- `use_event_checking` - Event checker and action functions
- `trigger_notification_workflow` - Logic Apps / Step Functions
- `return_feedback_to_device` - IoT feedback functions

---

## 2. Proposed Changes

### Component: Terraform Variables

#### [x] [MODIFY] variables.tf
- **Path:** `src/terraform/variables.tf`
- **Description:** Added feature flag variables with safe defaults

```hcl
variable "trigger_notification_workflow" {
  description = "Enable notification workflows (Logic Apps/Step Functions)"
  type        = bool
  default     = false
}

variable "use_event_checking" {
  description = "Enable event checking and user event actions"
  type        = bool
  default     = true
}

variable "return_feedback_to_device" {
  description = "Enable feedback functions to send responses to IoT devices"
  type        = bool
  default     = false
}
```

---

### Component: tfvars Generator

#### [x] [MODIFY] tfvars_generator.py
- **Path:** `src/tfvars_generator.py`
- **Description:** Added `_load_optimization_flags()` function to read from `config_optimization.json`

```python
def _load_optimization_flags(project_dir: Path) -> dict:
    """
    Load feature flags from config_optimization.json for conditional Terraform resources.
    
    Maps inputParamsUsed to Terraform variable names:
    - useEventChecking -> use_event_checking
    - triggerNotificationWorkflow -> trigger_notification_workflow
    - returnFeedbackToDevice -> return_feedback_to_device
    """
```

---

## 3. Verification Checklist

- [x] Variables added to `variables.tf`
- [x] `_load_optimization_flags()` implemented
- [x] Called in `generate_tfvars()` main function
- [x] Safe defaults for missing config file

---

## 4. Design Decisions

### Safe Defaults
- `use_event_checking = true` - Most common need
- `trigger_notification_workflow = false` - Complex, disabled for testing
- `return_feedback_to_device = false` - Optional feature

### JSON Path Mapping
Maps camelCase JSON keys to snake_case Terraform variables:
```
result.inputParamsUsed.useEventChecking -> use_event_checking
```
