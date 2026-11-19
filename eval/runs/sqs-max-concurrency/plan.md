## 1. Architecture inventory
- **Lambda**: Serverless functions (`MaxConcurrencyFunction`, `ReservedConcurrencyFunction`) with concurrency and event source configurations (`template.yaml:40`, `template.yaml:54`, confidence: high).
- **SQS**: Message queues and dead-letter queues (`ReservedConcurrencyDeadLetterQueue`, `ReservedConcurrencyQueue`, `MaxConcurrencyDeadLetterQueue`, `MaxConcurrencyQueue`) acting as event sources (`template.yaml:16`, `template.yaml:19`, `template.yaml:28`, `template.yaml:31`, confidence: high).
- **CloudWatch**: Dashboard definition (`CloudWatchDashboard`) monitoring metrics and execution concurrency (`template.yaml:67`, confidence: high).

## 2. Mapping table
| AWS service | Google Cloud | trade-off | evidence |
|---|---|---|---|
| Lambda | Cloud Run functions, Cloud Run | Cloud Run functions keep the function model; Cloud Run suits containerised handlers and longer requests. | `template.yaml:40`, `template.yaml:54` |
| SQS | Pub/Sub | Pub/Sub topic plus pull subscription replaces a queue; scales automatically but is a pub/sub model, not a queue. | `template.yaml:16`, `template.yaml:19`, `template.yaml:28`, `template.yaml:31` |
| CloudWatch | Cloud Logging, Cloud Monitoring | Logs go to Cloud Logging and metrics/alerts to Cloud Monitoring; Cloud Run ships stdout logs automatically. | `template.yaml:67` |

## 3. Target architecture
The serverless application runs on Cloud Run functions triggered by Pub/Sub subscriptions (replacing SQS queues and dead-letter queues). Operational visibility and custom metrics are monitored via Cloud Monitoring and Cloud Logging.

## 4. Risks and unknowns
- **Lambda migration risk**: Event source wiring (triggers), handler signatures, runtime versions and timeout/concurrency limits differ.
- **SQS migration risk**: FIFO ordering, visibility timeout and delay semantics differ (ordering keys, ack deadlines); consumers must be idempotent.
- **CloudWatch migration risk**: CloudWatch Logs Insights queries, metric filters and dashboards must be rebuilt; custom metric names differ.

## 5. Rollout and rollback
1. Provision Google Cloud infrastructure using Terraform (Pub/Sub topics/subscriptions, Cloud Run functions, and Cloud Monitoring dashboards) while keeping AWS live.
2. Deploy dual-publishing or mirror incoming traffic/events to both SQS and Pub/Sub to validate Cloud Run functions processing.
3. Verify Cloud Run functions metrics, logs, and dead-letter handling in Cloud Monitoring and Cloud Logging.
4. Cut over event producers to point exclusively to Pub/Sub.
5. Monitor error rates, latency, and concurrency on Cloud Run functions.
6. Rollback plan: If issues occur before final decommissioning, retain AWS SQS and Lambda live and immediately redirect producer traffic back to SQS.
7. Decommission AWS SQS queues, Lambda functions, and CloudWatch dashboards once stabilization is confirmed.

## 6. IAM least-privilege notes
- Create a dedicated service account for each Cloud Run function (e.g., `sa-max-concurrency-func@project.iam.gserviceaccount.com` and `sa-reserved-concurrency-func@project.iam.gserviceaccount.com`).
- Grant per-resource role bindings: assign `roles/pubsub.subscriber` to the respective function service account on the specific Pub/Sub subscription resource only.
- Grant `roles/run.invoker` only to authorized event sources or callers, and `roles/logging.logWriter` for application logging.

## 7. Generated artifacts
- terraform/main.tf
- Dockerfile
- .github/workflows/ci.yml