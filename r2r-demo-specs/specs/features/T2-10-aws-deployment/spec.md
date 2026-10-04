# T2-10 · AWS Deployment

> **Status: draft (outline).** Detail this into full `spec.md`/`plan.md`/`tasks.md` (same format as Tier 1) before building. Claude Code: do not implement from this outline. Ask the human to promote it first.

## Goal
Host the same stack for remote demos.

## Scope
- Terraform: VPC (or default), one EC2 Graviton `m7g.2xlarge` (Ubuntu, Docker), 128 GB gp3, Elastic IP, security group (443 only), Route 53 record, IAM role (SSM, Secrets Manager read, Bedrock invoke)
- Caddy reverse proxy with TLS; auth proxy (oauth2-proxy with Entra ID or Google) replacing `X-Demo-User` via `AuthProvider` (persona switcher still available to admins in DEMO_MODE)
- Bedrock provider in ModelGateway; secrets from Secrets Manager; leak-scan + build + deploy via GitHub Actions (SSH/SSM)
- EventBridge Scheduler stop/start (weekday working hours) + AWS Budgets alert
- Data never leaves synthetic; no customer data on the instance

## Acceptance sketch
- `terraform apply` + deploy workflow yields HTTPS demo behind login; `make demo-reset` works remotely; instance auto-stops out of hours

## Open questions
- Confirm Brightbeam AWS account/billing owner; Bedrock model access approval in chosen region
