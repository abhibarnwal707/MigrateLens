## 1. Architecture inventory
- **API Gateway**: Managed API ingress defined in serverless template (`sam/template.yaml:36`, confidence: high).
- **DynamoDB**: NoSQL user state table accessed via boto3 (`lambda_function.py:31`, confidence: high).
- **Lambda**: Serverless compute function handling webhook events (`sam/template.yaml:19`, confidence: high).
- **S3**: Object storage for processed images and deployment packages (`basic_lambda_function.py:14`, `lambda_function.py:28`, confidence: high).

## 2. Mapping table
| AWS service | Google Cloud | trade-off | evidence |
|---|---|---|---|
| API Gateway | API Gateway | Managed API front door for Cloud Run and other backends using OpenAPI configs. | `sam/template.yaml:36` |
| DynamoDB | Firestore, Bigtable | Firestore suits document and key-value access with simple queries; Bigtable suits very high throughput wide-column workloads but needs more design. | `lambda_function.py:31` |
| Lambda | Cloud Run functions, Cloud Run | Cloud Run functions keep the function model; Cloud Run suits containerised handlers and longer requests. | `sam/template.yaml:19` |
| S3 | Cloud Storage | Near drop-in object store; storage classes and lifecycle rules map, but the API and IAM model differ. | `lambda_function.py:28` |

## 3. Target architecture
Incoming webhook requests from Twilio arrive at API Gateway, which proxies traffic to Cloud Run functions (or Cloud Run). The request handler validates user state against Firestore, fetches and transforms incoming images, and persists processed assets into Cloud Storage. Public URLs are generated for retrieved objects and returned via the HTTP response.

## 4. Risks and unknowns
- **DynamoDB**: Firestore is not a direct equivalent (`direct: false`). Data model, secondary indexes, transactions and capacity model differ; access patterns must be re-validated before choosing the target.
- **Lambda**: Event source wiring (triggers), handler signatures, runtime versions and timeout/concurrency limits differ.
- **API Gateway**: Authorizers, usage plans and stage variables map unevenly; the API config must be re-expressed.
- **S3**: Code using the S3 API needs the Cloud Storage client or the XML interoperability API; presigned URLs become signed URLs; bucket policies must be rewritten as IAM.

## 5. Rollout and rollback
1. Provision target Google Cloud infrastructure using Terraform (API Gateway, Cloud Run functions, Firestore, Cloud Storage).
2. Deploy the application code to Cloud Run functions while keeping AWS Lambda, API Gateway, DynamoDB, and S3 fully live and operational.
3. Configure a small percentage of traffic (or test webhook endpoints) against the Google Cloud API Gateway while monitoring error rates and logs.
4. Perform end-to-end integration testing of SMS ingestion, image filtering, and storage retrieval on Google Cloud.
5. Cut over DNS / Twilio webhook destination URL from AWS API Gateway to Google Cloud API Gateway.
6. Keep AWS services live for a verification window, ready for an immediate rollback by reverting the webhook URL if anomalies occur.
7. Decommission AWS resources only after stable operation is verified.

## 6. IAM least-privilege notes
- Create a dedicated Google Cloud service account for the Cloud Run function workload (e.g., `app-runtime-sa@project.iam.gserviceaccount.com`).
- Grant `roles/datastore.user` to the service account scoped specifically to the Firestore database.
- Grant `roles/storage.objectAdmin` to the service account scoped strictly to the Cloud Storage bucket used for image storage.
- Grant `roles/apigateway.viewer` or invocation permissions solely to the API Gateway service agent interacting with Cloud Run.

## 7. Generated artifacts
- terraform/main.tf
- Dockerfile
- .github/workflows/ci.yml