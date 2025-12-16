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

## Character Set, Code Point, and Encoding Primer

- **Character set**: The repertoire of symbols available. Unicode is a modern character set encompassing letters, digits, emoji, etc. Older sets include ASCII (128 characters).
- **Code point**: The numeric ID assigned to each character within the character set. Example: Unicode assigns U+0041 to the letter “A” and U+1F600 to 😀.
- **Encoding**: The rule for turning code points into raw bytes. UTF-8, UTF-16, and UTF-32 are encodings of Unicode; ASCII effectively serves as both a character set and encoding because each 7-bit value maps directly to a character.

### Example

Suppose the string is `Hello 😀`:

1. The characters belong to the Unicode character set.
2. Each character has a code point—H is U+0048, e is U+0065, etc., and 😀 is U+1F600.
3. Using UTF-8 encoding:
   - Each ASCII letter (U+0048, U+0065, etc.) maps to a single byte because UTF-8 preserves ASCII directly.
   - 😀 (U+1F600) becomes four bytes: `F0 9F 98 80`.
4. When the string is uploaded to S3, we encode it (e.g., `utf-8`) into bytes, send it over the network, and later decode using the same encoding to reconstruct the original characters.

Knowing this helps ensure you read and write text data consistently when dealing with S3 objects.
