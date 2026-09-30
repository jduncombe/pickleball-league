variable "aws_region" {
  description = "AWS region for everything except CloudFront (global)."
  type        = string
  default     = "ap-southeast-2"
}

variable "project" {
  description = "Name prefix for resources. Must match the bootstrap stack (the deploy role's IAM rights are scoped to it)."
  type        = string
  default     = "pickleball-league"
}

variable "environment" {
  description = "Environment name, used for tagging."
  type        = string
  default     = "production"
}

variable "api_image" {
  description = "Full API image reference, e.g. <account>.dkr.ecr.<region>.amazonaws.com/pickleball-league-api:<git sha>."
  type        = string
}

# --- Network (existing VPC, looked up) --------------------------------------------

variable "vpc_id" {
  description = "ID of the existing VPC. If empty, the VPC is looked up by vpc_name."
  type        = string
  default     = ""
}

variable "vpc_name" {
  description = "Name tag of the existing VPC, used when vpc_id is empty."
  type        = string
  default     = ""

  validation {
    condition     = var.vpc_id != "" || var.vpc_name != ""
    error_message = "Set vpc_id or vpc_name to identify the existing VPC."
  }
}

variable "private_subnet_tags" {
  description = "Tags identifying the VPC's private subnets (routed through a NAT gateway). The ALB, API tasks and RDS are placed in every matching subnet; they must span at least two AZs."
  type        = map(string)
  default     = { Tier = "private" }
}

# --- API (ECS Fargate) ------------------------------------------------------------

variable "api_cpu" {
  description = "Fargate task CPU units (256 = 0.25 vCPU). Tasks run on Graviton (ARM64)."
  type        = number
  default     = 256
}

variable "api_memory" {
  description = "Fargate task memory (MiB)."
  type        = number
  default     = 512
}

variable "api_desired_count" {
  description = "Number of API tasks."
  type        = number
  default     = 1
}

variable "log_retention_days" {
  description = "CloudWatch log retention for the API."
  type        = number
  default     = 30
}

# --- Database (RDS PostgreSQL) -------------------------------------------------------

variable "db_instance_class" {
  description = "RDS instance class. Graviton (t4g/m7g/r7g) classes are cheaper than their Intel equivalents."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "RDS storage (GiB)."
  type        = number
  default     = 20
}

variable "db_multi_az" {
  description = "Run a standby replica in a second AZ (roughly doubles database cost)."
  type        = bool
  default     = false
}

variable "db_backup_retention_days" {
  description = "Automated backup retention (days)."
  type        = number
  default     = 7
}

variable "db_deletion_protection" {
  description = "Block deletion of the database. Set false (and apply) before `terraform destroy`."
  type        = bool
  default     = true
}

# --- Web (S3 + CloudFront) ----------------------------------------------------------

variable "cloudfront_price_class" {
  description = "CloudFront price class (edge locations used)."
  type        = string
  default     = "PriceClass_100"
}

variable "domain_names" {
  description = "Optional custom domain names for the site. Requires acm_certificate_arn."
  type        = list(string)
  default     = []
}

variable "acm_certificate_arn" {
  description = "ACM certificate in us-east-1 covering domain_names. Leave empty to use the *.cloudfront.net domain."
  type        = string
  default     = ""

  validation {
    condition     = var.acm_certificate_arn == "" || can(regex("^arn:aws:acm:us-east-1:", var.acm_certificate_arn))
    error_message = "CloudFront certificates must be issued in us-east-1."
  }
}
