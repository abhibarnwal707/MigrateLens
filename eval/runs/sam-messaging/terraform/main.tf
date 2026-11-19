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
  account_id   = "sam-messaging-sa"
  display_name = "sam-messaging runtime service account"
}

# SQS -> Pub/Sub topic + pull subscription
resource "google_pubsub_topic" "queue" {
  name = "sam-messaging-queue"
}

resource "google_pubsub_subscription" "queue" {
  name                 = "sam-messaging-queue-sub"
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
  name = "sam-messaging-events"
}

resource "google_pubsub_topic_iam_member" "events_publish" {
  topic  = google_pubsub_topic.events.name
  role   = "roles/pubsub.publisher"
  member = google_service_account.app.member
}

# Lambda / ECS (Fargate) -> Cloud Run
resource "google_cloud_run_v2_service" "app" {
  name                = "sam-messaging"
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

# No Terraform generated for: EventBridge (see the mapping table; these need a manual decision).
