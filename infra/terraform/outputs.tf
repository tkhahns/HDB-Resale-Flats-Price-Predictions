output "artifacts_bucket" {
  description = "S3 bucket for model artifacts and reports"
  value       = aws_s3_bucket.artifacts.bucket
}

output "datalake_bucket" {
  description = "S3 bucket for raw/interim/processed data"
  value       = aws_s3_bucket.datalake.bucket
}

output "batch_ecr_url" {
  description = "ECR repository URL for the batch pipeline image"
  value       = aws_ecr_repository.batch.repository_url
}

output "api_ecr_url" {
  description = "ECR repository URL for the FastAPI image"
  value       = aws_ecr_repository.api.repository_url
}

output "api_alb_dns" {
  description = "DNS name of the API application load balancer"
  value       = aws_lb.api.dns_name
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "batch_task_definition" {
  description = "ARN of the latest batch task definition"
  value       = aws_ecs_task_definition.batch.arn
}

output "scheduler_role_arn" {
  description = "IAM role ARN for EventBridge Scheduler"
  value       = aws_iam_role.scheduler.arn
}
