# EC2 Instance Helper

`create_instance.py` provisions a t3.micro instance for connectivity testing. It:

- Creates (or reuses) a key pair and writes the `.pem` locally.
- Finds the VPC’s public subnet by the `Tier=public` tag.
- Locates the `pf1-public-sg` security group and attaches it.
- Launches the instance with a public IP so you can verify routing, SSH, and outbound access.

## Example: Create Instance (VPC ID only)

```bash
source .venv/bin/activate
python ec2_instance/create_instance.py \
  --vpc-id vpc-0123456789abcdef0
```

The script uses default values for the AMI (`ami-004e960cde33f9146` in eu-central-1), key name, and security group unless overridden.

## Example: SSH Into the Instance

```bash
ssh -i pf1-ec2-key.pem ubuntu@<public-ip-address>
```

Replace `<public-ip-address>` with the value shown in the AWS console or from `aws ec2 describe-instances`. Ensure the PEM file has `chmod 600` permissions before connecting.
