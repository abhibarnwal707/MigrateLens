## 1. Architecture inventory
- **Lambda**: High confidence. Defined as `AWS::Serverless::Function` for event processing and consumption (`template.yaml:101`, `template.yaml:133`).
- **SNS**: High confidence. Defined as `AWS::SNS::Topic` and subscriptions (`template.yaml:8`, `template.yaml:72`, `template.yaml:79`, `template.yaml:89`), and referenced in application code (`src/processor/eventprocessor.js:7`).
- **SQS**: High confidence. Defined as `AWS::SQS::Queue` queues and dead-letter queues (`template.yaml:15`, `template.yaml:22`, `template.yaml:29`, `template.yaml:36`, `template.yaml:40`, `template.yaml:44`), queue policies (`template.yaml:50`), and as a Lambda event source (`template.yaml:150`).
- **DynamoDB**: High confidence. Defined as `AWS::DynamoDB::Table` (`template.yaml:157`).

## 2. Mapping table
| AWS service | Google Cloud | trade-off | evidence |
|---|---|---|---|
| Lambda | Cloud Run functions | Cloud Run functions keep the function model; Cloud Run suits containerised handlers and longer requests. | `template.yaml:101`, `template.yaml:133` |
| SNS | Pub/Sub | A Pub/Sub topic with subscriptions replaces an SNS topic; push subscriptions cover HTTP fan-out. | `template.yaml:8`, `template.yaml:72` |
| SQS | Pub/Sub | Pub/Sub topic plus pull subscription replaces a queue; scales automatically but is a pub/sub model, not a queue. | `template.yaml:15`, `template.yaml:150` |
| DynamoDB | Firestore | Firestore suits document and key-value access with simple queries; Bigtable suits very high throughput wide-column workloads but needs more design. | `template.yaml:157` |

## 3. Target architecture
The target Google Cloud architecture uses **Cloud Run functions** for serverless event processing and consumption, replacing **Lambda**. Ingested device events flow through **Pub/Sub** topics and subscriptions replacing **SNS** and **SQS**, filtering metrics by message attributes. Finally, processed events are persisted in **Firestore** replacing **DynamoDB**.

## 4. Risks and unknowns
- **DynamoDB / Firestore**: Data model, secondary indexes, transactions and capacity model differ; access patterns must be re-validated before choosing the target.
- **Lambda / Cloud Run functions**: Event source wiring (triggers), handler signatures, runtime versions and timeout/concurrency limits differ.
- **SNS / Pub/Sub**: SMS, mobile push and email delivery protocols have no Pub/Sub equivalent; message filtering syntax differs.
- **SQS / Pub/Sub**: FIFO ordering, visibility timeout and delay semantics differ (ordering keys, ack deadlines); consumers must be idempotent.
- **Unmapped services**: The repository templates define AWS IoT (`template.yaml:124`), which has no direct equivalent in the mapping catalog. IoT Core ingestion must be redesigned using Google Cloud IoT alternatives or direct ingestion via Pub/Sub endpoints.

## 5. Rollout and rollback
1. Provision Google Cloud infrastructure using Terraform (Pub/Sub topics/subscriptions, Firestore database, and Cloud Run functions) alongside the live AWS environment (`template.yaml`).
2. Deploy code updates to publish telemetry concurrently to both the existing **SNS** topic and the new **Pub/Sub** topic.
3. Verify Cloud Run functions consumption and Firestore writes in Google Cloud staging environments while keeping AWS **Lambda** and **DynamoDB** fully operational.
4. Cut over downstream consumers and IoT event sources to Google Cloud **Pub/Sub** and **Cloud Run functions**.
5. Monitor error rates, latency, and dead-letter topics. If anomalies occur, revert DNS or traffic routing back to the live AWS services.
6. Decommission AWS resources only after verification in production.

## 6. IAM least-privilege notes
- **Cloud Run functions (IoTMetricsEventProcessorFunction)**: Run under a dedicated service account (`iot-processor-sa@project.iam.gserviceaccount.com`). Bind `roles/pubsub.publisher` restricted solely to the target **Pub/Sub** topic resource.
- **Cloud Run functions (AllFilteredEventConsumerFunction)**: Run under a dedicated service account (`event-consumer-sa@project.iam.gserviceaccount.com`). Bind `roles/pubsub.subscriber` on the inbound **Pub/Sub** subscription and `roles/datastore.user` scoped specifically to the **Firestore** database instance.

## 7. Generated artifacts
- terraform/main.tf
- Dockerfile
- .github/workflows/ci.yml