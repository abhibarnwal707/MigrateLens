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
  account_id   = "iot-sns-sqs-ddb-sa"
  display_name = "iot-sns-sqs-ddb runtime service account"
}

# SQS -> Pub/Sub topic + pull subscription
resource "google_pubsub_topic" "queue" {
  name = "iot-sns-sqs-ddb-queue"
}

resource "google_pubsub_subscription" "queue" {
  name                 = "iot-sns-sqs-ddb-queue-sub"
  topic                = google_pubsub_topic.queue.id
  ack_deadline_seconds = 30
}

resource "google_pubsub_topic_iam_member" "queue_publish" {
  topic  = google_pubsub_topic.queue.name
  role   = "roles/pubsub.publisher"
  member = google_service_account.app.member
}

resource "google_pubsub_subscription_iam_member" "queue_consume" {
  subscription = google_pubsub_subscription.queue.name
  role         = "roles/pubsub.subscriber"
  member       = google_service_account.app.member
}

# SNS -> Pub/Sub topic
resource "google_pubsub_topic" "events" {
  name = "iot-sns-sqs-ddb-events"
}

resource "google_pubsub_topic_iam_member" "events_publish" {
  topic  = google_pubsub_topic.events.name
  role   = "roles/pubsub.publisher"
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
  name                = "iot-sns-sqs-ddb"
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
        name  = "PUBSUB_QUEUE_TOPIC"
        value = google_pubsub_topic.queue.name
      }
      env {
        name  = "PUBSUB_EVENTS_TOPIC"
        value = google_pubsub_topic.events.name
      }
    }
  }
}
