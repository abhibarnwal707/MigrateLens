terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {
  type        = string
  description = "Target Google Cloud project (never applied by MigrateLens)"
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "image" {
  type        = string
  description = "Container image for the Cloud Run service"
}

resource "google_service_account" "app" {
  account_id   = "twilio-apigw-sa"
  display_name = "twilio-apigw runtime service account"
}

# S3 -> Cloud Storage
resource "google_storage_bucket" "data" {
  name                        = "${var.project_id}-twilio-apigw-data"
  location                    = var.region
  uniform_bucket_level_access = true
}

resource "google_storage_bucket_iam_member" "data_rw" {
  bucket = google_storage_bucket.data.name
  role   = "roles/storage.objectUser"
  member = google_service_account.app.member
}

# DynamoDB -> Firestore (Native mode); Bigtable for huge throughput.
resource "google_firestore_database" "main" {
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"
}

resource "google_project_iam_member" "firestore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = google_service_account.app.member
}
# Note: granted project-wide; scope it down with an IAM condition before real use.

# Lambda / ECS (Fargate) -> Cloud Run
resource "google_cloud_run_v2_service" "app" {
  name                = "twilio-apigw"
  location            = var.region
  deletion_protection = false

  template {
    service_account = google_service_account.app.email
    containers {
      image = var.image
      ports {
        container_port = 8080
      }
      env {
        name  = "GCS_BUCKET"
        value = google_storage_bucket.data.name
      }
    }
  }
}

# No Terraform generated for: API Gateway (see the mapping table; these need a manual decision).
