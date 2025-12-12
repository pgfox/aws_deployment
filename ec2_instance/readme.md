# EC2 Instance Helper

`create_instance.py` provisions a t3.micro instance for connectivity testing. It:

- Creates (or reuses) a key pair and writes the `.pem` locally.
- Finds the VPC’s public subnet by the `Tier=public` tag.
- Locates the `pf1-public-sg` security group and attaches it.
- Launches the instance with a public IP so you can verify routing, SSH, and outbound access.
- Installs `/home/ubuntu/s3_bucket_test.py`, a helper script that exercises S3 by uploading and downloading a test file.

## Example: Create Instance (VPC ID only)

```bash
source .venv/bin/activate
python ec2_instance/create_instance.py \
  --vpc-id vpc-0123456789abcdef0
```

The script uses default values for the AMI (`ami-004e960cde33f9146` in eu-central-1), key name, and security group unless overridden.

## S3 Bucket Test Script on the Instance

Every instance launched with `create_instance.py` now includes `/home/ubuntu/s3_bucket_test.py`. It uploads a small text file to the bucket you passed via `--test-s3-bucket`, downloads it back, and prints the contents so you can confirm IAM/S3 wiring. Use it like:

```bash
ssh -i pf1-ec2-key.pem ubuntu@<public-ip-address>
./s3_bucket_test.py --bucket my-demo-bucket
```

If you omit `--bucket`, it defaults to the bucket specified during provisioning. You can also provide `--key my-test-object.txt` to control the object key.

## IAM Role, Policy, and Instance Profile (assign_s3_role.py)

AWS uses IAM roles to define permissions, and instance profiles to attach those roles to EC2 instances. The `assign_s3_role.py` utility automates:

- Creating an IAM role (`pf1-ec2-s3-role` by default) with permissions to list, read, write, and delete objects in a specified bucket.
- Creating (or reusing) an instance profile (`pf1-ec2-s3-profile`) that wraps the role.
- Associating the profile with an EC2 instance so its applications can access the bucket without embedding credentials.

Run it after the instance is up:

```bash
source .venv/bin/activate
python ec2_instance/assign_s3_role.py \
  --instance-id i-0123456789abcdef0 \
  --bucket-name my-demo-bucket \
  --region eu-central-1
```

Behind the scenes the script handles IAM propagation delays before calling `associate-iam-instance-profile`. Without this role/profile binding, the on-instance S3 test script will fail because EC2 instances don't have permissions by default.

## How IAM Components Grant S3 Access to EC2

1. **IAM Role**: Defines *what* the EC2 instance is allowed to do. Our inline policy permits `s3:ListBucket`, `s3:GetObject`, `s3:PutObject`, and `s3:DeleteObject` on the target bucket. The assume-role policy lets the EC2 service assume this role.
2. **Instance Profile**: Acts as the “bridge” between EC2 and the IAM role. EC2 can only attach roles via an instance profile, so `assign_s3_role.py` creates one and adds the role to it.
3. **EC2 Association**: Once the profile is associated with the instance, AWS automatically injects temporary credentials for that role into the instance metadata service (IMDS). Applications like our `s3_bucket_test.py` fetch these credentials through the AWS SDK (boto3) transparently.
4. **S3 Bucket**: Remains unchanged, but IAM policies reference the bucket ARN to scope allowed actions. If you change buckets, rerun `assign_s3_role.py` to update the policy.

This chain ensures the EC2 instance never needs static AWS keys; instead, AWS rotates short-lived credentials bound by the IAM role permissions, keeping the S3 interaction secure and auditable.

## Example: SSH Into the Instance

```bash
ssh -i pf1-ec2-key.pem ubuntu@<public-ip-address>
```

Replace `<public-ip-address>` with the value shown in the AWS console or from `aws ec2 describe-instances`. Ensure the PEM file has `chmod 600` permissions before connecting.
