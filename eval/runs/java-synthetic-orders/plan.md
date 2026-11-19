## 1. Architecture inventory
- **DynamoDB**: Medium confidence. Used for NoSQL data storage. Evidence: `src/main/java/example/OrderService.java:5` (`import software.amazon.awssdk.services.dynamodb.DynamoDbClient;`), `src/main/java/example/OrderService.java:6` (`import software.amazon.awssdk.services.dynamodb.model.AttributeValue;`), `src/main/java/example/OrderService.java:7` (`import software.amazon.awssdk.services.dynamodb.model.PutItemRequest;`).
- **S3**: Medium confidence. Used for object storage. Evidence: `src/main/java/example/OrderService.java:8` (`import software.amazon.awssdk.services.s3.S3Client;`), `src/main/java/example/OrderService.java:9` (`import software.amazon.awssdk.services.s3.model.PutObjectRequest;`), `src/main/java/example/OrderService.java:17` (`private final String bucket = System.getenv("S3_BUCKET");`).
- **SQS**: Medium confidence. Used for message queuing. Evidence: `src/main/java/example/OrderService.java:10` (`import software.amazon.awssdk.services.sqs.SqsClient;`), `src/main/java/example/OrderService.java:11` (`import software.amazon.awssdk.services.sqs.model.SendMessageRequest;`), `src/main/java/example/OrderService.java:18` (`private final String queueUrl = System.getenv("SQS_QUEUE_URL");`).

## 2. Mapping table
| AWS service | Google Cloud | trade-off | evidence |
|---|---|---|---|
| DynamoDB | Firestore, Bigtable | Firestore suits document and key-value access with simple queries; Bigtable suits very high throughput wide-column workloads but needs more design. | `src/main/java/example/OrderService.java:5` |
| S3 | Cloud Storage | Near drop-in object store; storage classes and lifecycle rules map, but the API and IAM model differ. | `src/main/java/example/OrderService.java:8` |
| SQS | Pub/Sub | Pub/Sub topic plus pull subscription replaces a queue; scales automatically but is a pub/sub model, not a queue. | `src/main/java/example/OrderService.java:10` |

## 3. Target architecture
The application workload container runs on Cloud Run, leveraging Cloud Storage for object storage, Firestore for NoSQL document data, and Pub/Sub for asynchronous messaging. The Java application code is refactored from the AWS SDK to the Google Cloud client libraries. Incoming HTTP requests invoke the container service, which stores order payloads in Cloud Storage, persists order records in Firestore, and publishes order identifiers to Pub/Sub.

## 4. Risks and unknowns
- **DynamoDB**: Data model, secondary indexes, transactions and capacity model differ; access patterns must be re-validated before choosing the target. DynamoDB has no direct equivalent in Google Cloud (map_service direct: false).
- **S3**: Code using the S3 API needs the Cloud Storage client or the XML interoperability API; presigned URLs become signed URLs; bucket policies must be rewritten as IAM.
- **SQS**: FIFO ordering, visibility timeout and delay semantics differ (ordering keys, ack deadlines); consumers must be idempotent.

## 5. Rollout and rollback
1. Provision Google Cloud resources (Cloud Storage bucket, Firestore database, Pub/Sub topic and subscription) using Terraform.
2. Build and push the container image referencing Google Cloud client libraries to Artifact Registry.
3. Deploy the application to Cloud Run alongside the live AWS environment, using feature flags or internal traffic splitting for dark launching.
4. Run end-to-end integration tests against the Cloud Run staging deployment while keeping AWS live and fully operational.
5. Cut over DNS/traffic to Cloud Run gradually while monitoring error rates and latency.
6. **Rollback procedure**: If critical issues occur, immediately revert DNS/traffic weights back to the live AWS deployment.

## 6. IAM least-privilege notes
- Create a dedicated Google Cloud service account for the Cloud Run service (e.g., `order-service-sa@project-id.iam.gserviceaccount.com`).
- Grant `roles/storage.objectAdmin` restricted specifically to the target Cloud Storage bucket resource.
- Grant `roles/datastore.user` restricted to the target Firestore database.
- Grant `roles/pubsub.publisher` restricted to the target Pub/Sub topic.

## 7. Generated artifacts
- `terraform/main.tf`
- `Dockerfile`
- `.github/workflows/ci.yml`