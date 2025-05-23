variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "app_name" {
  description = "The name of the application"
  type        = string
  default     = "needl-email"
}

variable "telegram_id" {
  description = "The Telegram bot ID used to send messages to Telegram"
  type        = string
  default     = ""
}

locals {
  bucket           = "${var.app_name}-storage-raw"
  bedrock_model_id = "anthropic.claude-3-haiku-20240307-v1:0"
}
