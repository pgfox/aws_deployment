#!/usr/bin/env python3
"""
Provision an EC2 host that exposes a simple Flask "Hello World" endpoint
via Gunicorn + Nginx. The instance is launched in the VPC's public subnet
(identified by tag Tier=public) so it can be used to verify connectivity.

Example:
    python REST_SRV_setup/create_REST.py --vpc-id vpc-0123456789abcdef0
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
DEFAULT_AMI_ID = "ami-004e960cde33f9146"  # Ubuntu 20.04 LTS in eu-central-1
SERVER_APP_PATH = Path(__file__).parent / "server" / "app.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a REST test instance with Flask/Gunicorn/Nginx."
    )
    parser.add_argument("--region", default=DEFAULT_REGION, help="AWS region")
    parser.add_argument("--vpc-id", default=DEFAULT_VPC_ID, help="Target VPC ID")
    parser.add_argument("--ami-id", default=DEFAULT_AMI_ID, help="AMI to use")
    parser.add_argument("--instance-type", default="t3.micro", help="EC2 instance type")
    parser.add_argument("--key-name", default="pf1-rest-key", help="EC2 key pair name")
    parser.add_argument("--key-path", default="pf1-rest-key.pem", help="Where to write the PEM")
    parser.add_argument(
        "--security-group-name",
        default="pf1-rest-sg",
        help="Security group allowing SSH + HTTP",
    )
    parser.add_argument("--instance-name", default="pf1-rest-instance", help="Name tag")
    args = parser.parse_args()

    if not args.vpc_id:
        parser.error("--vpc-id is required (set VPC_ID env var or pass the flag).")

    return args


def load_app_source() -> str:
    """Read the Flask app source code from the repository."""
    if not SERVER_APP_PATH.exists():
        raise FileNotFoundError(f"Server app file not found at {SERVER_APP_PATH}")
    content = SERVER_APP_PATH.read_text().rstrip()
    return content + "\n"


def create_key_pair(ec2_client, key_name: str, key_path: Path) -> None:
    """Create (or reuse) a key pair and persist the private key."""
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
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "InvalidKeyPair.Duplicate":
            print(f"Key pair '{key_name}' already exists; reusing.")
            if not key_path.exists():
                print(
                    f"WARNING: {key_path} missing. Ensure you have the original private key.",
                    file=sys.stderr,
                )
            return
        raise

    key_path.write_text(response["KeyMaterial"])
    key_path.chmod(0o600)
    print(f"Created key pair '{key_name}' and wrote PEM to {key_path}")


def find_public_subnet(ec2_client, vpc_id: str) -> str:
    """Return the subnet ID tagged Tier=public (expects exactly one)."""
    response = ec2_client.describe_subnets(
        Filters=[
            {"Name": "vpc-id", "Values": [vpc_id]},
            {"Name": "tag:Tier", "Values": ["public"]},
        ]
    )
    subnets = response["Subnets"]
    if not subnets:
        raise ValueError("No subnet tagged Tier=public found.")
    if len(subnets) > 1:
        raise ValueError(
            f"Expected single public subnet but found {len(subnets)}. "
            "Tag only one with Tier=public or specify a subnet explicitly."
        )
    subnet_id = subnets[0]["SubnetId"]
    print(f"Using public subnet: {subnet_id}")
    return subnet_id


def ensure_security_group(ec2_client, group_name: str, vpc_id: str) -> str:
    """Create or fetch a SG allowing SSH and HTTP from anywhere."""
    try:
        response = ec2_client.create_security_group(
            GroupName=group_name,
            Description="HTTP + SSH access for REST test host",
            VpcId=vpc_id,
            TagSpecifications=[
                {
                    "ResourceType": "security-group",
                    "Tags": [{"Key": "Name", "Value": group_name}],
                }
            ],
        )
        sg_id = response["GroupId"]
        ec2_client.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "SSH"}],
                },
                {
                    "IpProtocol": "tcp",
                    "FromPort": 80,
                    "ToPort": 80,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "HTTP"}],
                },
            ],
        )
        print(f"Created security group '{group_name}' ({sg_id})")
        return sg_id
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "InvalidGroup.Duplicate":
            groups = ec2_client.describe_security_groups(
                Filters=[
                    {"Name": "group-name", "Values": [group_name]},
                    {"Name": "vpc-id", "Values": [vpc_id]},
                ]
            )
            sg_id = groups["SecurityGroups"][0]["GroupId"]
            print(f"Security group '{group_name}' already exists ({sg_id}); reusing.")
            return sg_id
        raise


def build_user_data(app_source: str) -> str:
    """Return cloud-init script to install Flask/Gunicorn/Nginx."""
    script = dedent(
        """\
        #!/bin/bash
        set -xeuo pipefail

        apt-get update -y
        apt-get install -y python3 python3-venv python3-pip nginx

        install -d -o ubuntu -g ubuntu /opt/rest_app
        cat <<'EOF' >/opt/rest_app/app.py
        APP_SOURCE_PLACEHOLDER
        EOF
        chown ubuntu:ubuntu /opt/rest_app/app.py

        sudo -u ubuntu python3 -m venv /opt/rest_app/venv
        sudo -u ubuntu /opt/rest_app/venv/bin/pip install --upgrade pip
        sudo -u ubuntu /opt/rest_app/venv/bin/pip install flask gunicorn

        cat <<'EOF' >/etc/systemd/system/restapp.service
        [Unit]
        Description=Gunicorn instance to serve Flask REST app
        After=network.target

        [Service]
        User=ubuntu
        Group=www-data
        WorkingDirectory=/opt/rest_app
        Environment="PATH=/opt/rest_app/venv/bin"
        ExecStart=/opt/rest_app/venv/bin/gunicorn --bind unix:/opt/rest_app/restapp.sock app:app

        [Install]
        WantedBy=multi-user.target
        EOF

        systemctl daemon-reload
        systemctl enable --now restapp.service

        cat <<'EOF' >/etc/nginx/sites-available/restapp
        server {
            listen 80;
            server_name _;

            location / {
                proxy_pass http://unix:/opt/rest_app/restapp.sock;
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto $scheme;
            }
        }
        EOF

        ln -sf /etc/nginx/sites-available/restapp /etc/nginx/sites-enabled/restapp
        rm -f /etc/nginx/sites-enabled/default
        systemctl restart nginx
        """
    )
    return script.replace("APP_SOURCE_PLACEHOLDER", app_source)


def launch_instance(
    ec2_resource,
    ami_id: str,
    instance_type: str,
    subnet_id: str,
    sg_id: str,
    key_name: str,
    instance_name: str,
    user_data: str,
) -> str:
    """Launch EC2 instance with provided configuration."""
    instances = ec2_resource.create_instances(
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
                "Groups": [sg_id],
            }
        ],
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [{"Key": "Name", "Value": instance_name}],
            }
        ],
        UserData=user_data,
    )

    instance_id = instances[0].id
    print(f"REST instance launch requested: {instance_id}")
    return instance_id


def main() -> None:
    args = parse_args()
    key_path = Path(args.key_path)

    session = boto3.session.Session(region_name=args.region)
    ec2_client = session.client("ec2")
    ec2_resource = session.resource("ec2")

    create_key_pair(ec2_client, args.key_name, key_path)
    subnet_id = find_public_subnet(ec2_client, args.vpc_id)
    sg_id = ensure_security_group(ec2_client, args.security_group_name, args.vpc_id)
    app_source = load_app_source()
    user_data = build_user_data(app_source)

    launch_instance(
        ec2_resource=ec2_resource,
        ami_id=args.ami_id,
        instance_type=args.instance_type,
        subnet_id=subnet_id,
        sg_id=sg_id,
        key_name=args.key_name,
        instance_name=args.instance_name,
        user_data=user_data,
    )

    print("REST service EC2 provisioning submitted. Check AWS console for status.")


if __name__ == "__main__":
    try:
        main()
    except (ClientError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
