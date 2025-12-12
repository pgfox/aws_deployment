#!/usr/bin/env python3
"""
Create an IAM role/instance profile permitting EC2 instances to read/write a specific S3 bucket,
then attach that profile to the named EC2 instance.

Example:
    python ec2_instance/assign_s3_role.py \
        --instance-id i-0123456789abcdef0 \
        --bucket-name my-demo-bucket-123
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import boto3
from botocore.exceptions import ClientError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assign an S3 access role to an EC2 instance.")
    parser.add_argument("--instance-id", required=True, help="Target EC2 instance ID.")
    parser.add_argument("--bucket-name", required=True, help="S3 bucket name for access.")
    parser.add_argument(
        "--role-name",
        default="pf1-ec2-s3-role",
        help="IAM role name to create/use (default: pf1-ec2-s3-role).",
    )
    parser.add_argument(
        "--profile-name",
        default="pf1-ec2-s3-profile",
        help="IAM instance profile name to create/use.",
    )
    parser.add_argument(
        "--region",
        default=None,
        help="AWS region (optional, defaults to boto3 configuration).",
    )
    return parser.parse_args()


def ensure_role_and_profile(
    iam_client,
    role_name: str,
    profile_name: str,
    bucket_name: str,
) -> str:
    assume_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "ec2.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    try:
        iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(assume_policy),
            Description="EC2 S3 access role",
            Tags=[{"Key": "Name", "Value": role_name}],
        )
        print(f"Created IAM role '{role_name}'.")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "EntityAlreadyExists":
            raise
        print(f"IAM role '{role_name}' already exists; reusing.")

    policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:ListBucket"],
                "Resource": f"arn:aws:s3:::{bucket_name}",
            },
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
                "Resource": f"arn:aws:s3:::{bucket_name}/*",
            },
        ],
    }
    policy_name = f"{role_name}-s3-access"
    iam_client.put_role_policy(
        RoleName=role_name,
        PolicyName=policy_name,
        PolicyDocument=json.dumps(policy_document),
    )

    try:
        iam_client.create_instance_profile(
            InstanceProfileName=profile_name,
            Tags=[{"Key": "Name", "Value": profile_name}],
        )
        print(f"Created instance profile '{profile_name}'.")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "EntityAlreadyExists":
            raise
        print(f"Instance profile '{profile_name}' already exists; reusing.")

    try:
        iam_client.add_role_to_instance_profile(
            InstanceProfileName=profile_name,
            RoleName=role_name,
        )
        print(f"Attached role '{role_name}' to profile '{profile_name}'.")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "LimitExceeded":
            raise
        print(f"Instance profile '{profile_name}' already has a role; using existing attachment.")

    return profile_name


def wait_for_instance_profile(iam_client, profile_name: str, attempts: int = 2, delay: int = 30) -> str:
    """Wait for the instance profile to become available and return its ARN."""
    for attempt in range(attempts):
        try:
            profile = iam_client.get_instance_profile(InstanceProfileName=profile_name)["InstanceProfile"]
            return profile["Arn"]
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "NoSuchEntity":
                raise
            if attempt == attempts - 1:
                raise RuntimeError(
                    f"Instance profile '{profile_name}' not available after {attempts} checks."
                )
            print(f"Instance profile '{profile_name}' not yet available; waiting {delay} seconds...")
            time.sleep(delay)
    raise RuntimeError(f"Instance profile '{profile_name}' not available.")


def attach_profile_to_instance(ec2_client, instance_id: str, profile_arn: str) -> None:
    ec2_client.associate_iam_instance_profile(
        IamInstanceProfile={"Arn": profile_arn},
        InstanceId=instance_id,
    )
    print(f"Associated instance profile with EC2 instance {instance_id}.")


def main() -> None:
    args = parse_args()
    session = boto3.session.Session(region_name=args.region)
    iam_client = session.client("iam")
    ec2_client = session.client("ec2")

    try:
        profile_name = ensure_role_and_profile(
            iam_client=iam_client,
            role_name=args.role_name,
            profile_name=args.profile_name,
            bucket_name=args.bucket_name,
        )
        profile_arn = wait_for_instance_profile(iam_client, profile_name)
        attach_profile_to_instance(ec2_client, args.instance_id, profile_arn)
    except (ClientError, RuntimeError) as exc:
        print(f"AWS error: {exc}", file=sys.stderr)
        raise SystemExit(1)

    print("S3 access role assigned successfully.")


if __name__ == "__main__":
    main()
