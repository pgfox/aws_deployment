terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.5"
    }
  }
}

provider "aws" {
  region = var.region
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

locals {
  bucket_name = var.bucket_name != "" ? var.bucket_name : "${var.bucket_prefix}-${random_id.bucket_suffix.hex}"
}

resource "aws_s3_bucket" "test" {
  bucket        = local.bucket_name
  force_destroy = true

  tags = {
    Name        = "${var.project_prefix}-s3-bucket"
    Provisioned = "terraform"
  }
}

resource "aws_iam_role" "ec2_s3" {
  name = "${var.project_prefix}-ec2-s3-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.project_prefix}-ec2-s3-role"
    Provisioned = "terraform"
  }
}

resource "aws_iam_role_policy" "ec2_s3_policy" {
  name = "${var.project_prefix}-ec2-s3-access"
  role = aws_iam_role.ec2_s3.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.test.arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "${aws_s3_bucket.test.arn}/*"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "ec2_s3" {
  name = "${var.project_prefix}-ec2-s3-profile"
  role = aws_iam_role.ec2_s3.name
}

resource "aws_security_group" "public" {
  name        = "${var.project_prefix}-public-sg"
  description = "Allow SSH to public instances"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_prefix}-public-sg"
    Provisioned = "terraform"
  }
}

resource "tls_private_key" "main" {
  algorithm = "RSA"
  rsa_bits  = 4096
}

resource "local_sensitive_file" "ssh_private_key" {
  filename             = var.private_key_output_path
  file_permission      = "0600"
  directory_permission = "0700"
  content              = tls_private_key.main.private_key_pem
}

resource "aws_key_pair" "main" {
  key_name   = "${var.project_prefix}-ec2-key"
  public_key = tls_private_key.main.public_key_openssh
}

locals {
  user_data = templatefile("${path.module}/user_data.sh", {
    bucket_name = aws_s3_bucket.test.bucket
  })
}

resource "aws_instance" "test" {
  ami                         = var.ami_id
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_id
  key_name                    = aws_key_pair.main.key_name
  vpc_security_group_ids      = [aws_security_group.public.id]
  associate_public_ip_address = true
  iam_instance_profile        = aws_iam_instance_profile.ec2_s3.name
  user_data                   = local.user_data

  tags = {
    Name        = var.instance_name
    Provisioned = "terraform"
  }
}
