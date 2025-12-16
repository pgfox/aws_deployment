#!/usr/bin/env python3
"""
Upload a sample CSV file to S3 and read it back.

Example:
    python S3_setup/client_upload_and_fetch.py --bucket-name my-demo-bucket-123
"""

from __future__ import annotations

import argparse
import io
import os
import sys
from datetime import datetime

import boto3
import pandas as pd
from botocore.exceptions import ClientError

DEFAULT_REGION = os.getenv("AWS_REGION", "eu-central-1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Upload and read a sample CSV file in S3.")
    parser.add_argument("--bucket-name", required=True, help="Target S3 bucket.")
    parser.add_argument("--object-key", default="sample-data.csv", help="Key for the CSV object.")
    parser.add_argument(
        "--dataframe-key",
        default="sample-dataframe.csv",
        help="Object key used when uploading the pandas dataframe.",
    )
    parser.add_argument("--region", default=DEFAULT_REGION, help="AWS region for the S3 client.")
    return parser.parse_args()


def build_sample_csv() -> bytes:
    rows = [
        ["id", "name", "timestamp"],
        ["1", "alpha", datetime.utcnow().isoformat()],
        ["2", "beta", datetime.utcnow().isoformat()],
    ]
    buffer = io.StringIO()
    for row in rows:
        buffer.write(",".join(row) + "\n")
    return buffer.getvalue().encode("utf-8")


def upload_csv(s3_client, bucket_name: str, object_key: str, data: bytes) -> None:
    s3_client.put_object(
        Bucket=bucket_name,
        Key=object_key,
        Body=data,
        ContentType="text/csv",
    )
    print(f"Uploaded {object_key} to bucket {bucket_name}.")


def download_csv(s3_client, bucket_name: str, object_key: str) -> str:
    response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
    body = response["Body"].read().decode("utf-8")
    print(f"Downloaded {object_key} from bucket {bucket_name}.")
    return body


def upload_df(s3_client, bucket_name: str, object_key: str) -> None:
    """Create a dummy pandas DataFrame and upload it as CSV to S3."""
    df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "category": ["alpha", "beta", "gamma"],
            "value": [10.5, 42.0, 100.1],
        }
    )
    # holds a unicode (python) string buffer
    buffer = io.StringIO()
    # write the DataFrame to the buffer 
    df.to_csv(buffer, index=False)

    # convert the buffer to a byte stream (utf-8) and upload to S3
    s3_client.put_object(
        Bucket=bucket_name,
        Key=object_key,
        Body=buffer.getvalue().encode("utf-8"),
        ContentType="text/csv",
    )
    print(f"Uploaded DataFrame to {bucket_name}/{object_key}.")


def download_df(s3_client, bucket_name: str, object_key: str) -> pd.DataFrame:
    """Download the DataFrame CSV from S3 and load into pandas."""
    response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
    body = response["Body"].read().decode("utf-8")
    df = pd.read_csv(io.StringIO(body))
    print(f"Downloaded DataFrame from {bucket_name}/{object_key}.")
    return df


def main() -> None:
    args = parse_args()
    session = boto3.session.Session(region_name=args.region)
    s3_client = session.client("s3")

    csv_bytes = build_sample_csv()

    try:
        upload_csv(s3_client, args.bucket_name, args.object_key, csv_bytes)
        contents = download_csv(s3_client, args.bucket_name, args.object_key)
        upload_df(s3_client, args.bucket_name, args.dataframe_key)
        df = download_df(s3_client, args.bucket_name, args.dataframe_key)
    except ClientError as exc:
        print(f"S3 operation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)

    print("CSV contents retrieved:")
    print(contents.strip())
    print("DataFrame downloaded from S3:")
    print(df)


if __name__ == "__main__":
    main()
