resource "aws_dynamodb_table" "users" {
  name         = "users"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "email"

  attribute {
    name = "email"
    type = "S"
  }

  tags = {
    Name        = "users"
    Environment = "prod"
    App         = var.app_name
  }
}

resource "aws_dynamodb_table" "user_emails" {
  name         = "user_emails"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_email"
  range_key    = "timestamp"

  attribute {
    name = "user_email"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  tags = {
    Name        = "user_emails"
    Environment = "prod"
    App         = var.app_name
  }
}

resource "aws_dynamodb_table" "pending_links" {
  name         = "pending_links"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "link_code"

  attribute {
    name = "link_code"
    type = "S"
  }

  tags = {
    Name        = "pending_links"
    Environment = "prod"
    App         = var.app_name
  }
}

resource "aws_dynamodb_table" "telegram" {
  name         = "telegram"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "telegram_id"

  attribute {
    name = "telegram_id"
    type = "S"
  }

  tags = {
    Name        = "telegram_id"
    Environment = "prod"
    App         = var.app_name
  }
}