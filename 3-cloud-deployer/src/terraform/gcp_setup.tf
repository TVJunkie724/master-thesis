# GCP Setup Layer (Foundation Resources)
#
# This file creates the foundational GCP resources that all other layers depend on.
# Resources are created conditionally based on whether any layer uses GCP.
#
# Resources Created:
# - GCP Project: Resource container (only for org accounts with billing_account)
# - Service Account for function deployment
# - Enabled APIs for required services
# - Cloud Storage bucket for function source code
#
# Supports two modes:
# - Private Account Mode: Uses existing project via gcp_project_id
# - Organization Account Mode: Creates new project via gcp_billing_account

# ==============================================================================
# Locals for GCP
# ==============================================================================

locals {
  gcp_common_labels = {
    digital-twin = var.digital_twin_name
    environment  = var.environment
    managed-by   = "terraform"
  }
  
  # Dual-mode detection: private account (existing project) vs org account (auto-create)
  gcp_use_existing_project = var.gcp_project_id != ""
  
  # Generated project ID (for org account mode)
  gcp_generated_project_id = "${var.digital_twin_name}-project"
  
  # Unified project ID - used by all other GCP resources
  # Uses existing project if provided, otherwise uses the auto-created one
  gcp_project_id = local.gcp_use_existing_project ? var.gcp_project_id : (
    local.deploy_gcp && !local.gcp_use_existing_project ? google_project.main[0].project_id : ""
  )
  
  # GCP-specific layer checks
  gcp_l1_enabled           = var.layer_1_provider == "google"
  gcp_l2_enabled           = var.layer_2_provider == "google"
  gcp_l3_hot_enabled       = var.layer_3_hot_provider == "google"
  gcp_l3_cold_enabled      = var.layer_3_cold_provider == "google"
  gcp_l3_archive_enabled   = var.layer_3_archive_provider == "google"
  
  # Multi-cloud detection for GCP
  gcp_needs_ingestion = local.gcp_l2_enabled && var.layer_1_provider != "google"
  gcp_needs_hot_writer = local.gcp_l3_hot_enabled && var.layer_2_provider != "google"
  gcp_needs_cold_writer = local.gcp_l3_cold_enabled && var.layer_3_hot_provider != "google"
  gcp_needs_archive_writer = local.gcp_l3_archive_enabled && var.layer_3_cold_provider != "google"
  gcp_needs_hot_reader = (
    (var.layer_4_provider != "google" && var.layer_4_provider != "" && local.gcp_l3_hot_enabled) ||
    (var.layer_5_provider != "google" && var.layer_5_provider != "" && local.gcp_l3_hot_enabled)
  )
  
  # Base URL for GCP Cloud Functions
  gcp_function_base_url = "https://${var.gcp_region}-${local.gcp_project_id}.cloudfunctions.net"
}

# ==============================================================================
# GCP Project (Resource Container - only for Organization Account Mode)
# ==============================================================================

# Only create project in org account mode (when billing_account provided but no project_id)
resource "google_project" "main" {
  count           = local.deploy_gcp && !local.gcp_use_existing_project ? 1 : 0
  name            = "${var.digital_twin_name}-project"
  project_id      = local.gcp_generated_project_id
  billing_account = var.gcp_billing_account

  labels = local.gcp_common_labels
}

# ==============================================================================
# Enable Required APIs
# ==============================================================================

# Cloud Resource Manager API is required to enable other APIs
resource "google_project_service" "cloudresourcemanager" {
  count   = local.deploy_gcp ? 1 : 0
  project = local.gcp_project_id
  service = "cloudresourcemanager.googleapis.com"
  
  disable_on_destroy = false
}

resource "google_project_service" "pubsub" {
  count   = local.deploy_gcp ? 1 : 0
  project = local.gcp_project_id
  service = "pubsub.googleapis.com"
  
  disable_on_destroy = false
  depends_on = [google_project_service.cloudresourcemanager]
}

resource "google_project_service" "cloudfunctions" {
  count   = local.deploy_gcp ? 1 : 0
  project = local.gcp_project_id
  service = "cloudfunctions.googleapis.com"
  
  disable_on_destroy = false
  depends_on = [google_project_service.cloudresourcemanager]
}

resource "google_project_service" "run" {
  count   = local.deploy_gcp ? 1 : 0
  project = local.gcp_project_id
  service = "run.googleapis.com"
  
  disable_on_destroy = false
  depends_on = [google_project_service.cloudresourcemanager]
}

resource "google_project_service" "firestore" {
  count   = local.gcp_l3_hot_enabled ? 1 : 0
  project = local.gcp_project_id
  service = "firestore.googleapis.com"
  
  disable_on_destroy = false
  depends_on = [google_project_service.cloudresourcemanager]
}

resource "google_project_service" "storage" {
  count   = local.gcp_l3_cold_enabled || local.gcp_l3_archive_enabled ? 1 : 0
  project = local.gcp_project_id
  service = "storage.googleapis.com"
  
  disable_on_destroy = false
  depends_on = [google_project_service.cloudresourcemanager]
}

resource "google_project_service" "eventarc" {
  count   = local.deploy_gcp ? 1 : 0
  project = local.gcp_project_id
  service = "eventarc.googleapis.com"
  
  disable_on_destroy = false
  depends_on = [google_project_service.cloudresourcemanager]
}

resource "google_project_service" "cloudbuild" {
  count   = local.deploy_gcp ? 1 : 0
  project = local.gcp_project_id
  service = "cloudbuild.googleapis.com"
  
  disable_on_destroy = false
  depends_on = [google_project_service.cloudresourcemanager]
}

resource "google_project_service" "cloudscheduler" {
  count   = local.gcp_l3_hot_enabled ? 1 : 0
  project = local.gcp_project_id
  service = "cloudscheduler.googleapis.com"
  
  disable_on_destroy = false
  depends_on = [google_project_service.cloudresourcemanager]
}

resource "google_project_service" "iam" {
  count   = local.deploy_gcp ? 1 : 0
  project = local.gcp_project_id
  service = "iam.googleapis.com"
  
  disable_on_destroy = false
  depends_on = [google_project_service.cloudresourcemanager]
}

# ==============================================================================
# Service Account for Cloud Functions
# ==============================================================================

resource "google_service_account" "functions" {
  count        = local.deploy_gcp ? 1 : 0
  project      = local.gcp_project_id
  account_id   = "${var.digital_twin_name}-functions-sa"
  display_name = "${var.digital_twin_name} Cloud Functions Service Account"
  
  depends_on = [google_project_service.iam]
}

# ==============================================================================
# Custom IAM Role for Cloud Functions (Least Privilege)
# ==============================================================================

resource "google_project_iam_custom_role" "functions_role" {
  count       = local.deploy_gcp ? 1 : 0
  project     = local.gcp_project_id
  role_id     = "${replace(var.digital_twin_name, "-", "_")}_functions_role"
  title       = "${var.digital_twin_name} Functions Role"
  description = "Custom role for Digital Twin Cloud Functions with least-privilege permissions"
  stage       = "GA"

  permissions = [
    # Pub/Sub (L1)
    "pubsub.topics.get",
    "pubsub.topics.publish",
    "pubsub.subscriptions.consume",
    "pubsub.subscriptions.get",

    # Firestore (L3 Hot)
    "datastore.entities.create",
    "datastore.entities.delete",
    "datastore.entities.get",
    "datastore.entities.list",
    "datastore.entities.update",

    # Cloud Storage (L3 Cold/Archive)
    "storage.objects.create",
    "storage.objects.delete",
    "storage.objects.get",
    "storage.objects.list",

    # Cloud Run (Function invocation)
    "run.routes.invoke",
  ]
  
  depends_on = [google_project_service.iam]
}

# Bind custom role to service account
resource "google_project_iam_member" "functions_custom_role" {
  count   = local.deploy_gcp ? 1 : 0
  project = local.gcp_project_id
  role    = google_project_iam_custom_role.functions_role[0].id
  member  = "serviceAccount:${google_service_account.functions[0].email}"
}

# ==============================================================================
# Cloud Storage Bucket for Function Source Code
# ==============================================================================

resource "google_storage_bucket" "function_source" {
  count         = local.deploy_gcp ? 1 : 0
  project       = local.gcp_project_id
  name          = "${local.gcp_project_id}-${var.digital_twin_name}-functions"
  location      = var.gcp_region
  force_destroy = true
  
  uniform_bucket_level_access = true
  
  labels = local.gcp_common_labels
}

