#!/usr/bin/env python3
"""
Simple client to query the REST test_data endpoint.

Usage:
    python REST_SRV_setup/client/query_test_data.py --server-ip 203.0.113.10 --data-id 1
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query the REST test_data service.")
    parser.add_argument("--server_ip", required=True, help="Public IP or hostname of the REST server.")
    parser.add_argument("--data_id", default="1", help="Value for the data_id query parameter (default: 1).")
    return parser.parse_args()


def fetch_test_data(server_ip: str, data_id: str) -> Any:
    url = f"http://{server_ip}/test_data"
    response = requests.get(url, params={"data_id": data_id}, timeout=10)
    response.raise_for_status()
    return response.json()


def main() -> None:
    args = parse_args()
    try:
        payload = fetch_test_data(args.server_ip, args.data_id)
    except requests.HTTPError as exc:
        print(f"Request failed with status {exc.response.status_code}: {exc.response.text}", file=sys.stderr)
        raise SystemExit(1)
    except requests.RequestException as exc:
        print(f"Request error: {exc}", file=sys.stderr)
        raise SystemExit(1)

    print(payload)


if __name__ == "__main__":
    main()
