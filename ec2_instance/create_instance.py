#!/usr/bin/env python3
"""
Provision an EC2 instance in a given VPC/subnet.

Steps performed:
1. Create (or retrieve) an EC2 key pair and write the private key to disk.
2. Create a security group that allows SSH from anywhere (typical internet gateway traffic).
3. Launch a tiny EC2 instance (t3.micro by default) associated with the key pair and security group.

Example:
    python ec2_instance/create_instance.py \\
        --ami-id ami-0123456789abcdef0 \\
        --vpc-id vpc-0123456789abcdef0 \\
        --subnet-id subnet-0123456789abcdef0 \\
        --key-name pf1-ec2-key \\
        --security-group-name pf1-ec2-sg

AWS credentials and region must already be configured via environment variables,
credential files, or an instance profile.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from textwrap import dedent

import boto3
from botocore.exceptions import ClientError

DEFAULT_REGION = os.getenv("AWS_REGION", "eu-central-1")
DEFAULT_VPC_ID = os.getenv("VPC_ID", "")
DEFAULT_SUBNET_ID = os.getenv("SUBNET_ID", "")
DEFAULT_AMI_ID = "ami-004e960cde33f9146"  # ubuntu/images/hvm-ssd/ubuntu-focal-20.04-amd64-server-20230420 (eu-central-1) 


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create an EC2 instance with SSH access.")
    parser.add_argument("--region", default=DEFAULT_REGION, help="AWS region (default: %(default)s)")
    parser.add_argument("--ami-id", default=DEFAULT_AMI_ID, help="AMI ID for the EC2 instance.")
    parser.add_argument("--vpc-id", default=DEFAULT_VPC_ID, help="Target VPC ID.")
    parser.add_argument(
        "--subnet-id",
        default=DEFAULT_SUBNET_ID or None,
        help="Optional subnet ID; if omitted the script looks for the public subnet in the VPC.",
    )
    parser.add_argument("--key-name", default="pf1-ec2-key", help="Name for the EC2 key pair.")
    parser.add_argument("--key-path", default="pf1-ec2-key.pem", help="Where to write the private key.")
    parser.add_argument("--security-group-name", default="pf1-public-sg", help="Security group name.")
    parser.add_argument("--instance-type", default="t3.micro", help="Instance type (default tiny instance t3.micro).")
    parser.add_argument("--instance-name", default="pf1-ec2-instance", help="Tag Name for the instance.")
    parser.add_argument(
        "--test-s3-bucket",
        required=True,
        help="S3 bucket used by the on-instance test script.",
    )
    args = parser.parse_args()

    if not args.vpc_id:
        parser.error("--vpc-id is required (set VPC_ID env var or pass the flag).")
    return args


def create_key_pair(ec2_client, key_name: str, key_path: Path) -> None:
    """Create a new key pair and write the private key to disk."""
    try:
        response = ec2_client.create_key_pair(
            KeyName=key_name,
            KeyType="rsa",
            KeyFormat="pem",
            TagSpecifications=[
                {
                    "ResourceType": "key-pair",
                    "Tags": [{"Key": "Name", "Value": key_name}],
                }
            ],
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "InvalidKeyPair.Duplicate":
            print(f"Key pair '{key_name}' already exists. Using existing key pair.")
            return

    key_material = response["KeyMaterial"]
    key_path.write_text(key_material)
    key_path.chmod(0o600)
    print(f"Created key pair '{key_name}' and wrote private key to {key_path}")
    
    

def find_public_subnet(ec2_client, vpc_id: str) -> str:
    """
    Return the ID of the single subnet tagged Tier=public within the VPC.
    Raises ValueError if zero or multiple such subnets are found.
    """
    response = ec2_client.describe_subnets(
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": "tag:Tier", "Values": ["public"]},
        ]
    )
    subnets = response["Subnets"]
    if not subnets:
        raise ValueError("No subnet tagged Tier=public found in the VPC.")
    if len(subnets) > 1:
        raise ValueError(
            f"Expected a single public subnet but found {len(subnets)}. "
            "Pass --subnet-id explicitly to disambiguate."
        )
    subnet_id = subnets[0]["SubnetId"]
    print(f"Identified public subnet: {subnet_id}")
    return subnet_id


def get_security_group_id(ec2_client, group_name: str, vpc_id: str) -> str:
    """
    Look up the ID of the named security group within the VPC.
    Raises ValueError if not found.
    """
    response = ec2_client.describe_security_groups(
        Filters=[
            {"Name": "group-name", "Values": [group_name]},
            {"Name": "vpc-id", "Values": [vpc_id]},
        ]
    )
    groups = response["SecurityGroups"]
    if not groups:
        raise ValueError(f"Security group '{group_name}' not found in VPC {vpc_id}.")
    group_id = groups[0]["GroupId"]
    print(f"Using security group '{group_name}' ({group_id})")
    return group_id


def build_user_data(bucket_name: str) -> str:
    """Create user-data script that installs boto3 and writes the S3 test helper."""
    s3_test_script = f"""#!/usr/bin/env python3
import argparse
import uuid
from datetime import datetime
from pathlib import Path

import boto3

DEFAULT_BUCKET = "{bucket_name}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload and download a test file from S3.")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET, help="S3 bucket to use.")
    parser.add_argument("--key", default=None, help="Optional object key. Defaults to random.")
    args = parser.parse_args()

    bucket = args.bucket
    key = args.key or f"s3-test-{{uuid.uuid4().hex}}.txt"

    payload = f"Test data generated at {{datetime.utcnow().isoformat()}}"
    upload_path = Path("/tmp/s3_test_upload.txt")
    upload_path.write_text(payload)

    s3 = boto3.client("s3")
    s3.upload_file(str(upload_path), bucket, key)
    print(f"Uploaded {{key}} to {{bucket}} from {{upload_path}}")

    download_path = Path("/tmp/s3_test_download.txt")
    s3.download_file(bucket, key, str(download_path))
    print(f"Downloaded object to {{download_path}}")
    print("Downloaded contents:")
    print(download_path.read_text())


if __name__ == "__main__":
    main()
"""

    return dedent(
        f"""#!/bin/bash
        set -xeuo pipefail

        apt-get update -y
        apt-get install -y python3-boto3 python3-venv python3-pip

        cat <<'PYCODE' >/home/ubuntu/s3_bucket_test.py
{s3_test_script}
PYCODE
        chown ubuntu:ubuntu /home/ubuntu/s3_bucket_test.py
        chmod +x /home/ubuntu/s3_bucket_test.py
        """
    )

def launch_instance(
    ec2_resource,
    ami_id: str,
    subnet_id: str,
    group_id: str,
    key_name: str,
    instance_type: str,
    instance_name: str,
    user_data: str | None = None,
) -> str:
    """Launch a single EC2 instance and return its ID."""
    params = dict(
        ImageId=ami_id,
        InstanceType=instance_type,
        KeyName=key_name,
        MinCount=1,
        MaxCount=1,
        NetworkInterfaces=[
            {
                "SubnetId": subnet_id,
                "DeviceIndex": 0,
                "AssociatePublicIpAddress": True,
                "Groups": [group_id],
            }
        ],
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [{"Key": "Name", "Value": instance_name}],
            }
        ],
    )
    if user_data:
        params["UserData"] = user_data

    instances = ec2_resource.create_instances(**params)

    instance_id = instances[0].id
    print(f"Instance launch initiated. Instance ID: {instance_id}")
    return instance_id


def main() -> None:
    args = parse_args()
    key_path = Path(args.key_path)

    session = boto3.session.Session(region_name=args.region)
    ec2_client = session.client("ec2")
    ec2_resource = session.resource("ec2")

    create_key_pair(ec2_client, args.key_name, key_path)
    subnet_id = args.subnet_id or find_public_subnet(ec2_client, args.vpc_id)
    group_id = get_security_group_id(ec2_client, args.security_group_name, args.vpc_id)

    user_data = build_user_data(args.test_s3_bucket)

    instance_id = launch_instance(
        ec2_resource=ec2_resource,
        ami_id=args.ami_id,
        subnet_id=subnet_id,
        group_id=group_id,
        key_name=args.key_name,
        instance_type=args.instance_type,
        instance_name=args.instance_name,
        user_data=user_data,
    )

    print("EC2 instance provisioning submitted. Monitor progress in the AWS console or with describe-instances.")


if __name__ == "__main__":
    try:
        main()
    except ClientError as error:
        print(f"AWS error: {error}", file=sys.stderr)
        raise SystemExit(1)
