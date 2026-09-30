# Copy these into the GitHub repository's variables (Settings -> Secrets and
# variables -> Actions -> Variables); see docs/deployment.md.

output "github_variables" {
  description = "Repository variables for the deploy workflow."
  value = {
    AWS_REGION          = var.aws_region
    AWS_DEPLOY_ROLE_ARN = aws_iam_role.deploy.arn
    ECR_REPOSITORY_URL  = aws_ecr_repository.api.repository_url
    TF_STATE_BUCKET     = aws_s3_bucket.tf_state.bucket
  }
}
