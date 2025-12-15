# EC2 Terraform Deployment

This module recreates the resources previously provisioned via Python scripts:

- S3 bucket for test uploads/downloads (auto-generated name unless provided).
- IAM role + inline policy, instance profile, and key pair for EC2.
- Security group allowing SSH from the internet.
- EC2 instance with user data installing `/home/ubuntu/s3_bucket_test.py`.

## Prerequisites

- Terraform >= 1.5
- AWS credentials with permission to manage EC2, IAM, and S3 resources.
- Existing VPC + subnet (public) to host the instance.
- SSH public key file to register as an AWS key pair.

## Configuration

Update or supply the following variables (via `terraform.tfvars`, CLI `-var`, or environment):

| Variable | Description |
| --- | --- |
| `region` | AWS region (default `eu-central-1`). |
| `vpc_id` | VPC ID where resources reside. |
| `subnet_id` | Public subnet ID for the EC2 instance. |
| `private_key_output_path` | File path where Terraform writes the generated private key (default `./pf1-terraform-key.pem`). |
| `bucket_name` | Optional S3 bucket name; leave blank to auto-generate `deploy-dag-<rand>`. |
| `instance_type`, `ami_id`, `instance_name`, `project_prefix` | Customize as needed. |

Example `terraform.tfvars`:

```hcl
region       = "eu-central-1"
vpc_id       = "vpc-0123456789abcdef0"
subnet_id    = "subnet-0123456789abcdef0"
private_key_output_path = "./pf1-terraform-key.pem"
```

## Usage

```bash
cd ec2_terraform
terraform init
terraform plan
terraform apply
```

Outputs include the bucket name, EC2 instance ID, and public IP. After the instance is running:

```bash
ssh -i pf1-terraform-key.pem ubuntu@<public-ip>
./s3_bucket_test.py --bucket <bucket-from-output>
```

## Cleanup

Destroy all Terraform-managed resources:

```bash
terraform destroy
```
