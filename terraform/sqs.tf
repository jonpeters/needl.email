resource "aws_sqs_queue" "ses_email_queue" {
  name                       = "${var.app_name}-raw"
  visibility_timeout_seconds = 60
}

resource "aws_sqs_queue" "sanitized_queue" {
  name                       = "${var.app_name}-sanitized"
  visibility_timeout_seconds = 60
}

resource "aws_sqs_queue" "chat_queue" {
  name                       = "${var.app_name}-chat"
  visibility_timeout_seconds = 60
}


resource "aws_sqs_queue" "notify_queue" {
  name                       = "${var.app_name}-notify"
  visibility_timeout_seconds = 60
}