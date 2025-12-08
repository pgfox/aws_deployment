#!/usr/bin/env python3
"""
Create an Amazon S3 bucket using boto3.

Example:
    python S3_setup/create_bucket.py --bucket-name my-demo-bucket-123 --region eu-central-1
"""

from __future__ import annotations

import argparse
import os
import sys

import boto3
from botocore.exceptions import ClientError

DEFAULT_REGION = os.getenv("AWS_REGION", "eu-central-1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create an S3 bucket.")
    parser.add_argument("--bucket-name", required=True, help="Globally unique S3 bucket name.")
    parser.add_argument("--region", default=DEFAULT_REGION, help="AWS region for the bucket.")
    return parser.parse_args()


def create_bucket(bucket_name: str, region: str) -> None:
    session = boto3.session.Session(region_name=region)
    s3_client = session.client("s3")

    params = {"Bucket": bucket_name}
    if region != "us-east-1":
        params["CreateBucketConfiguration"] = {"LocationConstraint": region}

    try:
        s3_client.create_bucket(**params)
    except ClientError as exc:
        print(f"Error creating bucket: {exc}", file=sys.stderr)
        raise SystemExit(1)

    print(f"S3 bucket '{bucket_name}' created in region {region}.")


def main() -> None:
    args = parse_args()
    create_bucket(args.bucket_name, args.region)


if __name__ == "__main__":
    main()
