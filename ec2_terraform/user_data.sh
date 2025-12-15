#!/bin/bash
set -xeuo pipefail

apt-get update -y
apt-get install -y python3-boto3 python3-venv python3-pip

cat <<'PYCODE' >/home/ubuntu/s3_bucket_test.py
#!/usr/bin/env python3
import argparse
import uuid
from datetime import datetime
from pathlib import Path

import boto3

DEFAULT_BUCKET = "${bucket_name}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload and download a test file from S3.")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET, help="S3 bucket to use.")
    parser.add_argument("--key", default=None, help="Optional object key. Defaults to random.")
    args = parser.parse_args()

    bucket = args.bucket
    key = args.key or f"s3-test-{uuid.uuid4().hex}.txt"

    payload = f"Test data generated at {datetime.utcnow().isoformat()}"
    upload_path = Path("/tmp/s3_test_upload.txt")
    upload_path.write_text(payload)

    s3 = boto3.client("s3")
    s3.upload_file(str(upload_path), bucket, key)
    print(f"Uploaded {key} to {bucket} from {upload_path}")

    download_path = Path("/tmp/s3_test_download.txt")
    s3.download_file(bucket, key, str(download_path))
    print(f"Downloaded object to {download_path}")
    print("Downloaded contents:")
    print(download_path.read_text())


if __name__ == "__main__":
    main()
PYCODE

chown ubuntu:ubuntu /home/ubuntu/s3_bucket_test.py
chmod +x /home/ubuntu/s3_bucket_test.py
