# S3 Setup Tools

This directory contains helper scripts for basic Amazon S3 workflows:

- `create_bucket.py`: creates an S3 bucket in the region you specify.
- `client_upload_and_fetch.py`: uploads a sample CSV object to a bucket, then downloads it back to verify access.

## create_bucket.py

Parameters:

- `--bucket-name`: globally unique bucket name (required).
- `--region`: AWS region (default: `eu-central-1`). Buckets in `us-east-1` omit the `CreateBucketConfiguration`.

Usage:

```bash
source .venv/bin/activate
python S3_setup/create_bucket.py --bucket-name my-demo-bucket-123 --region eu-central-1
```

## client_upload_and_fetch.py

Parameters:

- `--bucket-name`: Target bucket (required).
- `--object-key`: Object key/name (default: `sample-data.csv`).
- `--region`: AWS region for the client (default: `eu-central-1`).

Steps performed:

1. Builds an in-memory CSV with sample rows.
2. Uploads it to the bucket using `put_object`.
3. Retrieves it with `get_object` and prints the content.

Usage:

```bash
source .venv/bin/activate
python S3_setup/client_upload_and_fetch.py \
  --bucket-name my-demo-bucket-123 \
  --object-key sample-data.csv
```

Ensure your AWS credentials allow S3 access before running these scripts.
