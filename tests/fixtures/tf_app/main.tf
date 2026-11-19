provider "aws" {
  region = "us-east-1"
}

resource "aws_sns_topic" "alerts" {
  name = "alerts"
}

resource "aws_dynamodb_table" "orders" {
  name = "orders"
}
