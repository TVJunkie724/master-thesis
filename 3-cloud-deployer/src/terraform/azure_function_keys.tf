# ==============================================================================
# Azure Function Host Keys (for cross-app authentication)
# 
# These data sources retrieve the default function keys from deployed function
# apps to enable authenticated Azure→Azure HTTP calls.
#
# IMPORTANT: Terraform Cycle Limitation & Workaround
# ==================================================
# Problem: Terraform has a cycle dependency when a function app references
# its OWN key in app_settings:
#   - L2 app would need L2_FUNCTION_KEY = data.l2.key in app_settings
#   - data.l2 depends_on L2 app being created
#   - L2 app depends_on data.l2 (via app_settings reference) = CYCLE
#
# Terraform cannot resolve this cycle, causing deployment to fail.
#
# Workaround Implemented:
# - Internal L2 functions (persister, event-checker) use AuthLevel.ANONYMOUS
#   instead of AuthLevel.FUNCTION, eliminating the need for L2 to have its
#   OWN L2_FUNCTION_KEY in app_settings
# - Cross-app calls (L1→L2, L0→L2) still work because L1/L0 can reference
#   L2's key without creating a cycle (they're different apps)
# - See persister/function_app.py and event-checker/function_app.py for
#   full security documentation
#
# Cross-app keys work fine because there's no self-reference:
# - L2 app references USER_FUNCTION_KEY (different app = no cycle)
# - L1/L0 apps reference L2_FUNCTION_KEY (different app = no cycle)
#
# Future Improvement: See docs/future-work.md for proper solutions when
# Terraform supports post-deployment app_settings updates.
#
# Reference: Known Terraform/Azure issue documented in:
# - https://github.com/hashicorp/terraform-provider-azurerm/issues/14642
# - https://github.com/hashicorp/terraform-provider-azurerm/issues/15402
#
# NOTE: L0 Glue and L3 reader functions use AuthLevel.ANONYMOUS with
# X-Inter-Cloud-Token validation - they don't need function keys for those.
# ==============================================================================

# --- L2 Function App Key Retrieval ---
# Used by L1 (dispatcher) and L0 (glue) to call processor_wrapper
# NOTE: L2 itself does NOT use this key in its app_settings (would cause cycle)

# Wait for L2 function app to fully initialize and generate host keys
resource "time_sleep" "wait_for_l2_keys" {
  count           = var.layer_2_provider == "azure" ? 1 : 0
  create_duration = "60s"
  
  # Explicit trigger ensures this runs after L2 app is created
  triggers = {
    function_app_id = azurerm_linux_function_app.l2[0].id
  }
}

data "azurerm_function_app_host_keys" "l2" {
  count               = var.layer_2_provider == "azure" ? 1 : 0
  name                = azurerm_linux_function_app.l2[0].name
  resource_group_name = azurerm_resource_group.main[0].name
  
  # Depend on the sleep - gives Azure time to generate keys
  depends_on = [time_sleep.wait_for_l2_keys]
}

# --- User Function App Key Retrieval ---
# Used by L2 (processor_wrapper, event_feedback_wrapper) to call user functions

# Wait for user function app to fully initialize and generate host keys
resource "time_sleep" "wait_for_user_keys" {
  count           = var.layer_2_provider == "azure" ? 1 : 0
  create_duration = "60s"
  
  # Explicit trigger ensures this runs after user app is created
  triggers = {
    function_app_id = azurerm_linux_function_app.user[0].id
  }
}

data "azurerm_function_app_host_keys" "user" {
  count               = var.layer_2_provider == "azure" ? 1 : 0
  name                = azurerm_linux_function_app.user[0].name
  resource_group_name = azurerm_resource_group.main[0].name
  
  # Depend on the sleep - gives Azure time to generate keys
  depends_on = [time_sleep.wait_for_user_keys]
}
