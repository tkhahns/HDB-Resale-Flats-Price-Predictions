# Runbook

## Manual pipeline run

```bash
# Trigger the batch task manually in ECS (uses the latest image)
aws ecs run-task \
  --cluster hdb-avm \
  --task-definition hdb-avm-batch \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=DISABLED}" \
  --overrides '{"containerOverrides":[{"name":"batch","command":["--all"]}]}'
```

## Model rollback

To roll back to a previously published model:

1. Find the target run date in S3:
   ```bash
   aws s3 ls s3://hdb-avm-artifacts/models/ --human-readable
   ```

2. Overwrite `latest.json` to point at the prior prefix:
   ```bash
   aws s3 cp - s3://hdb-avm-artifacts/models/latest.json <<EOF
   {
     "model_prefix": "models/date=2026-01-01",
     "run_date": "2026-01-01",
     "metrics": {"MAE": 27145}
   }
   EOF
   ```

3. Force a new API deployment to pick up the change:
   ```bash
   aws ecs update-service --cluster hdb-avm --service hdb-avm-api --force-new-deployment
   ```

## CloudWatch alarms

| Alarm | Trigger | Action |
|---|---|---|
| `hdb-avm-batch-task-failure` | Batch ECS task exits non-zero | Check `/ecs/hdb-avm/batch` log group |
| `hdb-avm-api-5xx-rate` | API 5xx > 5% over 5 min | Check `/ecs/hdb-avm/api` log group |
| `hdb-avm-api-unhealthy-targets` | All API targets unhealthy | Check model loading (`/readyz`) |
| `hdb-avm-no-new-model-36h` | `latest.json` not updated in 36 h | Manually trigger batch run |

## Enable daily schedule

After verifying the first manual run succeeds:

```bash
aws scheduler update-schedule \
  --name hdb-avm-batch-daily \
  --state ENABLED \
  --schedule-expression "cron(0 23 * * ? *)"
```

Or update in Terraform:
```hcl
# infra/terraform/eventbridge.tf
state = "ENABLED"
```

## QuickSight setup

1. In the AWS Console, go to QuickSight → Datasets → New dataset → Athena.
2. Select the `hdb_avm` database.
3. Create datasets for:
   - `model_metrics` (MAE/RMSE/R² trend over time)
   - `backtest_metrics` (walk-forward fold results)
   - `backtest_bias_flat_type`, `backtest_bias_town` (segment bias)
   - `feature_importance`
4. Enable SPICE auto-refresh (daily, after Glue crawler runs).

## Local development

```bash
# Install all deps
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run full synthetic pipeline
python -m src.avm.pipeline --all --synthetic --run-date $(date +%Y-%m-%d)

# Start API locally (after running the pipeline to create models/)
uvicorn src.avm.api.main:app --reload

# Check linting
ruff check src/ tests/
ruff format --check src/ tests/
```
