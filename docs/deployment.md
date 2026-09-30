# Deployment (AWS)

```
                      ┌────────────────────── CloudFront (HTTPS) ──────────────────────┐
  Browser ──HTTPS──▶  │  /*      ──▶ S3 bucket (private, Origin Access Control)        │
                      │  /api/*  ──▶ VPC origin ──▶ internal ALB ──▶ ECS Fargate (API) │
                      └────────────────────────────────────────────────────────────────┘
                                                                        │
                                                                        ▼
                                                            RDS PostgreSQL (private)
```

- **Web:** the Next.js static export (`web/out/`) in a private S3 bucket, served
  by CloudFront. A CloudFront Function maps `/league/teams/` to
  `league/teams/index.html`.
- **API:** the `api/` image on ECS Fargate behind an **internal** Application
  Load Balancer. CloudFront reaches it through a
  [VPC origin](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-vpc-origins.html),
  so the API has no public endpoint and the browser uses a single origin (no
  CORS). A second CloudFront Function strips the `/api` prefix.
- **Database:** RDS PostgreSQL 17 in private subnets. RDS generates the master
  password and stores it in Secrets Manager; ECS injects it into the container.
- **State and images:** a bootstrap stack creates the Terraform state bucket,
  the ECR repository and the GitHub Actions deploy role.

Terraform lives in [`infra/`](../infra):

| Stack | Applied by | State | Contents |
| --- | --- | --- | --- |
| `infra/bootstrap` | You, once, with admin credentials | local | State bucket, ECR repository, GitHub OIDC provider + deploy role |
| `infra/app` | The deploy workflow, on every push to `main` | S3 (from bootstrap) | VPC, RDS, ECS, ALB, S3 site bucket, CloudFront |

## One-time setup

You need an AWS account, the AWS CLI logged in with admin rights, and
Terraform ≥ 1.10.

1. **Bootstrap AWS resources**

   ```bash
   cd infra/bootstrap
   terraform init
   terraform apply            # optionally -var aws_region=... -var github_repository=owner/repo
   terraform output github_variables
   ```

   If the account already has a GitHub Actions OIDC provider, add
   `-var create_github_oidc_provider=false`.

   This stack keeps its state locally in `terraform.tfstate` (git-ignored).
   Keep that file safe, or move it into the new bucket by adding a
   `backend "s3"` block and running `terraform init -migrate-state`.

2. **Configure GitHub.** In the repository settings, go to *Secrets and
   variables → Actions → Variables* and add the four values from
   `github_variables`:

   | Variable | Example |
   | --- | --- |
   | `AWS_REGION` | `eu-west-2` |
   | `AWS_DEPLOY_ROLE_ARN` | `arn:aws:iam::123456789012:role/pickleball-league-github-deploy` |
   | `ECR_REPOSITORY_URL` | `123456789012.dkr.ecr.eu-west-2.amazonaws.com/pickleball-league-api` |
   | `TF_STATE_BUCKET` | `pickleball-league-tfstate-123456789012` |

   None of these are secret: the workflow authenticates with OIDC and there are
   no stored AWS keys. The deploy role only trusts jobs running in this
   repository's `production` environment. GitHub creates that environment on
   the first deploy; add required reviewers to it (*Settings → Environments*)
   if you want deploys to need approval.

3. **Deploy.** Push to `main`, or run the *Deploy* workflow by hand
   (*Actions → Deploy → Run workflow*). The first run takes roughly 20–30
   minutes, mostly RDS and CloudFront being created. The site URL appears in
   the run summary and on the `production` environment.

Until `AWS_DEPLOY_ROLE_ARN` is set, the Deploy workflow runs the CI checks and
skips the deploy job.

## What a deploy does

[`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml), on every
push to `main`:

1. Runs the full CI workflow (API tests on SQLite and Postgres, web build,
   Docker builds, Terraform checks). Nothing deploys if it fails.
2. Builds the API image and pushes it to ECR tagged with the commit SHA.
3. Runs `terraform apply` on `infra/app` with `api_image=<repo>:<sha>`. The
   apply waits for the ECS service to become stable on the new task
   definition. If the new tasks fail their health checks, ECS rolls back to
   the previous version and the workflow fails.
4. Builds the static site and syncs it to S3. Hashed assets under
   `_next/static/` are cached for a year; HTML is `no-cache`.
5. Invalidates CloudFront.

Deploys are queued, never run in parallel, so two `terraform apply` runs never
overlap. The S3 state backend also takes a lock.

**Rolling back:** revert the offending commit on `main`. The deploy of the
revert redeploys the previous code. Images stay in ECR (the 30 most recent
are kept).

## Operating it

```bash
# API logs
aws logs tail /ecs/pickleball-league-api --follow

# Service status / recent events
aws ecs describe-services --cluster pickleball-league --services pickleball-league-api \
  --query 'services[0].{running:runningCount,desired:desiredCount,events:events[:5].message}'

# Database credentials
aws secretsmanager get-secret-value --secret-id "$(terraform -chdir=infra/app output -raw db_secret_arn)"
```

The database is only reachable from inside the VPC. For ad-hoc SQL, run a
one-off task in the cluster, add a bastion or SSM instance, or enable ECS Exec
on the service.

Local `terraform plan` against the real state:

```bash
cd infra/app
terraform init -backend-config="bucket=<TF_STATE_BUCKET>" -backend-config="region=<AWS_REGION>"
terraform plan -var="api_image=<ECR_REPOSITORY_URL>:<currently deployed sha>"
```

Pass the currently deployed image. Any other value is a real change, and
applying it would roll the service.

### Custom domain

1. Request an ACM certificate for the domain **in us-east-1** (a CloudFront
   requirement) and validate it.
2. Set `domain_names = ["league.example.com"]` and `acm_certificate_arn` in
   `infra/app/variables.tf` defaults, or pass them as `-var` flags in
   `deploy.yml`.
3. Point DNS (a CNAME, or a Route 53 alias) at the `cloudfront_domain_name`
   output.

### Tearing down

```bash
cd infra/app
terraform apply -var db_deletion_protection=false -var api_image=<current image>
terraform destroy -var api_image=<current image>
```

RDS takes a final snapshot (`pickleball-league-final`) on destroy. Then destroy
`infra/bootstrap`. Empty the ECR repository and state bucket first, or delete
them by hand.

## Cost

With the defaults, the running cost is roughly **US$45–55/month** before free
tier. Check the AWS pricing pages for your region:

| Item | Approx. / month |
| --- | --- |
| Application Load Balancer | $18–20 |
| RDS `db.t4g.micro` + 20 GB gp3 | $15–17 |
| Fargate, 1 × 0.25 vCPU / 0.5 GB | $9–10 |
| Public IPv4 address for the task | $3.60 |
| Secrets Manager, CloudWatch Logs, S3, CloudFront | ~$1–3 at league-scale traffic |

`db_multi_az = true` roughly doubles the database line.

## Security notes and hardening options

In place now:

- The S3 bucket is private and readable only by this distribution (Origin
  Access Control).
- The ALB is internal and admits only traffic from inside the VPC. The API
  tasks admit only the ALB. The database admits only the API tasks.
- The database is encrypted, not publicly accessible, has 7-day backups and
  deletion protection, and takes a final snapshot on destroy.
- GitHub → AWS uses OIDC, scoped to this repository's `production`
  environment. The deploy role has PowerUserAccess plus IAM rights limited to
  `pickleball-league-*` roles.
- Images are immutable, tagged by commit, and scanned on push.

Deliberate trade-offs worth revisiting:

- **Tasks in public subnets.** API tasks run in public subnets with a public
  IP, for outbound access to ECR, Secrets Manager and CloudWatch, which avoids
  a ~$35/month NAT gateway. Their security group still blocks all inbound
  traffic except from the ALB. To move them to private subnets, add a NAT
  gateway or VPC endpoints (ECR API/DKR, S3 gateway, Secrets Manager, Logs).
- **HTTP between CloudFront and the ALB.** This hop is private (VPC origin,
  AWS network), not the public internet. For end-to-end TLS, add an HTTPS
  listener with an ACM certificate and set `origin_protocol_policy =
  "https-only"`.
- **No WAF.** Attach AWS WAF to the distribution (rate limiting, managed rule
  groups) once the site is public.
- **No authentication.** Anyone with the URL can edit leagues. See
  [architecture.md](architecture.md#known-gaps--next-steps).
- **CloudFront 403 handling.** CloudFront turns *any* 403 into the site's 404
  page, because S3 returns 403 for missing files. The API must not return
  403 until that is scoped differently.
- **One API task.** Tables are created at startup, so run one task until
  Alembic migrations are in place (see architecture.md). After that,
  `api_desired_count` can go up, and ECS auto scaling can be added.
