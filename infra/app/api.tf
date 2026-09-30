# API: ECS Fargate service behind an internal Application Load Balancer.
# CloudFront reaches the ALB through a VPC origin (web.tf).

locals {
  api_port = 8000
  # Secrets Manager secret created by RDS: {"username": ..., "password": ...}
  db_secret_arn = aws_db_instance.main.master_user_secret[0].secret_arn
}

# --- Load balancer ----------------------------------------------------------------

resource "aws_security_group" "alb" {
  name        = "${local.name}-alb"
  description = "Internal API load balancer, reached by CloudFront VPC origin"
  vpc_id      = local.vpc_id
}

# CloudFront's VPC origin connects from network interfaces inside this VPC.
resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = local.vpc_cidr
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
  description       = "CloudFront VPC origin"
}

resource "aws_vpc_security_group_egress_rule" "alb_to_api" {
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = aws_security_group.api.id
  ip_protocol                  = "tcp"
  from_port                    = local.api_port
  to_port                      = local.api_port
  description                  = "API tasks"
}

resource "aws_lb" "api" {
  name               = "${local.name}-api"
  internal           = true
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = local.private_subnet_ids

  drop_invalid_header_fields = true
}

resource "aws_lb_target_group" "api" {
  name        = "${local.name}-api"
  port        = local.api_port
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = local.vpc_id

  deregistration_delay = 30

  health_check {
    path                = "/health"
    matcher             = "200"
    interval            = 15
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "api_http" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# --- IAM ------------------------------------------------------------------------

data "aws_iam_policy_document" "ecs_tasks_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# Used by ECS itself: pull the image, write logs, read the DB secret.
resource "aws_iam_role" "api_execution" {
  name               = "${local.name}-api-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json
}

resource "aws_iam_role_policy_attachment" "api_execution" {
  role       = aws_iam_role.api_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "api_execution_secrets" {
  statement {
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [local.db_secret_arn]
  }
}

resource "aws_iam_role_policy" "api_execution_secrets" {
  name   = "read-db-secret"
  role   = aws_iam_role.api_execution.id
  policy = data.aws_iam_policy_document.api_execution_secrets.json
}

# Assumed by the application code. No permissions yet (e.g. add DUPR API
# credentials access here later).
resource "aws_iam_role" "api_task" {
  name               = "${local.name}-api-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_trust.json
}

# --- ECS --------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${local.name}-api"
  retention_in_days = var.log_retention_days
}

resource "aws_ecs_cluster" "main" {
  name = local.name
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.name}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.api_execution.arn
  task_role_arn            = aws_iam_role.api_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64" # Graviton; the deploy workflow builds a linux/arm64 image
  }

  container_definitions = jsonencode([{
    name         = "api"
    image        = var.api_image
    essential    = true
    portMappings = [{ containerPort = local.api_port, protocol = "tcp" }]

    # See api/app/config.py: DATABASE_URL is assembled from the DB_* parts.
    environment = [
      { name = "DB_HOST", value = aws_db_instance.main.address },
      { name = "DB_PORT", value = tostring(aws_db_instance.main.port) },
      { name = "DB_NAME", value = aws_db_instance.main.db_name },
      { name = "ROOT_PATH", value = "/api" },
      # Browsers reach the API same-origin through CloudFront; no CORS needed.
      { name = "CORS_ORIGINS", value = "" },
    ]
    secrets = [
      { name = "DB_USER", valueFrom = "${local.db_secret_arn}:username::" },
      { name = "DB_PASSWORD", valueFrom = "${local.db_secret_arn}:password::" },
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.api.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "api"
      }
    }
  }])
}

resource "aws_security_group" "api" {
  name        = "${local.name}-api"
  description = "API tasks: inbound from the ALB only"
  vpc_id      = local.vpc_id
}

resource "aws_vpc_security_group_ingress_rule" "api_from_alb" {
  security_group_id            = aws_security_group.api.id
  referenced_security_group_id = aws_security_group.alb.id
  ip_protocol                  = "tcp"
  from_port                    = local.api_port
  to_port                      = local.api_port
  description                  = "ALB"
}

resource "aws_vpc_security_group_egress_rule" "api_all" {
  security_group_id = aws_security_group.api.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
  description       = "ECR, Secrets Manager, CloudWatch Logs (via NAT), RDS"
}

resource "aws_ecs_service" "api" {
  name            = "${local.name}-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  # Private subnets, no public IP: outbound traffic (ECR, Secrets Manager,
  # CloudWatch Logs) goes through the VPC's NAT gateway.
  network_configuration {
    subnets          = local.private_subnet_ids
    security_groups  = [aws_security_group.api.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = local.api_port
  }

  health_check_grace_period_seconds = 60

  # Roll back automatically if new tasks never become healthy, and make
  # `terraform apply` (and so the deploy workflow) fail in that case.
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
  wait_for_steady_state = true

  depends_on = [aws_lb_listener.api_http]
}
