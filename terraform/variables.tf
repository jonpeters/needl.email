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
  default     = "7938788653:AAGAUsR7P83Z5l-cUCPn4IfUdLUurfVtvJc"
}

locals {
  bucket = "${var.app_name}-storage"
}
