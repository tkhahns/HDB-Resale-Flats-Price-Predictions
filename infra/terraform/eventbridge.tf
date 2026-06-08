resource "aws_scheduler_schedule" "batch_daily" {
  name       = "${var.app_name}-batch-daily"
  group_name = "default"

  # Daily at 07:00 Asia/Singapore (cron in UTC: 23:00 previous day)
  schedule_expression          = var.schedule_expression
  schedule_expression_timezone = "Asia/Singapore"

  # Disabled by default — enable after verifying manual RunTask succeeds
  state = "DISABLED"

  flexible_time_window {
    mode                      = "FLEXIBLE"
    maximum_window_in_minutes = 15
  }

  target {
    arn      = aws_ecs_cluster.main.arn
    role_arn = aws_iam_role.scheduler.arn

    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.batch.arn
      launch_type         = "FARGATE"
      task_count          = 1

      network_configuration {
        assign_public_ip = false
        subnets          = var.private_subnet_ids
        security_groups  = [aws_security_group.api_tasks.id]
      }
    }

    retry_policy {
      maximum_retry_attempts       = 0
      maximum_event_age_in_seconds = 3600
    }
  }
}
