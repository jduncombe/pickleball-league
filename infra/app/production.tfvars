# Settings for the production deploy (deploy.yml passes -var-file=production.tfvars).
# api_image is supplied by the workflow.
#
# TODO before enabling the deploy job: point these at the real VPC.

aws_region = "ap-southeast-2"

# Existing VPC, looked up by its Name tag (or set vpc_id instead).
vpc_name = "pickleball-league"

# Tags that select the VPC's private (NAT-routed) subnets, in at least two AZs.
private_subnet_tags = { Tier = "private" }
