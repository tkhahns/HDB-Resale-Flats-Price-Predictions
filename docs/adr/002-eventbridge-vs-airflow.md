# ADR-002: EventBridge Scheduler + Fargate vs Airflow

**Status:** Accepted

**Context:** The pipeline runs once daily and is a single linear sequence of stages.

**Decision:** Use AWS EventBridge Scheduler to trigger an ECS Fargate one-shot task.

**Alternatives considered:**

- **Apache Airflow (MWAA)** — powerful DAG engine but costs ~$400/month for the smallest
  managed environment even at zero utilization.  Overkill for a single daily job.
- **AWS Step Functions** — good fit for multi-step workflows, but adds Lambda + state machine
  complexity for what is just a Python script with sequential function calls.

**Consequences:** No idle compute cost (Fargate bills only for task runtime).  The pipeline
must be idempotent (re-running with the same `--run-date` overwrites existing artifacts).
