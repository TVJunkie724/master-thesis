# Cross-Cloud Authentication Token
#
# This file manages the inter-cloud authentication token used for
# cross-cloud communication between layers (L1→L2, L2→L3, etc.).
#
# The token is automatically generated when any cross-cloud boundary exists
# and no explicit token is provided via var.inter_cloud_token.

# ==============================================================================
# Cross-Cloud Detection
# ==============================================================================

locals {
  # Detect if any cross-cloud boundaries exist
  needs_inter_cloud_token = (
    var.layer_1_provider != var.layer_2_provider ||
    var.layer_2_provider != var.layer_3_hot_provider ||
    var.layer_3_hot_provider != var.layer_3_cold_provider ||
    var.layer_3_cold_provider != var.layer_3_archive_provider
  )
}

# ==============================================================================
# Random Password for Inter-Cloud Token
# ==============================================================================

resource "random_password" "inter_cloud_token" {
  count   = var.inter_cloud_token == "" && local.needs_inter_cloud_token ? 1 : 0
  length  = 64
  special = false
}
