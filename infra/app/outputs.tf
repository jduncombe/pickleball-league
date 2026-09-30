output "site_url" {
  description = "Public URL of the site (the API is under /api)."
  value       = "https://${length(var.domain_names) > 0 ? var.domain_names[0] : aws_cloudfront_distribution.main.domain_name}"
}

output "cloudfront_domain_name" {
  description = "CloudFront domain; point custom DNS (CNAME/alias) here."
  value       = aws_cloudfront_distribution.main.domain_name
}

output "cloudfront_distribution_id" {
  description = "Distribution to invalidate after uploading the site."
  value       = aws_cloudfront_distribution.main.id
}

output "web_bucket" {
  description = "S3 bucket the static site is uploaded to."
  value       = aws_s3_bucket.web.bucket
}

output "ecs_cluster" {
  value = aws_ecs_cluster.main.name
}

output "ecs_service" {
  value = aws_ecs_service.api.name
}

output "api_log_group" {
  description = "CloudWatch log group for the API containers."
  value       = aws_cloudwatch_log_group.api.name
}

output "db_endpoint" {
  description = "RDS endpoint (private; reachable from inside the VPC only)."
  value       = aws_db_instance.main.endpoint
}

output "db_secret_arn" {
  description = "Secrets Manager secret holding the database credentials."
  value       = local.db_secret_arn
}
