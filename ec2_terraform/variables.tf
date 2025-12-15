variable "region" {
  description = "AWS region for all resources."
  type        = string
  default     = "eu-central-1"
}

variable "vpc_id" {
  description = "VPC ID where the EC2 instance and security group reside."
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID for the EC2 instance (should be public)."
  type        = string
}

variable "ami_id" {
  description = "AMI ID for the EC2 instance."
  type        = string
  default     = "ami-004e960cde33f9146"
}

variable "instance_type" {
  description = "EC2 instance type."
  type        = string
  default     = "t3.micro"
}

variable "private_key_output_path" {
  description = "Where to write the generated private key (PEM)."
  type        = string
  default     = "./pf1-terraform-key.pem"
}

variable "bucket_name" {
  description = "Optional fixed S3 bucket name. Leave blank to generate."
  type        = string
  default     = ""
}

variable "bucket_prefix" {
  description = "Prefix for generated S3 bucket names."
  type        = string
  default     = "deploy-dag"
}

variable "project_prefix" {
  description = "Short prefix applied to resource names."
  type        = string
  default     = "pf1"
}

variable "instance_name" {
  description = "Name tag for the EC2 instance."
  type        = string
  default     = "pf1-ec2-instance"
}
