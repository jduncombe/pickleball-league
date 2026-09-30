# Static site in a private S3 bucket, served by CloudFront. CloudFront also
# routes /api/* to the internal API load balancer, so the browser only ever
# talks to one origin (no CORS, one domain/certificate).

# --- S3 -----------------------------------------------------------------------------

resource "aws_s3_bucket" "web" {
  bucket = "${local.name}-web-${local.account_id}"
  # Contents are build output, re-uploaded on every deploy.
  force_destroy = true
}

resource "aws_s3_bucket_ownership_controls" "web" {
  bucket = aws_s3_bucket.web.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "web" {
  bucket                  = aws_s3_bucket.web.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "web" {
  bucket = aws_s3_bucket.web.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

data "aws_iam_policy_document" "web_bucket" {
  statement {
    sid       = "CloudFrontRead"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.web.arn}/*"]
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.main.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "web" {
  bucket = aws_s3_bucket.web.id
  policy = data.aws_iam_policy_document.web_bucket.json

  depends_on = [aws_s3_bucket_public_access_block.web]
}

# --- CloudFront --------------------------------------------------------------------

resource "aws_cloudfront_origin_access_control" "web" {
  name                              = "${local.name}-web"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# Lets CloudFront reach the internal ALB privately (no public API endpoint).
# Traffic between CloudFront and the ALB stays on the AWS network.
resource "aws_cloudfront_vpc_origin" "api" {
  vpc_origin_endpoint_config {
    name                   = "${local.name}-api"
    arn                    = aws_lb.api.arn
    http_port              = 80
    https_port             = 443
    origin_protocol_policy = "http-only"

    origin_ssl_protocols {
      items    = ["TLSv1.2"]
      quantity = 1
    }
  }
}

resource "aws_cloudfront_function" "web_rewrite" {
  name    = "${local.name}-web-rewrite"
  runtime = "cloudfront-js-2.0"
  comment = "Map directory URLs to index.html"
  publish = true
  code    = file("${path.module}/functions/web-rewrite.js")
}

resource "aws_cloudfront_function" "api_strip_prefix" {
  name    = "${local.name}-api-strip-prefix"
  runtime = "cloudfront-js-2.0"
  comment = "Strip the /api prefix before forwarding to the API"
  publish = true
  code    = file("${path.module}/functions/api-strip-prefix.js")
}

data "aws_cloudfront_cache_policy" "caching_optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_cache_policy" "caching_disabled" {
  name = "Managed-CachingDisabled"
}

data "aws_cloudfront_origin_request_policy" "all_viewer_except_host" {
  name = "Managed-AllViewerExceptHostHeader"
}

data "aws_cloudfront_response_headers_policy" "security_headers" {
  name = "Managed-SecurityHeadersPolicy"
}

locals {
  web_origin_id = "web-s3"
  api_origin_id = "api-alb"
}

resource "aws_cloudfront_distribution" "main" {
  enabled             = true
  comment             = local.name
  default_root_object = "index.html"
  price_class         = var.cloudfront_price_class
  http_version        = "http2and3"
  is_ipv6_enabled     = true
  aliases             = var.domain_names

  origin {
    origin_id                = local.web_origin_id
    domain_name              = aws_s3_bucket.web.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.web.id
  }

  origin {
    origin_id   = local.api_origin_id
    domain_name = aws_lb.api.dns_name

    vpc_origin_config {
      vpc_origin_id            = aws_cloudfront_vpc_origin.api.id
      origin_read_timeout      = 30
      origin_keepalive_timeout = 5
    }
  }

  # Static site. HTML is uploaded with Cache-Control: no-cache and hashed
  # assets under /_next/static/ with a one-year immutable TTL (deploy workflow).
  default_cache_behavior {
    target_origin_id           = local.web_origin_id
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS"]
    cached_methods             = ["GET", "HEAD"]
    compress                   = true
    cache_policy_id            = data.aws_cloudfront_cache_policy.caching_optimized.id
    response_headers_policy_id = data.aws_cloudfront_response_headers_policy.security_headers.id

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.web_rewrite.arn
    }
  }

  ordered_cache_behavior {
    path_pattern             = "/api/*"
    target_origin_id         = local.api_origin_id
    viewer_protocol_policy   = "redirect-to-https"
    allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods           = ["GET", "HEAD"]
    compress                 = true
    cache_policy_id          = data.aws_cloudfront_cache_policy.caching_disabled.id
    origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_viewer_except_host.id

    function_association {
      event_type   = "viewer-request"
      function_arn = aws_cloudfront_function.api_strip_prefix.arn
    }
  }

  # S3 answers 403 for missing keys (CloudFront has no ListBucket permission),
  # so serve the site's 404 page. Note this applies to every origin: the API
  # must not use 403 for its own errors (use 401, or scope this differently
  # when auth is added).
  custom_error_response {
    error_code            = 403
    response_code         = 404
    response_page_path    = "/404.html"
    error_caching_min_ttl = 10
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = var.acm_certificate_arn == ""
    acm_certificate_arn            = var.acm_certificate_arn == "" ? null : var.acm_certificate_arn
    ssl_support_method             = var.acm_certificate_arn == "" ? null : "sni-only"
    minimum_protocol_version       = var.acm_certificate_arn == "" ? "TLSv1" : "TLSv1.2_2021"
  }
}
