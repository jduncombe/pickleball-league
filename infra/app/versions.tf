terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # bucket and region are supplied at init time:
  #   terraform init -backend-config="bucket=<TF_STATE_BUCKET>" -backend-config="region=<AWS_REGION>"
  backend "s3" {
    key          = "app/terraform.tfstate"
    use_lockfile = true
    encrypt      = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  name       = var.project
  account_id = data.aws_caller_identity.current.account_id
}
