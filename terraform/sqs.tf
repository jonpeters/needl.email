resource "aws_sqs_queue" "ses_email_queue" {
  name = "${var.app_name}-raw"
}
