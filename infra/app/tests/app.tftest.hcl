# Offline test of the app stack: a mocked AWS provider (no credentials, nothing
# created) checks that the pieces are wired together as intended.
# Run with: terraform init -backend=false && terraform test

mock_provider "aws" {
  mock_data "aws_vpc" {
    defaults = { id = "vpc-0123456789abcdef0", cidr_block = "10.20.0.0/16" }
  }
  mock_data "aws_subnets" {
    defaults = { ids = ["subnet-bbbb", "subnet-aaaa"] }
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
        secret_arn    = "arn:aws:secretsmanager:ap-southeast-2:123456789012:secret:rds-db-abc"
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
    defaults = { arn = "arn:aws:elasticloadbalancing:ap-southeast-2:123456789012:loadbalancer/app/example/abc" }
  }
  mock_resource "aws_lb_target_group" {
    defaults = { arn = "arn:aws:elasticloadbalancing:ap-southeast-2:123456789012:targetgroup/example/abc" }
  }
  mock_resource "aws_ecs_task_definition" {
    defaults = { arn = "arn:aws:ecs:ap-southeast-2:123456789012:task-definition/example:1" }
  }
  mock_resource "aws_s3_bucket" {
    defaults = { arn = "arn:aws:s3:::example" }
  }
}

# Each looked-up private subnet sits in a different AZ.
override_data {
  target = data.aws_subnet.private["subnet-aaaa"]
  values = { id = "subnet-aaaa", availability_zone = "ap-southeast-2a" }
}

override_data {
  target = data.aws_subnet.private["subnet-bbbb"]
  values = { id = "subnet-bbbb", availability_zone = "ap-southeast-2b" }
}

variables {
  api_image = "123456789012.dkr.ecr.ap-southeast-2.amazonaws.com/pickleball-league-api:test"
  vpc_name  = "existing-vpc"
}

run "default_configuration" {
  command = apply

  assert {
    condition     = aws_lb.api.subnets == toset(["subnet-aaaa", "subnet-bbbb"])
    error_message = "The ALB must use the looked-up private subnets."
  }

  assert {
    condition = (
      !one(aws_ecs_service.api.network_configuration).assign_public_ip &&
      one(aws_ecs_service.api.network_configuration).subnets == toset(["subnet-aaaa", "subnet-bbbb"])
    )
    error_message = "API tasks must run in the private subnets without public IPs."
  }

  assert {
    condition     = aws_db_subnet_group.main.subnet_ids == toset(["subnet-aaaa", "subnet-bbbb"])
    error_message = "RDS must use the looked-up private subnets."
  }

  assert {
    condition     = aws_vpc_security_group_ingress_rule.alb_http.cidr_ipv4 == "10.20.0.0/16"
    error_message = "The ALB should admit the VPC's CIDR (CloudFront VPC origin)."
  }

  assert {
    condition     = one(aws_ecs_task_definition.api.runtime_platform).cpu_architecture == "ARM64"
    error_message = "The API should run on Graviton (ARM64)."
  }

  assert {
    condition     = startswith(aws_db_instance.main.instance_class, "db.t4g.")
    error_message = "The default database instance should be Graviton (t4g)."
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
      "arn:aws:secretsmanager:ap-southeast-2:123456789012:secret:rds-db-abc:username::",
      "arn:aws:secretsmanager:ap-southeast-2:123456789012:secret:rds-db-abc:password::",
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

run "rejects_single_az_subnets" {
  command = plan

  override_data {
    target = data.aws_subnet.private["subnet-bbbb"]
    values = { id = "subnet-bbbb", availability_zone = "ap-southeast-2a" }
  }

  expect_failures = [check.private_subnets_span_two_azs]
}

run "requires_vpc_identifier" {
  command = plan

  variables {
    vpc_name = ""
  }

  expect_failures = [var.vpc_name]
}

run "rejects_regional_certificate" {
  command = plan

  variables {
    acm_certificate_arn = "arn:aws:acm:ap-southeast-2:123456789012:certificate/abc"
  }

  expect_failures = [var.acm_certificate_arn]
}
