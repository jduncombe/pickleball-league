# Offline test of the app stack: a mocked AWS provider (no credentials, nothing
# created) checks that the pieces are wired together as intended.
# Run with: terraform init -backend=false && terraform test

mock_provider "aws" {
  mock_data "aws_availability_zones" {
    defaults = { names = ["eu-west-2a", "eu-west-2b", "eu-west-2c"] }
  }
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
  mock_data "aws_iam_policy_document" {
    defaults = { json = "{}" }
  }
  mock_resource "aws_db_instance" {
    defaults = {
      address = "db.internal"
      port    = 5432
      master_user_secret = [{
        secret_arn    = "arn:aws:secretsmanager:eu-west-2:123456789012:secret:rds-db-abc"
        kms_key_id    = ""
        secret_status = "active"
      }]
    }
  }
  mock_resource "aws_cloudfront_distribution" {
    defaults = {
      arn         = "arn:aws:cloudfront::123456789012:distribution/EXAMPLE"
      domain_name = "d111111abcdef8.cloudfront.net"
    }
  }
  mock_resource "aws_cloudfront_function" {
    defaults = { arn = "arn:aws:cloudfront::123456789012:function/example" }
  }
  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::123456789012:role/example" }
  }
  mock_resource "aws_lb" {
    defaults = { arn = "arn:aws:elasticloadbalancing:eu-west-2:123456789012:loadbalancer/app/example/abc" }
  }
  mock_resource "aws_lb_target_group" {
    defaults = { arn = "arn:aws:elasticloadbalancing:eu-west-2:123456789012:targetgroup/example/abc" }
  }
  mock_resource "aws_ecs_task_definition" {
    defaults = { arn = "arn:aws:ecs:eu-west-2:123456789012:task-definition/example:1" }
  }
  mock_resource "aws_s3_bucket" {
    defaults = { arn = "arn:aws:s3:::example" }
  }
}

variables {
  api_image = "123456789012.dkr.ecr.eu-west-2.amazonaws.com/pickleball-league-api:test"
}

run "default_configuration" {
  command = apply

  assert {
    condition     = length(aws_subnet.public) == 2 && length(aws_subnet.private) == 2
    error_message = "Expected two public and two private subnets."
  }

  assert {
    condition     = aws_lb.api.internal
    error_message = "The API load balancer must be internal (reached via CloudFront VPC origin)."
  }

  assert {
    condition     = !aws_db_instance.main.publicly_accessible && aws_db_instance.main.storage_encrypted
    error_message = "The database must be private and encrypted."
  }

  assert {
    condition     = one([for b in aws_cloudfront_distribution.main.ordered_cache_behavior : b.target_origin_id if b.path_pattern == "/api/*"]) == "api-alb"
    error_message = "/api/* must be routed to the API origin."
  }

  assert {
    condition = [
      for s in jsondecode(aws_ecs_task_definition.api.container_definitions)[0].secrets : s.valueFrom
      ] == [
      "arn:aws:secretsmanager:eu-west-2:123456789012:secret:rds-db-abc:username::",
      "arn:aws:secretsmanager:eu-west-2:123456789012:secret:rds-db-abc:password::",
    ]
    error_message = "DB credentials must come from the RDS-managed secret."
  }

  assert {
    condition = contains(
      [for e in jsondecode(aws_ecs_task_definition.api.container_definitions)[0].environment : "${e.name}=${e.value}"],
      "ROOT_PATH=/api"
    )
    error_message = "The API must know it is served under /api."
  }

  assert {
    condition     = output.site_url == "https://d111111abcdef8.cloudfront.net"
    error_message = "site_url should default to the CloudFront domain."
  }
}

run "custom_domain" {
  command = apply

  variables {
    domain_names        = ["league.example.com"]
    acm_certificate_arn = "arn:aws:acm:us-east-1:123456789012:certificate/abc"
  }

  assert {
    condition     = output.site_url == "https://league.example.com"
    error_message = "site_url should use the custom domain."
  }
}

run "rejects_regional_certificate" {
  command = plan

  variables {
    acm_certificate_arn = "arn:aws:acm:eu-west-2:123456789012:certificate/abc"
  }

  expect_failures = [var.acm_certificate_arn]
}
