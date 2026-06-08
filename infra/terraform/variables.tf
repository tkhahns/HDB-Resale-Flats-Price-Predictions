variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-southeast-1"
}

variable "environment" {
  description = "Deployment environment (dev / prod)"
  type        = string
  default     = "prod"
}

variable "app_name" {
  description = "Application name prefix for all resources"
  type        = string
  default     = "hdb-avm"
}

variable "artifacts_bucket_name" {
  description = "S3 bucket for model artifacts and reports"
  type        = string
  default     = "hdb-avm-artifacts"
}

variable "datalake_bucket_name" {
  description = "S3 bucket for raw / interim / processed data"
  type        = string
  default     = "hdb-avm-datalake"
}

variable "batch_cpu" {
  description = "Fargate batch task vCPU units (1024 = 1 vCPU)"
  type        = number
  default     = 2048
}

variable "batch_memory" {
  description = "Fargate batch task memory (MiB)"
  type        = number
  default     = 8192
}

variable "api_cpu" {
  description = "Fargate API task vCPU units"
  type        = number
  default     = 512
}

variable "api_memory" {
  description = "Fargate API task memory (MiB)"
  type        = number
  default     = 1024
}

variable "api_desired_count" {
  description = "Number of API service tasks"
  type        = number
  default     = 2
}

variable "schedule_expression" {
  description = "EventBridge cron expression for the daily batch run (UTC)"
  type        = string
  # 07:00 SGT = 23:00 UTC (previous day)
  default = "cron(0 23 * * ? *)"
}

variable "alert_email" {
  description = "SNS email address for CloudWatch alarms"
  type        = string
  default     = ""
}

variable "vpc_id" {
  description = "VPC ID for ECS tasks and ALB"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for ECS tasks"
  type        = list(string)
}

variable "public_subnet_ids" {
  description = "Public subnet IDs for the ALB"
  type        = list(string)
}

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS on the ALB (leave empty to use HTTP)"
  type        = string
  default     = ""
}
