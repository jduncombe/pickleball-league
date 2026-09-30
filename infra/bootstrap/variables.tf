variable "aws_region" {
  description = "Region for the state bucket, ECR repository and the app stack."
  type        = string
  default     = "eu-west-2"
}

variable "project" {
  description = "Name prefix for all resources. IAM permissions for the deploy role are scoped to it."
  type        = string
  default     = "pickleball-league"
}

variable "github_repository" {
  description = "GitHub repository (owner/name) allowed to assume the deploy role."
  type        = string
  default     = "jduncombe/pickleball-league"
}

variable "github_environment" {
  description = "GitHub Actions environment the deploy job runs in. Only that environment can assume the role."
  type        = string
  default     = "production"
}

variable "create_github_oidc_provider" {
  description = "Create the GitHub Actions OIDC provider. Set false if the account already has one (only one is allowed per account)."
  type        = bool
  default     = true
}
