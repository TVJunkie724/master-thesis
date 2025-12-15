# Azure L3 Storage Layer (Hot/Cold/Archive)
#
# This file creates the L3 layer infrastructure for tiered data storage.
# L3 stores telemetry data with automatic tiering based on age.
#
# Resources Created:
# - Cosmos DB Account (Serverless): Hot storage for real-time queries
# - Cosmos DB Database & Container: Structured data storage
# - Blob Storage Containers: Cold and Archive tiers
# - App Service Plan (Consumption Y1): Serverless hosting for L3 functions
# - Linux Function App: Hosts hot reader and mover functions
#
# Functions Deployed:
# - Hot Reader: Exposes hot data to L4/L5 via REST API
# - Hot Reader Last Entry: Returns most recent entry per device
# - Hot-Cold Mover: Timer-triggered, moves old data to cold storage
# - Cold-Archive Mover: Timer-triggered, moves old cold data to archive
#
# Storage Tiers:
# - Hot: Cosmos DB Serverless (< 30 days by default)
# - Cold: Blob Storage Cool tier (30-90 days by default)
# - Archive: Blob Storage Archive tier (> 90 days by default)

# ==============================================================================
# Cosmos DB Account (Serverless - Hot Storage)
# ==============================================================================

resource "azurerm_cosmosdb_account" "main" {
  count               = var.layer_3_hot_provider == "azure" ? 1 : 0
  name                = "${var.digital_twin_name}-cosmos"
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location
  offer_type          = "Standard"
  kind                = "GlobalDocumentDB"

  # Serverless capacity mode
  capabilities {
    name = "EnableServerless"
  }

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = azurerm_resource_group.main[0].location
    failover_priority = 0
  }

  tags = local.common_tags
}

# ==============================================================================
# Cosmos DB Database
# ==============================================================================

resource "azurerm_cosmosdb_sql_database" "main" {
  count               = var.layer_3_hot_provider == "azure" ? 1 : 0
  name                = "${var.digital_twin_name}-db"
  resource_group_name = azurerm_resource_group.main[0].name
  account_name        = azurerm_cosmosdb_account.main[0].name
}

# ==============================================================================
# Cosmos DB Container (Hot Data)
# ==============================================================================

resource "azurerm_cosmosdb_sql_container" "hot" {
  count               = var.layer_3_hot_provider == "azure" ? 1 : 0
  name                = "hot"
  resource_group_name = azurerm_resource_group.main[0].name
  account_name        = azurerm_cosmosdb_account.main[0].name
  database_name       = azurerm_cosmosdb_sql_database.main[0].name
  partition_key_paths = ["/deviceId"]

  # TTL disabled - data moves to cold storage via mover function
  default_ttl = -1

  indexing_policy {
    indexing_mode = "consistent"

    included_path {
      path = "/*"
    }
  }
}

# ==============================================================================
# Blob Storage Containers (Cold & Archive)
# ==============================================================================

resource "azurerm_storage_container" "cold" {
  count                 = var.layer_3_cold_provider == "azure" ? 1 : 0
  name                  = "cold"
  storage_account_name  = azurerm_storage_account.main[0].name
  container_access_type = "private"
}

resource "azurerm_storage_container" "archive" {
  count                 = var.layer_3_archive_provider == "azure" ? 1 : 0
  name                  = "archive"
  storage_account_name  = azurerm_storage_account.main[0].name
  container_access_type = "private"
}

# ==============================================================================
# L3 App Service Plan (Consumption - Serverless)
# ==============================================================================

resource "azurerm_service_plan" "l3" {
  count               = var.layer_3_hot_provider == "azure" ? 1 : 0
  name                = "${var.digital_twin_name}-l3-plan"
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location
  os_type             = "Linux"
  sku_name            = "Y1"

  tags = local.common_tags
}

# ==============================================================================
# L3 Function App (Hot Reader, Movers)
# ==============================================================================

resource "azurerm_linux_function_app" "l3" {
  count               = var.layer_3_hot_provider == "azure" ? 1 : 0
  name                = "${var.digital_twin_name}-l3-functions"
  resource_group_name = azurerm_resource_group.main[0].name
  location            = azurerm_resource_group.main[0].location
  service_plan_id     = azurerm_service_plan.l3[0].id

  storage_account_name       = azurerm_storage_account.main[0].name
  storage_account_access_key = azurerm_storage_account.main[0].primary_access_key

  # Managed Identity
  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.main[0].id]
  }

  site_config {
    application_stack {
      python_version = "3.11"
    }

    # CORS for cross-cloud hot reader access
    cors {
      allowed_origins = ["*"]
    }
  }

  app_settings = {
    # Azure Functions runtime
    FUNCTIONS_WORKER_RUNTIME       = "python"
    FUNCTIONS_EXTENSION_VERSION    = "~4"
    AzureWebJobsStorage           = local.azure_storage_connection_string
    WEBSITE_RUN_FROM_PACKAGE      = "1"
    SCM_DO_BUILD_DURING_DEPLOYMENT = "true"

    # Cosmos DB connection
    COSMOS_ENDPOINT = azurerm_cosmosdb_account.main[0].endpoint
    COSMOS_KEY      = azurerm_cosmosdb_account.main[0].primary_key
    COSMOS_DATABASE = azurerm_cosmosdb_sql_database.main[0].name

    # Storage account for cold/archive
    STORAGE_CONNECTION_STRING = local.azure_storage_connection_string

    # Mover intervals (in days)
    HOT_TO_COLD_DAYS     = var.layer_3_hot_to_cold_interval_days
    COLD_TO_ARCHIVE_DAYS = var.layer_3_cold_to_archive_interval_days

    # Digital Twin info
    DIGITAL_TWIN_NAME = var.digital_twin_name
    AZURE_CLIENT_ID   = azurerm_user_assigned_identity.main[0].client_id

    # Cross-cloud authentication
    INTER_CLOUD_TOKEN = var.inter_cloud_token != "" ? var.inter_cloud_token : random_password.inter_cloud_token[0].result
  }

  tags = local.common_tags

  lifecycle {
    ignore_changes = [
      app_settings["WEBSITE_RUN_FROM_PACKAGE"],
    ]
  }
}

# ==============================================================================
# RBAC: Managed Identity → Cosmos DB Data Contributor
# ==============================================================================

resource "azurerm_cosmosdb_sql_role_assignment" "identity_cosmos" {
  count               = var.layer_3_hot_provider == "azure" ? 1 : 0
  resource_group_name = azurerm_resource_group.main[0].name
  account_name        = azurerm_cosmosdb_account.main[0].name
  role_definition_id  = "${azurerm_cosmosdb_account.main[0].id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002"  # Built-in Data Contributor
  principal_id        = azurerm_user_assigned_identity.main[0].principal_id
  scope               = azurerm_cosmosdb_account.main[0].id
}
