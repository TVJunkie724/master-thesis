# GCP Setup Layer (Foundation Resources)
#
# This file creates the foundational GCP resources that all other layers depend on.
# Resources are created conditionally based on whether any layer uses GCP.
#
# Resources Created:
# - GCP Project: Resource container (like Azure Resource Group)
# - Service Account for function deployment
# - Enabled APIs for required services
# - Cloud Storage bucket for function source code
#
# Note: GCP project creation requires a billing account to be specified.

# ==============================================================================
# Locals for GCP
# ==============================================================================

locals {
  gcp_common_labels = {
    digital-twin = var.digital_twin_name
    environment  = var.environment
    managed-by   = "terraform"
  }
  
  # Generated project ID (follows GCP naming: lowercase, 6-30 chars, starts with letter)
  gcp_generated_project_id = "${var.digital_twin_name}-project"
  
  # Use provided project_id or generate one
  gcp_effective_project_id = var.gcp_project_id != "" ? var.gcp_project_id : local.gcp_generated_project_id
  
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
}

# ==============================================================================
# GCP Project (Resource Container - like Azure Resource Group)
# ==============================================================================

resource "google_project" "main" {
  count           = local.deploy_gcp && var.gcp_project_id == "" ? 1 : 0
  name            = "${var.digital_twin_name}-project"
  project_id      = local.gcp_generated_project_id
  billing_account = var.gcp_billing_account

  labels = local.gcp_common_labels
}

# ==============================================================================
# Enable Required APIs
# ==============================================================================

resource "google_project_service" "pubsub" {
  count   = local.deploy_gcp ? 1 : 0
  project = var.gcp_project_id
  service = "pubsub.googleapis.com"
  
  disable_on_destroy = false
}

resource "google_project_service" "cloudfunctions" {
  count   = local.deploy_gcp ? 1 : 0
  project = var.gcp_project_id
  service = "cloudfunctions.googleapis.com"
  
  disable_on_destroy = false
}

resource "google_project_service" "run" {
  count   = local.deploy_gcp ? 1 : 0
  project = var.gcp_project_id
  service = "run.googleapis.com"
  
  disable_on_destroy = false
}

resource "google_project_service" "firestore" {
  count   = local.gcp_l3_hot_enabled ? 1 : 0
  project = var.gcp_project_id
  service = "firestore.googleapis.com"
  
  disable_on_destroy = false
}

resource "google_project_service" "storage" {
  count   = local.gcp_l3_cold_enabled || local.gcp_l3_archive_enabled ? 1 : 0
  project = var.gcp_project_id
  service = "storage.googleapis.com"
  
  disable_on_destroy = false
}

resource "google_project_service" "eventarc" {
  count   = local.deploy_gcp ? 1 : 0
  project = var.gcp_project_id
  service = "eventarc.googleapis.com"
  
  disable_on_destroy = false
}

resource "google_project_service" "cloudbuild" {
  count   = local.deploy_gcp ? 1 : 0
  project = var.gcp_project_id
  service = "cloudbuild.googleapis.com"
  
  disable_on_destroy = false
}

resource "google_project_service" "cloudscheduler" {
  count   = local.gcp_l3_hot_enabled ? 1 : 0
  project = var.gcp_project_id
  service = "cloudscheduler.googleapis.com"
  
  disable_on_destroy = false
}

# ==============================================================================
# Service Account for Cloud Functions
# ==============================================================================

resource "google_service_account" "functions" {
  count        = local.deploy_gcp ? 1 : 0
  project      = var.gcp_project_id
  account_id   = "${var.digital_twin_name}-functions-sa"
  display_name = "${var.digital_twin_name} Cloud Functions Service Account"
}

# ==============================================================================
# Custom IAM Role for Cloud Functions (Least Privilege)
# ==============================================================================

resource "google_project_iam_custom_role" "functions_role" {
  count       = local.deploy_gcp ? 1 : 0
  project     = var.gcp_project_id
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
}

# Bind custom role to service account
resource "google_project_iam_member" "functions_custom_role" {
  count   = local.deploy_gcp ? 1 : 0
  project = var.gcp_project_id
  role    = google_project_iam_custom_role.functions_role[0].id
  member  = "serviceAccount:${google_service_account.functions[0].email}"
}

# ==============================================================================
# Cloud Storage Bucket for Function Source Code
# ==============================================================================

resource "google_storage_bucket" "function_source" {
  count         = local.deploy_gcp ? 1 : 0
  name          = "${var.gcp_project_id}-${var.digital_twin_name}-functions"
  location      = var.gcp_region
  force_destroy = true
  
  uniform_bucket_level_access = true
  
  labels = local.gcp_common_labels
}

