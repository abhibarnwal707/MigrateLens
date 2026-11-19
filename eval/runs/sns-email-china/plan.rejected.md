## 1. Architecture inventory
- **CloudWatch**: Used for logs, metric filters, and alarms. (Confidence: high)
  - `templates/central.yaml:447` (`Type: AWS::Logs::LogGroup`)
  - `templates/central.yaml:494` (`Type: AWS::Logs::MetricFilter`)
  - `templates/central.yaml:500` (`Type: AWS::Logs::MetricFilter`)
  - `templates/central.yaml:506` (`Type: AWS::Logs::MetricFilter`)
  - `templates/central.yaml:512` (`Type: AWS::CloudWatch::Alarm`)
  - `templates/central.yaml:525` (`Type: AWS::CloudWatch::Alarm`)
  - `templates/central.yaml:538` (`Type: AWS::CloudWatch::Alarm`)
  - `templates/central.yaml:551` (`Type: AWS::CloudWatch::Alarm`)
  - `templates/central.yaml:565` (`Type: AWS::CloudWatch::Alarm`)
  - `templates/central.yaml:579` (`Type: AWS::CloudWatch::Alarm`)
  - `templates/central.yaml:593` (`Type: AWS::CloudWatch::Alarm`)
  - `templates/central.yaml:608` (`Type: AWS::CloudWatch::Alarm`)
- **DynamoDB**: Used for routing configuration, migration state, and delivery records. (Confidence: high)
  - `scripts/cleanup.py:82` (`ddb, s3 = central.client("dynamodb"), central.client("s3")`)
  - `src/mailer/handler.py:68` (`_ddb = boto3.client("dynamodb", config=AWS)`)
  - `templates/central.yaml:227` (`Type: AWS::DynamoDB::Table`)
  - `templates/central.yaml:241` (`Type: AWS::DynamoDB::Table`)
  - `templates/central.yaml:254` (`Type: AWS::DynamoDB::Table`)
  - `tools/mailcfg.py:298` (`client = boto3.Session(profile_name=a.profile, region_name=a.region).client("dynamodb")`)
  - `tools/migrate.py:92` (`ddb = session.client("dynamodb")`)
  - `tools/migrate.py:182` (`ddb = session.client("dynamodb")`)
  - `tools/migrate.py:242` (`ddb = session.client("dynamodb")`)
  - `tools/migrate.py:332` (`ddb = session.client("dynamodb")`)
  - `tools/migrate.py:386` (`ddb = session.client("dynamodb")`)
  - `tools/migrate.py:432` (`for i in items(session.client("dynamodb"), a.table):`)
- **IAM**: Used for execution and service roles. (Confidence: high)
  - `templates/central.yaml:394` (`Type: AWS::IAM::Role`)
  - `templates/member.yaml:79` (`Type: AWS::IAM::Role`)
  - `templates/member.yaml:102` (`Type: AWS::IAM::Role`)
  - `templates/test-smtp.yaml:90` (`Type: AWS::IAM::Role`)
  - `templates/test-smtp.yaml:130` (`Type: AWS::IAM::InstanceProfile`)
- **KMS**: Used for customer-managed encryption keys. (Confidence: high)
  - `templates/central.yaml:65` (`Type: AWS::KMS::Key`)
  - `templates/central.yaml:107` (`Type: AWS::KMS::Alias`)
- **Lambda**: Used for the mailer function and event source mapping. (Confidence: high)
  - `templates/central.yaml:297` (`Type: AWS::Lambda::EventSourceMapping`)
  - `templates/central.yaml:339` (`Type: AWS::Lambda::EventSourceMapping`)
  - `templates/central.yaml:382` (`Type: AWS::Lambda::EventSourceMapping`)
  - `templates/central.yaml:458` (`Type: AWS::Lambda::Function`)
- **S3**: Used for code artifacts and deployment storage. (Confidence: high)
  - `scripts/deploy.py:55` (`s3 = session.client("s3")`)
- **SNS**: Used for notification topics and subscriptions. (Confidence: high)
  - `templates/member.yaml:36` (`Type: AWS::SNS::Topic`)
  - `templates/member.yaml:42` (`Type: AWS::SNS::Topic`)
  - `templates/member.yaml:49` (`Type: AWS::SNS::Topic`)
  - `templates/member.yaml:56` (`Type: AWS::SNS::TopicPolicy`)
  - `tools/migrate.py:270` (`arn = session.client("sns", region_name=region_of(a.topic)).subscribe(`)
- **SQS**: Used for message queue shards and dead-letter queues. (Confidence: high)
  - `templates/central.yaml:268` (`Type: AWS::SQS::Queue`)
  - `templates/central.yaml:275` (`Type: AWS::SQS::Queue`)
  - `templates/central.yaml:284` (`Type: AWS::SQS::QueuePolicy`)
  - `templates/central.yaml:307` (`Type: AWS::SQS::Queue`)
  - `templates/central.yaml:315` (`Type: AWS::SQS::Queue`)
  - `templates/central.yaml:325` (`Type: AWS::SQS::QueuePolicy`)
  - `templates/central.yaml:350` (`Type: AWS::SQS::Queue`)
  - `templates/central.yaml:358` (`Type: AWS::SQS::Queue`)
  - `templates/central.yaml:368` (`Type: AWS::SQS::QueuePolicy`)
- **SSM Parameter Store**: Used for parameter lookup. (Confidence: high)
  - `templates/test-smtp.yaml:20` (`ImageId: {Type: "AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>", Default: /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64}`)
- **STS**: Used for identity resolution and assume-role calls. (Confidence: high)
  - `scripts/deploy.py:53` (`account = session.client("sts").get_caller_identity()["Account"]`)
  - `tools/migrate.py:56` (`creds = session.client("sts").assume_role(RoleArn=role_arn, RoleSessionName="sample-sns-email-migrate")[`)
- **Secrets Manager**: Used for SMTP credentials and CA certificates. (Confidence: high)
  - `src/mailer/handler.py:134` (`sm = boto3.client("secretsmanager", config=AWS)`)
  - `templates/central.yaml:205` (`Type: AWS::SecretsManager::Secret`)
  - `templates/central.yaml:217` (`Type: AWS::SecretsManager::Secret`)

## 2. Mapping table
| AWS service | Google Cloud | trade-off | evidence |
|---|---|---|---|
| CloudWatch | Cloud Logging, Cloud Monitoring | Logs go to Cloud Logging and metrics/alerts to Cloud Monitoring; Cloud Run ships stdout logs automatically. | `templates/central.yaml:447`, `templates/central.yaml:512` |
| DynamoDB | Firestore, Bigtable | Firestore suits document and key-value access with simple queries; Bigtable suits very high throughput wide-column workloads but needs more design. | `templates/central.yaml:227`, `src/mailer/handler.py:68` |
| IAM | Service Accounts, Cloud IAM | IAM roles become service accounts with narrowly scoped predefined roles bound to specific resources. | `templates/central.yaml:394`, `templates/member.yaml:79` |
| KMS | Cloud KMS | Key rings and keys; similar envelope-encryption pattern. | `templates/central.yaml:65`, `templates/central.yaml:107` |
| Lambda | Cloud Run functions, Cloud Run | Cloud Run functions keep the function model; Cloud Run suits containerised handlers and longer requests. | `templates/central.yaml:458` |
| S3 | Cloud Storage | Near drop-in object store; storage classes and lifecycle rules map, but the API and IAM model differ. | `scripts/deploy.py:55` |
| SNS | Pub/Sub | A Pub/Sub topic with subscriptions replaces an SNS topic; push subscriptions cover HTTP fan-out. | `templates/member.yaml:36`, `tools/migrate.py:270` |
| SQS | Pub/Sub | Pub/Sub topic plus pull subscription replaces a queue; scales automatically but is a pub/sub model, not a queue. | `templates/central.yaml:268`, `templates/central.yaml:307` |
| SSM Parameter Store | Secret Manager | Secret Manager covers sensitive parameters; plain configuration is better kept in environment variables. | `templates/test-smtp.yaml:20` |
| STS | Service Accounts | Short-lived credentials come from service account impersonation and workload identity. | `scripts/deploy.py:53`, `tools/migrate.py:56` |
| Secrets Manager | Secret Manager | Close match; secrets are versioned and IAM-controlled. | `templates/central.yaml:205`, `src/mailer/handler.py:134` |

## 3. Target architecture
The target architecture on Google Cloud implements the asynchronous email delivery pipeline using containerised workloads and fully managed messaging and storage services. Pub/Sub replaces SNS and SQS for topic publication and message queuing. Cloud Run hosts the mailer container application, which reads routing configuration and delivery state from Firestore and retrieves SMTP credentials from Secret Manager. Cloud KMS provides envelope encryption keys, while Cloud Logging and Cloud Monitoring collect application logs, metrics, and alerts. Cloud Storage stores application deployment artifacts.

## 4. Risks and unknowns
- **DynamoDB**: Data model, secondary indexes, transactions and capacity model differ; access patterns must be re-validated before choosing the target.
- **IAM**: Policy languages differ; over-broad grants are the main risk, so bind roles per resource and avoid project-wide editor/owner.
- **SQS**: FIFO ordering, visibility timeout and delay semantics differ (ordering keys, ack deadlines); consumers must be idempotent.
- **SNS**: SMS, mobile push and email delivery protocols have no Pub/Sub equivalent; message filtering syntax differs.
- **SSM Parameter Store**: Hierarchical path names and parameter types do not carry over; naming scheme must be redesigned.
- **STS**: Cross-account assume-role patterns need redesign around service account impersonation.
- **Secrets Manager**: Automatic rotation is wired differently (Pub/Sub rotation notifications plus your own function); secret values must be migrated out-of-band, never through the repo.
- **S3**: Code using the S3 API needs the Cloud Storage client or the XML interoperability API; presigned URLs become signed URLs; bucket policies must be rewritten as IAM.
- **Lambda**: Event source wiring (triggers), handler signatures, runtime versions and timeout/concurrency limits differ.
- **CloudWatch**: CloudWatch Logs Insights queries, metric filters and dashboards must be rebuilt; custom metric names differ.
- **KMS**: Existing ciphertext cannot be moved between providers without re-encryption.

## 5. Rollout and rollback
1. **Provision Infrastructure**: Deploy Cloud KMS keys, Firestore databases, Cloud Storage buckets, Secret Manager secrets, and Pub/Sub topics and subscriptions using Terraform.
2. **Deploy Mailer Service**: Build and push the mailer container image to Artifact Registry, then deploy the service on Cloud Run with environment variables and attached Secret Manager secrets.
3. **Dual-Publish / Shadow Mode**: Configure publisher applications to publish to Pub/Sub topics while keeping legacy SNS topics active. Verify message reception and recipient resolution in shadow mode.
4. **Cutover to Live**: Switch Pub/Sub consumers to live mode to send mail through the enterprise SMTP server.
5. **Verify Delivery**: Monitor delivery records in Firestore, check Cloud Logging and Cloud Monitoring metrics, and ensure zero message loss before decommissioning legacy resources.
6. **Rollback Procedure**: If failures occur, revert configuration changes in Firestore to disable live sending or roll back to shadow mode while keeping the legacy AWS infrastructure fully live and untouched until cutover verification is complete.

## 6. IAM least-privilege notes
- **Cloud Run Service Account (`mailer-sa@project.iam.gserviceaccount.com`)**:
  - Bound with `roles/datastore.user` specifically on the Firestore database resource.
  - Bound with `roles/secretmanager.secretAccessor` specifically on the SMTP credentials secret resource in Secret Manager.
  - Bound with `roles/cloudkms.cryptoKeyDecrypter` specifically on the Cloud KMS crypto key resource.
  - Bound with `roles/pubsub.subscriber` specifically on the ingestion Pub/Sub subscription resource.
- **CI/CD Deployment Service Account (`deploy-sa@project.iam.gserviceaccount.com`)**:
  - Bound with `roles/run.admin` on the Cloud Run service.
  - Bound with `roles/storage.objectAdmin` on the deployment artifact Cloud Storage bucket.
  - Bound with `roles/secretmanager.admin` on the Secret Manager secrets.

## 7. Generated artifacts
- terraform/main.tf
- Dockerfile
- .github/workflows/ci.yml