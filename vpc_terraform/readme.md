# VPC Terraform Module

This Terraform configuration reproduces the resources previously created by `vpc_setup/create_vpc.py`:

- VPC with DNS support and configurable name.
- Internet Gateway and public route table + default route.
- Public subnet (tags `Name`, `Tier=public`, auto-assign public IPs).
- Private subnet (tags `Name`, `Tier=private`).
- Security group allowing SSH/HTTP/HTTPS for resources in the public subnet.

## Usage

1. Ensure Terraform >= 1.5 and AWS credentials are configured.
2. Provide at least the VPC name via variables. Example `terraform.tfvars`:

```hcl
region        = "eu-central-1"
vpc_name      = "pf1-vpc"
project_prefix = "pf1"
```

You can also override CIDR blocks or prefixes if desired.

3. Deploy:

```bash
cd vpc_terraform
terraform init
terraform plan
terraform apply -var "vpc_name=pf1-vpc"
```

Outputs report the VPC ID, subnet IDs, and security group ID for downstream stacks.

## Cleanup

```bash
terraform destroy
```
