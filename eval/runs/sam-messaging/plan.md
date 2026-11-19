## 1. Architecture inventory
- **Lambda**: High confidence. Used for serverless function handlers across multiple components (`1-sqs/template.yaml:10`, `1-sqs/template.yaml:27`, `2-sns/template.yaml:16`, `2-sns/template.yaml:23`, `2-sns/template.yaml:30`, `2-sns/template.yaml:47`, `2-sns/template.yaml:56`, `3-eventbridge/template.yaml:7`, `3-eventbridge/template.yaml:21`, `3-eventbridge/template.yaml:44`, `6-eventbridge-sqs/template.yaml:10`).
- **SQS**: High confidence. Used for message queues and queue policies (`1-sqs/code/publisher.js:9`, `1-sqs/template.yaml:7`, `1-sqs/template.yaml:40`, `4-sns-sqs/template-basic.yaml:7`, `4-sns-sqs/template-basic.yaml:22`, `4-sns-sqs/template-filter-policy.yaml:7`, `4-sns-sqs/template-filter-policy.yaml:27`, `6-eventbridge-sqs/template.yaml:7`, `6-eventbridge-sqs/template.yaml:23`, `6-eventbridge-sqs/template.yaml:43`).
- **SNS**: High confidence. Used for pub/sub messaging topics and subscriptions (`2-sns/code/publisher.js:9`, `2-sns/template.yaml:7`, `4-sns-sqs/template-basic.yaml:10`, `4-sns-sqs/template-filter-policy.yaml:10`, `4-sns-sqs/template-filter-policy.yaml:14`, `5-eventbridge-sns/template.yaml:7`, `5-eventbridge-sns/template.yaml:24`).
- **EventBridge**: High confidence. Used for event buses, rules, and event routing (`3-eventbridge/code/publisher.js:20`, `3-eventbridge/template.yaml:29`, `5-eventbridge-sns/template.yaml:10`, `6-eventbridge-sqs/template.yaml:29`).

## 2. Mapping table
| AWS service | Google Cloud | trade-off | evidence |
| :--- | :--- | :--- | :--- |
| **Lambda** | Cloud Run functions, Cloud Run | Cloud Run functions keep the function model; Cloud Run suits containerised handlers and longer requests. | `1-sqs/template.yaml:10`, `1-sqs/template.yaml:27`, `2-sns/template.yaml:16`, `2-sns/template.yaml:23`, `2-sns/template.yaml:30`, `2-sns/template.yaml:47`, `2-sns/template.yaml:56`, `3-eventbridge/template.yaml:7`, `3-eventbridge/template.yaml:21`, `3-eventbridge/template.yaml:44`, `6-eventbridge-sqs/template.yaml:10` |
| **SQS** | Pub/Sub | Pub/Sub topic plus pull subscription replaces a queue; scales automatically but is a pub/sub model, not a queue. | `1-sqs/code/publisher.js:9`, `1-sqs/template.yaml:7`, `1-sqs/template.yaml:40`, `4-sns-sqs/template-basic.yaml:7`, `4-sns-sqs/template-basic.yaml:22`, `4-sns-sqs/template-filter-policy.yaml:7`, `4-sns-sqs/template-filter-policy.yaml:27`, `6-eventbridge-sqs/template.yaml:7`, `6-eventbridge-sqs/template.yaml:23`, `6-eventbridge-sqs/template.yaml:43` |
| **SNS** | Pub/Sub | A Pub/Sub topic with subscriptions replaces an SNS topic; push subscriptions cover HTTP fan-out. | `2-sns/code/publisher.js:9`, `2-sns/template.yaml:7`, `4-sns-sqs/template-basic.yaml:10`, `4-sns-sqs/template-filter-policy.yaml:10`, `4-sns-sqs/template-filter-policy.yaml:14`, `5-eventbridge-sns/template.yaml:7`, `5-eventbridge-sns/template.yaml:24` |
| **EventBridge** | Cloud Scheduler, Pub/Sub | Cloud Scheduler covers cron-style rules; event buses and pattern routing are approximated with Pub/Sub topics. | `3-eventbridge/code/publisher.js:20`, `3-eventbridge/template.yaml:29`, `5-eventbridge-sns/template.yaml:10`, `6-eventbridge-sqs/template.yaml:29` |

## 3. Target architecture
The target Google Cloud architecture replaces AWS serverless messaging and compute constructs with native managed services. 
Event publishing applications and event consumers run on Cloud Run functions (or containerised on Cloud Run) for stateless compute. 
Messaging and fan-out patterns previously handled by SQS and SNS are unified around Google Cloud Pub/Sub topics with push and pull subscriptions. 
Scheduled and event-driven routing previously implemented via EventBridge rules are handled via Cloud Scheduler for cron schedules and Pub/Sub message filtering for event pattern matching.

## 4. Risks and unknowns
- **EventBridge**: EventBridge has no direct equivalent; event pattern matching, event buses, and custom schema registries have no direct equivalent, requiring custom Pub/Sub message filtering logic and topic topologies.
- **SQS**: FIFO ordering, visibility timeout, and delay semantics differ (ordering keys, ack deadlines); consumers must be idempotent.
- **SNS**: SMS, mobile push, and email delivery protocols have no Pub/Sub equivalent; message filtering syntax differs.
- **Lambda**: Event source wiring (triggers), handler signatures, runtime versions, and timeout/concurrency limits differ.

## 5. Rollout and rollback
1. Provision Google Cloud infrastructure (Pub/Sub topics/subscriptions, Cloud Run functions) via Terraform.
2. Deploy dual-publishing in producer applications or mirror incoming events from AWS to Google Cloud Pub/Sub.
3. Deploy and test consumers on Cloud Run functions reading from Pub/Sub in a staging environment.
4. Perform canary cutover of read/write traffic to Google Cloud for a subset of components.
5. Promote Google Cloud to primary production and monitor error rates and latency.
6. **Rollback**: If anomalies occur, revert DNS/traffic routing or application producer configuration back to the live AWS infrastructure while keeping AWS live until cutover is fully verified.
7. Decommission AWS resources after verification period.

## 6. IAM least-privilege notes
- Create a dedicated Google Cloud service account for each Cloud Run function workload (e.g., `sa-sqs-consumer@project.iam.gserviceaccount.com`).
- Apply per-resource role bindings, granting `roles/pubsub.subscriber` strictly on the target Pub/Sub subscription and `roles/pubsub.publisher` on publishing topics.
- Ensure no shared service accounts are used across functions.

## 7. Generated artifacts
- terraform/main.tf
- Dockerfile
- .github/workflows/ci.yml