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

  # Computed token value - single source of truth
  # Used by all functions making cross-cloud HTTP calls
  inter_cloud_token_value = (
    var.inter_cloud_token != ""
    ? var.inter_cloud_token
    : try(random_password.inter_cloud_token[0].result, "")
  )

  # Function routing suffix - same-cloud uses processor, cross-cloud uses connector
  # Used by L1 dispatchers (AWS, Azure, GCP) to determine routing
  target_function_suffix = (
    var.layer_1_provider == var.layer_2_provider
    ? "-processor"
    : "-connector"
  )

  # ===========================================================================
  # API Paths - Single Source of Truth
  # ===========================================================================
  #
  # WARNING: These paths must match the Python function route decorators!
  # 
  # If you change a path here, you MUST also update the corresponding
  # Python function decorator. The mapping is:
  #
  # | Terraform Key     | Python File                                    | Decorator                      |
  # |-------------------|------------------------------------------------|--------------------------------|
  # | ingestion         | azure_functions/ingestion/function_app.py     | @bp.route(route="ingestion")   |
  # | hot_writer        | azure_functions/hot-writer/function_app.py    | @bp.route(route="hot-writer")  |
  # | cold_writer       | azure_functions/cold-writer/function_app.py   | @app.route(route="cold-writer")|
  # | archive_writer    | azure_functions/archive-writer/function_app.py| @app.route(route="archive-writer")|
  # | hot_reader        | azure_functions/hot-reader/function_app.py    | @bp.route(route="hot-reader")  |
  # | adt_pusher        | azure_functions/adt-pusher/function_app.py    | @bp.route(route="adt-pusher")  |
  # | persister         | azure_functions/persister/function_app.py     | @bp.route(route="persister")   |
  # | event_checker     | azure_functions/event-checker/function_app.py | @bp.route(route="event-checker")|
  # | event_feedback    | azure_functions/event_feedback_wrapper/...    | @bp.route(route="event-feedback")|
  # | dispatcher        | azure_functions/dispatcher/function_app.py    | (IoT Hub trigger, not HTTP)    |
  #
  api_paths = {
    ingestion       = "api/ingestion"
    hot_writer      = "api/hot-writer"
    cold_writer     = "api/cold-writer"
    archive_writer  = "api/archive-writer"
    hot_reader      = "api/hot-reader"
    adt_pusher      = "api/adt-pusher"
    persister       = "api/persister"
    event_checker   = "api/event-checker"
    event_feedback  = "api/event-feedback"
    dispatcher      = "api/dispatcher"
  }

  # ===========================================================================
  # Cross-Provider Schema Constants
  # ===========================================================================
  # Single source of truth for data schema used by DynamoDB, Cosmos DB, Firestore

  schema_partition_key = "device_id"
  schema_sort_key      = "timestamp"

  # ===========================================================================
  # Storage Tier Names
  # ===========================================================================

  storage_tier_hot     = "hot"
  storage_tier_cold    = "cold"
  storage_tier_archive = "archive"

  # ===========================================================================
  # Runtime & Function Constants
  # ===========================================================================

  python_runtime_aws   = "python3.11"  # AWS Lambda
  python_runtime_azure = "3.11"        # Azure Functions
  python_runtime_gcp   = "python311"   # GCP Cloud Functions

  # ===========================================================================
  # 3D Scenes Constants
  # ===========================================================================

  scenes_container_name = "3dscenes"  # Azure ADT scenes container
}

# ==============================================================================
# Random Password for Inter-Cloud Token
# ==============================================================================

resource "random_password" "inter_cloud_token" {
  count   = var.inter_cloud_token == "" && local.needs_inter_cloud_token ? 1 : 0
  length  = 64
  special = false
}
