## 1. Architecture inventory
- **S3**: `email_processing_stack/email_processing_stack.py:5`, `email_processing_stack/email_processing_stack.py:8`, `email_processing_stack/lambda_functions/email_processor/handler.py:13`, `email_processing_stack/lambda_functions/queue_consumer/handler.py:7`, `demo_priority_yielding.py:13` (Confidence: high)
- **SQS**: `email_processing_stack/email_processing_stack.py:7`, `email_processing_stack/lambda_functions/email_processor/handler.py:14`, `email_processing_stack/lambda_functions/queue_consumer/handler.py:9` (Confidence: high)
- **Lambda**: `email_processing_stack/email_processing_stack.py:6`, `email_processing_stack/email_processing_stack.py:9` (Confidence: medium)
- **IAM**: `email_processing_stack/email_processing_stack.py:11` (Confidence: medium)
- **CloudWatch**: `email_processing_stack/email_processing_stack.py:10` (Confidence: medium)
- **SES**: `email_processing_stack/lambda_functions/queue_consumer/handler.py:8` (Confidence: high)

## 2. Mapping table
| AWS service | Google Cloud | trade-off | evidence |
| :--- | :--- | :--- | :--- |
| S3 | Cloud Storage | Near drop-in object store; storage classes and lifecycle rules map, but the API and IAM model differ. | `email_processing_stack/email_processing_stack.py:32` |
| SQS | Pub/Sub | Pub/Sub topic plus pull subscription replaces a queue; scales automatically but is a pub/sub model, not a queue. | `email_processing_stack/email_processing_stack.py:97` |
| Lambda | Cloud Run functions, Cloud Run | Cloud Run functions keep the function model; Cloud Run suits containerised handlers and longer requests. | `email_processing_stack/email_processing_stack.py:190` |
| IAM | Service Accounts, Cloud IAM | IAM roles become service accounts with narrowly scoped predefined roles bound to specific resources. | `email_processing_stack/email_processing_stack.py:153` |
| CloudWatch | Cloud Logging, Cloud Monitoring | Logs go to Cloud Logging and metrics/alerts to Cloud Monitoring; Cloud Run ships stdout logs automatically. | `email_processing_stack/email_processing_stack.py:145` |
| SES | [No direct equivalent] | No first-party Google Cloud email-sending service; use a third-party provider or SMTP relay. | `email_processing_stack/lambda_functions/queue_consumer/handler.py:8` |

## 3. Target architecture
Incoming emails are stored in a Cloud Storage bucket configured with Object finalize notifications. When an email object is created, a Cloud Run function (Email Processor) is triggered to parse the metadata and publish messages to Pub/Sub topics representing general and priority channels. A second Cloud Run function (Queue Consumer) pulls messages from Pub/Sub subscriptions, processes the payloads, and dispatches outbound messages via an external SMTP or third-party email delivery provider (since SES has no direct equivalent). Operational logs are shipped automatically to Cloud Logging, and resource access is secured using Google Cloud Service Accounts and Cloud IAM.

## 4. Risks and unknowns
- **SES (Unmapped service)**: SES has no direct equivalent in Google Cloud. Deliverability reputation, domain validation, bounce handling, and API integration must be completely rebuilt using a third-party transactional email service.
- **S3 Notifications to Pub/Sub**: S3 object-created notifications must be adapted to Cloud Storage notification events published to Pub/Sub topics.
- **SQS to Pub/Sub Semantics**: SQS queues and DLQs map to Pub/Sub topics, subscriptions, and dead-letter topics. FIFO ordering, visibility timeouts, and message retention semantics differ and require careful configuration and idempotent consumers.
- **IAM Policy Translation**: Custom IAM role statements and resource policies must be converted to Cloud IAM bindings and bucket/topic IAM policies.

## 5. Rollout and rollback
1. **Provision Infrastructure**: Deploy Terraform configurations for Cloud Storage buckets, Pub/Sub topics and subscriptions, Cloud Run functions, and Cloud IAM service accounts. Keep AWS live and operational.
2. **Configure External Email Provider**: Set up domain verification and credentials with the third-party email provider replacing SES.
3. **Run Dual-Write / Shadow Testing**: Configure event routing or dual uploads so test emails flow through both AWS (live) and Google Cloud (staging) without affecting production recipients.
4. **Verify Observability**: Check Cloud Logging to ensure Cloud Run functions are executing successfully and capturing traces and metrics.
5. **Cutover DNS and Traffic**: Update DNS records or webhook sources to point email ingestion directly to the Google Cloud Storage bucket.
6. **Monitor and Decommission**: Observe error rates and processing latency in Google Cloud. Once stability is confirmed over a soaking period, decommission the AWS resources.
7. **Rollback Procedure**: If critical failures occur during cutover, revert DNS and ingestion traffic pointers back to the AWS S3 bucket and re-enable AWS Lambda consumers while keeping Google Cloud traffic paused.

## 6. IAM least-privilege notes
- **Email Processor Service Account**: Bound to Cloud Storage with `roles/storage.objectViewer` specifically on the email bucket, and to Pub/Sub with `roles/pubsub.publisher` on the target topics.
- **Queue Consumer Service Account**: Bound to Pub/Sub with `roles/pubsub.subscriber` on the general and priority subscriptions, and to Cloud Storage with `roles/storage.objectViewer` on the email bucket.
- **CI/CD Service Account**: Granted `roles/run.developer`, `roles/storage.admin`, and `roles/pubsub.admin` restricted strictly to the deployment project and target resource scopes.

## 7. Generated artifacts
- terraform/main.tf
- Dockerfile
- .github/workflows/ci.yml