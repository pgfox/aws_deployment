output "bucket_name" {
  description = "Name of the S3 bucket storing test data."
  value       = aws_s3_bucket.test.bucket
}

output "instance_id" {
  description = "ID of the created EC2 instance."
  value       = aws_instance.test.id
}

output "instance_public_ip" {
  description = "Public IP address of the EC2 instance."
  value       = aws_instance.test.public_ip
}
