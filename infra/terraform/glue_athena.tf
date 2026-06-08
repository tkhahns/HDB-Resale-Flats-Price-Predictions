resource "aws_glue_catalog_database" "hdb_avm" {
  name        = "hdb_avm"
  description = "HDB AVM pipeline outputs — reports partitioned by run date"
}

# ── Glue crawler: reports/date=* → Athena partitions ─────────────────────────
resource "aws_iam_role" "glue_crawler" {
  name = "${var.app_name}-glue-crawler"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "glue.amazonaws.com" }
    }]
  })
  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue_crawler.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

resource "aws_iam_role_policy" "glue_s3" {
  name = "s3-read"
  role = aws_iam_role.glue_crawler.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:ListBucket"]
      Resource = [
        aws_s3_bucket.artifacts.arn,
        "${aws_s3_bucket.artifacts.arn}/*",
      ]
    }]
  })
}

resource "aws_glue_crawler" "reports" {
  name          = "${var.app_name}-reports"
  role          = aws_iam_role.glue_crawler.arn
  database_name = aws_glue_catalog_database.hdb_avm.name
  tags          = local.common_tags

  s3_target {
    path = "s3://${var.artifacts_bucket_name}/reports/"
  }

  schema_change_policy {
    delete_behavior = "LOG"
    update_behavior = "UPDATE_IN_DATABASE"
  }

  # Run daily after the batch pipeline (~08:00 SGT)
  schedule = "cron(0 0 * * ? *)"
}
