# The VPC is not managed here: this stack deploys into an existing VPC that
# already has private subnets with outbound internet access through a NAT
# gateway. It is found by the tfvars-driven lookups below.
#
# Everything this stack creates in the VPC (internal ALB, API tasks, RDS) goes
# in the private subnets; nothing gets a public IP. CloudFront reaches the ALB
# through a VPC origin, which requires the VPC to have an internet gateway
# attached (any VPC with a NAT gateway does).

data "aws_vpc" "selected" {
  id = var.vpc_id != "" ? var.vpc_id : null

  tags = var.vpc_id != "" ? null : { Name = var.vpc_name }
}

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.selected.id]
  }

  tags = var.private_subnet_tags
}

data "aws_subnet" "private" {
  for_each = toset(data.aws_subnets.private.ids)
  id       = each.value
}

locals {
  vpc_id             = data.aws_vpc.selected.id
  vpc_cidr           = data.aws_vpc.selected.cidr_block
  private_subnet_ids = sort(data.aws_subnets.private.ids)
  private_subnet_azs = toset([for s in data.aws_subnet.private : s.availability_zone])
}

# Fail at plan time, with a clear message, if the lookup finds the wrong subnets.
check "private_subnets_span_two_azs" {
  assert {
    condition     = length(local.private_subnet_azs) >= 2
    error_message = "The private subnet lookup (private_subnet_tags) must match subnets in at least two availability zones; the ALB and RDS require it."
  }
}
