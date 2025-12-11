#!/usr/bin/env python3
"""
Provision an EC2-hosted Apache Airflow instance that syncs DAGs from an S3 bucket.

The script performs:
1. Ensures an S3 bucket (default: deploy-dag-<random>) exists and uploads a sample DAG.
2. Creates/reuses an EC2 key pair.
3. Creates a security group opening SSH (22) and Airflow UI (8080).
4. Provisions the IAM role + instance profile granting the EC2 host S3 access.
5. Launches an EC2 instance whose user data installs Airflow and syncs DAGs from the bucket.

Example:
    python Airflow_setup/deploy_ec2_airflow.py \
        --vpc-id vpc-0123456789abcdef0 \
        --subnet-id subnet-0123456789abcdef0
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from textwrap import dedent
import uuid
import json

import boto3
from botocore.exceptions import ClientError

DEFAULT_REGION = os.getenv("AWS_REGION", "eu-central-1")
DEFAULT_AMI_ID = "ami-004e960cde33f9146"  # Ubuntu 20.04 in eu-central-1
DEFAULT_BUCKET_NAME_PREFIX = "deploy-dag"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deploy an EC2 Airflow host that syncs DAGs from S3."
    )
    parser.add_argument("--region", default=DEFAULT_REGION, help="AWS region")
    parser.add_argument(
        "--bucket-name",
        help="S3 bucket for DAGs. Default is deploy-dag-<random>.",
    )
    parser.add_argument("--vpc-id", required=True, help="VPC ID where the instance will run")
    parser.add_argument("--subnet-id", required=True, help="Subnet ID for the EC2 instance")
    parser.add_argument("--instance-type", default="t3.medium", help="EC2 instance type")
    parser.add_argument("--ami-id", default=DEFAULT_AMI_ID, help="AMI ID")
    parser.add_argument("--key-name", default="pf1-airflow-key", help="Key pair name")
    parser.add_argument("--key-path", default="pf1-airflow-key.pem", help="Where to save the PEM")
    parser.add_argument(
        "--security-group-name",
        default="pf1-airflow-sg",
        help="Security group name for SSH and Airflow UI",
    )
    parser.add_argument(
        "--iam-role-name",
        default="pf1-airflow-ec2-role",
        help="IAM role name to create/use for the EC2 instance profile.",
    )
    parser.add_argument("--instance-name", default="pf1-airflow-ec2", help="Name tag for the instance")
    return parser.parse_args()

def generate_bucket_name() -> str:
    suffix = uuid.uuid4().hex[:8]
    return f"{DEFAULT_BUCKET_NAME_PREFIX}-{suffix}"

def ensure_bucket(s3_client, bucket_name: str, region: str) -> None:
    """Create the bucket if it does not exist."""
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"S3 bucket '{bucket_name}' already exists.")
        return
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        if error_code not in ("404", "NoSuchBucket"):
            raise

    params = {"Bucket": bucket_name}
    if region != "us-east-1":
        params["CreateBucketConfiguration"] = {"LocationConstraint": region}

    s3_client.create_bucket(**params)
    print(f"Created S3 bucket '{bucket_name}'.")


def upload_sample_dag(s3_client, bucket_name: str) -> None:
    """Upload a simple DAG to the bucket for testing."""
    dag_content = dedent(
        """\
        from airflow import DAG
        from airflow.operators.empty import EmptyOperator
        from datetime import datetime

        with DAG(
            dag_id="sample_s3_dag",
            start_date=datetime(2024, 1, 1),
            schedule_interval=None,
            catchup=False,
        ) as dag:
            EmptyOperator(task_id="hello_airflow")
        """
    )
    s3_client.put_object(
        Bucket=bucket_name,
        Key="dags/sample_s3_dag.py",
        Body=dag_content.encode("utf-8"),
        ContentType="text/x-python",
    )
    print("Uploaded sample DAG to S3.")


def create_key_pair(ec2_client, key_name: str, key_path: Path) -> None:
    try:
        response = ec2_client.create_key_pair(
            KeyName=key_name,
            KeyType="rsa",
            KeyFormat="pem",
            TagSpecifications=[
                {"ResourceType": "key-pair", "Tags": [{"Key": "Name", "Value": key_name}]}
            ],
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "InvalidKeyPair.Duplicate":
            print(f"Key pair '{key_name}' already exists; reusing.")
            if not key_path.exists():
                print(f"WARNING: {key_path} missing locally.", file=sys.stderr)
            return
        raise

    key_path.write_text(response["KeyMaterial"])
    key_path.chmod(0o600)
    print(f"Wrote key pair to {key_path}")


def ensure_security_group(ec2_client, group_name: str, vpc_id: str) -> str:
    try:
        response = ec2_client.create_security_group(
            GroupName=group_name,
            Description="Airflow EC2 access",
            VpcId=vpc_id,
            TagSpecifications=[
                {"ResourceType": "security-group", "Tags": [{"Key": "Name", "Value": group_name}]}
            ],
        )
        group_id = response["GroupId"]
        ec2_client.authorize_security_group_ingress(
            GroupId=group_id,
            IpPermissions=[
                {
                    "IpProtocol": "tcp",
                    "FromPort": 22,
                    "ToPort": 22,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "SSH"}],
                },
                {
                    "IpProtocol": "tcp",
                    "FromPort": 8080,
                    "ToPort": 8080,
                    "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "Airflow UI"}],
                },
            ],
        )
        print(f"Created security group '{group_name}' ({group_id}).")
        return group_id
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "InvalidGroup.Duplicate":
            groups = ec2_client.describe_security_groups(
                Filters=[
                    {"Name": "group-name", "Values": [group_name]},
                    {"Name": "vpc-id", "Values": [vpc_id]},
                ]
            )
            group_id = groups["SecurityGroups"][0]["GroupId"]
            print(f"Security group '{group_name}' already exists ({group_id}); reusing.")
            return group_id
        raise


def ensure_iam_role_and_profile(iam_client, role_name: str, bucket_name: str) -> str:
    """Create or reuse an IAM role and instance profile granting S3 read access."""
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
            Description="Access S3 DAG bucket for Airflow EC2 host",
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
                "Action": ["s3:GetObject"],
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
    profile_name = f"{role_name}-profile"

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
        if exc.response["Error"]["Code"] != "EntityAlreadyExists":
            raise

    return profile_name


def build_user_data(bucket_name: str) -> str:
    return dedent(
        f"""\
        #!/bin/bash
        set -xeuo pipefail

        apt-get update -y
        apt-get install -y python3 python3-venv python3-pip awscli

        useradd -m airflow || true
        install -d -o airflow -g airflow /opt/airflow
        sudo -u airflow python3 -m venv /opt/airflow/venv
        sudo -u airflow /opt/airflow/venv/bin/pip install --upgrade pip
        sudo -u airflow /opt/airflow/venv/bin/pip install 'apache-airflow==2.8.1'

        cat <<'EOF' >/opt/airflow/sync_dags.sh
        #!/bin/bash
        export AIRFLOW_HOME=/opt/airflow
        aws s3 sync s3://{bucket_name}/dags $AIRFLOW_HOME/dags
        EOF
        chown airflow:airflow /opt/airflow/sync_dags.sh
        chmod +x /opt/airflow/sync_dags.sh

        cat <<'EOF' >/etc/systemd/system/airflow-web.service
        [Unit]
        Description=Airflow standalone service syncing DAGs from S3
        After=network.target

        [Service]
        User=airflow
        Group=airflow
        Environment="AIRFLOW_HOME=/opt/airflow"
        ExecStart=/bin/bash -c "/opt/airflow/sync_dags.sh && source /opt/airflow/venv/bin/activate && airflow standalone"
        Restart=on-failure

        [Install]
        WantedBy=multi-user.target
        EOF

        systemctl daemon-reload
        systemctl enable --now airflow-web.service
        """
    )


def launch_instance(
    ec2_resource,
    ami_id: str,
    instance_type: str,
    subnet_id: str,
    sg_id: str,
    key_name: str,
    instance_name: str,
    iam_instance_profile_name: str,
    user_data: str,
) -> str:
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
            {"ResourceType": "instance", "Tags": [{"Key": "Name", "Value": instance_name}]}
        ],
        IamInstanceProfile={"Name": iam_instance_profile_name},
        UserData=user_data,
    )
    instance_id = instances[0].id
    print(f"Airflow EC2 instance launch requested: {instance_id}")
    return instance_id


def main() -> None:
    args = parse_args()
    session = boto3.session.Session(region_name=args.region)
    s3_client = session.client("s3")
    ec2_client = session.client("ec2")
    ec2_resource = session.resource("ec2")
    iam_client = session.client("iam")

    bucket_name = args.bucket_name or generate_bucket_name()

    ensure_bucket(s3_client, bucket_name, args.region)
    upload_sample_dag(s3_client, bucket_name)
    create_key_pair(ec2_client, args.key_name, Path(args.key_path))
    sg_id = ensure_security_group(ec2_client, args.security_group_name, args.vpc_id)
    instance_profile_name = ensure_iam_role_and_profile(
        iam_client, args.iam_role_name, bucket_name
    )
    user_data = build_user_data(bucket_name)

    launch_instance(
        ec2_resource=ec2_resource,
        ami_id=args.ami_id,
        instance_type=args.instance_type,
        subnet_id=args.subnet_id,
        sg_id=sg_id,
        key_name=args.key_name,
        instance_name=args.instance_name,
        iam_instance_profile_name=instance_profile_name,
        user_data=user_data,
    )

    print("Airflow EC2 deployment submitted. Monitor AWS console for status.")


if __name__ == "__main__":
    try:
        main()
    except ClientError as error:
        print(f"AWS error: {error}", file=sys.stderr)
        raise SystemExit(1)
