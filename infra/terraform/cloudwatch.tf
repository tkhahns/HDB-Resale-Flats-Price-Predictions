resource "aws_sns_topic" "alarms" {
  name = "${var.app_name}-alarms"
  tags = local.common_tags
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ── Alarm: batch ECS task failure ────────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "batch_failure" {
  alarm_name          = "${var.app_name}-batch-task-failure"
  alarm_description   = "Batch pipeline ECS task stopped with a non-zero exit code"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  threshold           = 1
  metric_name         = "FailedTaskCount"
  namespace           = "ECS/ContainerInsights"
  period              = 300
  statistic           = "Sum"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = aws_ecs_cluster.main.name
    ServiceName = "${var.app_name}-batch"
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  tags          = local.common_tags
}

# ── Alarm: API 5xx rate ───────────────────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  alarm_name          = "${var.app_name}-api-5xx-rate"
  alarm_description   = "API 5xx error rate exceeds 5% over 5 minutes"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  threshold           = 5
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = aws_lb.api.arn_suffix
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  tags          = local.common_tags
}

# ── Alarm: unhealthy API targets ──────────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "api_unhealthy" {
  alarm_name          = "${var.app_name}-api-unhealthy-targets"
  alarm_description   = "All API targets unhealthy"
  comparison_operator = "LessThanOrEqualToThreshold"
  evaluation_periods  = 2
  threshold           = 0
  metric_name         = "HealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Average"

  dimensions = {
    LoadBalancer = aws_lb.api.arn_suffix
    TargetGroup  = aws_lb_target_group.api.arn_suffix
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  tags          = local.common_tags
}

# ── Alarm: no new model in 36 hours ──────────────────────────────────────────
resource "aws_cloudwatch_metric_alarm" "no_new_model" {
  alarm_name          = "${var.app_name}-no-new-model-36h"
  alarm_description   = "latest.json has not been updated in over 36 hours — batch may have failed silently"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  threshold           = 1
  metric_name         = "NumberOfObjectsUpdated"
  namespace           = "AWS/S3"
  period              = 129600  # 36 hours
  statistic           = "Sum"
  treat_missing_data  = "breaching"

  dimensions = {
    BucketName  = var.artifacts_bucket_name
    FilterId    = "LatestJson"
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  tags          = local.common_tags
}
