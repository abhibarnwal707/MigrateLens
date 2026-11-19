# Priority Email Processing CDK Solution using Amazon SES

## Overview

This project implements an intelligent email processing pipeline using AWS CDK (Python). The stack creates an automated workflow that:
1. Classifies emails based on content (urgent keywords detection)
2. Routes them through priority-based SQS queues
3. Processes priority emails first using the priority queue pattern
4. Sends emails via Amazon SES

## ⚠️ Sample Code Notice

This is sample code for demonstration and educational purposes only. It is not intended for production use without significant modifications and additional security hardening. This code is provided "as-is" with no warranty or support guarantees.

**⚠️ Cost Warning**: Deploying this solution will incur AWS charges for Lambda invocations, S3 storage, SQS requests, SES email sending, and CloudWatch logs. See the [Cost Considerations](#cost-considerations) section for estimates.

## Security and Compliance Considerations

### Security Best Practices

This sample demonstrates the priority queue pattern for educational purposes. For production deployments, implement these additional security configurations:

1. **Enhanced Encryption**: 
   - This solution uses S3 default encryption (SSE-S3) and SQS server-side encryption
   - For additional security requirements, configure AWS KMS Customer Managed Keys (CMK) for both S3 bucket encryption and SQS queue encryption
   - Enable encryption in transit for all service communications

2. **Private Network Access**: 
   - Deploy resources within a VPC with private subnets
   - Configure VPC endpoints for S3, SQS, and SES to keep traffic within the AWS network
   - Deploy Lambda functions within VPC private subnets with appropriate security groups
   - Use AWS PrivateLink endpoints to avoid internet gateway traffic

3. **IAM Permissions**:
   - This sample uses least-privilege IAM roles scoped to specific resources
   - Review and further restrict permissions based on your organization's security policies
   - Avoid using AWS managed policies in production; use custom policies with minimal required permissions

4. **Logging Best Practices**: 
   - The detailed logging shown in this solution is designed to demonstrate priority queue behavior
   - In production: limit logs to required metadata only, avoid logging Personally Identifiable Information (PII), implement log filtering and redaction mechanisms, and comply with your organization's data retention policies

### Email Compliance

When using this solution for email sending, ensure compliance with:

- **CAN-SPAM Act**: Include physical address, clear unsubscribe mechanism, and accurate sender information
- **GDPR**: Obtain proper consent for email processing, implement data subject rights, and maintain audit trails
- **Industry Regulations**: Follow applicable email marketing and communication regulations for your jurisdiction
- **Unsubscribe Mechanisms**: Implement proper opt-out functionality (not included in this sample)

### Testing Environment

- **Deploy in non-production account first**: Test thoroughly in a separate AWS account before production use
- **SES Sandbox Limitations**: New AWS accounts start in SES sandbox mode with sending restrictions
- **Verify all email addresses**: In sandbox mode, both sender and recipient addresses must be verified

## Architecture

![Architecture Diagram](architecture.png)

### Components

- **S3 Bucket**: Private bucket for storing email files with encryption and versioning enabled
- **S3 Access Logs Bucket**: Dedicated bucket for storing S3 server access logs
- **Email Processor Lambda**: 
  - Triggered by S3 PUT/CREATE events
  - Reads email content from S3
  - Classifies emails based on keywords (urgent, critical, alert, outage, emergency, immediate)
  - Routes to priority or general queue based on classification
- **SQS Queues**: Two standard queues for message buffering
  - **Priority Queue**: For high-priority emails (immediate processing)
  - **General Queue**: For standard emails (batched processing)
  - **Dead Letter Queues**: Separate DLQs for both queues (14-day retention)
- **Queue Consumer Lambda**: 
  - Single Lambda with event source mappings to both queues
  - Implements priority queue pattern (yields general messages when priority messages exist)
  - Reads full email content from S3
  - Sends emails via Amazon SES
  - Reserved concurrency: 1 (for clear demonstration of yielding behavior)

### Priority Queue Pattern

The queue consumer implements the priority queue pattern with yielding behavior:

**How it works:**
1. Single Lambda function with event source mappings to both queues
2. When processing a general queue message:
   - Checks if priority queue has messages (visible or in-flight)
   - If priority messages exist, raises exception to return message to queue (yields)
   - Message becomes visible again after visibility timeout
3. Priority messages are processed immediately without checking
4. Uses partial batch response to return yielded messages efficiently

**Demonstration setup:**
- Reserved concurrency: 1 (ensures only one message processes at a time)
- For local testing/demos: Uncomment the sleep timer in `queue_consumer/handler.py` (see Testing section)
- This creates a clear yielding scenario for testing

**Timeline example (with optional delay enabled):**
```
00:00 - General message 1 starts (3-second processing delay)
00:02 - Priority messages uploaded to S3
00:03 - General message checks priority queue → sees messages → YIELDS
00:03 - Priority message 1 starts (no delay, immediate processing)
00:04 - Priority message 1 completes
00:04 - Priority message 2 starts
00:05 - Priority message 2 completes
00:05 - General message 1 retried and completes
```

**Result:** Priority messages interrupt general message processing and are handled first.

## Prerequisites

Before you begin, ensure you have the following:

### Required Software
- **Python 3.9 or higher**: Required for CDK and Lambda functions (Python 3.13 recommended)
- **AWS CLI**: Configured with appropriate credentials
  ```bash
  aws configure
  ```
- **AWS CDK CLI**: Install globally via npm
  ```bash
  npm install -g aws-cdk
  ```

### AWS Account Requirements
- Appropriate permissions to create:
  - S3 buckets
  - Lambda functions
  - SQS queues
  - IAM roles and policies
  - CloudWatch log groups
  - SES send permissions

### Amazon SES Setup (REQUIRED)
Before deploying, you **must** verify an email address or domain in Amazon SES:

1. **Go to AWS SES Console** in your deployment region
2. **Verify an identity**:
   - **Option A - Email Address**: Verify a single email (e.g., `sender@example.com`)
     - Go to "Verified identities" → "Create identity"
     - Select "Email address"
     - Enter your email and click "Create identity"
     - Check your inbox and click the verification link
   
   - **Option B - Domain**: Verify an entire domain (e.g., `example.com`)
     - Go to "Verified identities" → "Create identity"
     - Select "Domain"
     - Enter your domain and follow DNS verification steps

3. **SES Sandbox Mode** (default for new accounts):
   - Can only send to verified email addresses
   - Limited to 200 emails/day
   - **For testing**: Also verify recipient email addresses
   - **For production**: Request production access to remove limits

4. **Update CDK Stack**: 
   - Edit `email_processing_stack/email_processing_stack.py`
   - Replace `"verified-email@example.com"` with your verified identity
   - Can be an email address or domain

## Installation

### 1. Create Virtual Environment

```bash
# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate.bat
```

### 2. Install Dependencies

```bash
pip install -e .
```

### 3. Bootstrap CDK (First Time Only)

```bash
cdk bootstrap
```

## Deployment

### Synthesize CloudFormation Template

Before deploying, you can generate and review the CloudFormation template:

```bash
cdk synth
```

This creates a `cdk.out` directory containing the synthesized CloudFormation template and runs cdk-nag security checks to ensure compliance with AWS Solutions best practices.

### Deploy the Stack

Deploy the stack to your AWS account:

```bash
cdk deploy
```

You'll be prompted to approve IAM changes and security-related modifications. Review them and type `y` to proceed.

### View Stack Outputs

After deployment, CDK will display important outputs:
- **EmailBucketName**: S3 bucket name for uploading emails
- **GeneralQueueUrl**: URL of the general processing queue
- **PriorityQueueUrl**: URL of the priority processing queue
- **EmailProcessorLogGroup**: CloudWatch log group for email processor
- **QueueConsumerLogGroup**: CloudWatch log group for queue consumer

You can also retrieve outputs later:
```bash
aws cloudformation describe-stacks --stack-name EmailProcessingStack --query 'Stacks[0].Outputs'
```

## Testing

### Demonstrate Priority Queue Yielding

Use the automated demo script to show how general queue messages yield to priority messages:

```bash
# 1. OPTIONAL - Enable processing delay for clearer demonstration:
#    Edit lambda_functions/queue_consumer/handler.py
#    Uncomment lines 156-158 (the sleep timer code)
#    Redeploy: cdk deploy

# 2. Update the script with your bucket name and recipient email
# Edit demo_priority_yielding.py and set:
#   BUCKET_NAME = "your-email-bucket-name"  # From CDK output
#   RECIPIENT_EMAIL = "recipient@example.com"  # Must be SES verified

# 3. Run the demo script
python3 demo_priority_yielding.py
```

**What the demo does:**
1. Uploads 5 general emails to create a processing queue
2. Waits 5 seconds for Lambda to start processing general messages
3. Uploads 3 priority emails while general processing is in progress
4. General messages yield (return to queue) when priority messages arrive
5. Priority messages are processed immediately
6. General messages resume processing after priority queue is empty

**Note on processing delay:**
- The optional 3-second delay makes yielding behavior more visible during demos
- Without the delay, yielding still occurs but happens faster
- For production use, keep the delay commented out

**Verify yielding behavior in CloudWatch Logs Insights:**
```
fields @timestamp, message, queue_type, s3_key
| filter function = "queue_consumer" 
| filter message in ["Yielding to priority message", "Email sent successfully via SES"]
| sort @timestamp asc
```

**Expected output:**
- General messages showing "Yielding to priority message" (queue_type: general)
- Priority messages processed immediately (queue_type: priority)
- Same general message IDs appearing twice (yielded, then processed later)

**Monitor the results:**
- Watch logs in real-time: `aws logs tail /aws/lambda/EmailProcessingStack-QueueConsumer --follow`
- For comprehensive monitoring: See `MONITORING_GUIDE.md` for CloudWatch Insights queries, dashboard setup, and troubleshooting

**CloudWatch Dashboard:**

![CloudWatch Dashboard](cloudwatch-dashboard.png)

The dashboard provides real-time visibility into:
- Lambda invocations and errors
- SQS queue depths and message flow
- Priority queue yielding behavior
- Email processing metrics

## Cleanup

### Important: Avoid Ongoing Costs

To avoid incurring AWS charges, follow these steps to completely remove all resources:

### Step 1: Destroy the Stack

```bash
cdk destroy
```

This removes:
- ✅ Lambda functions
- ✅ SQS queues
- ✅ CloudWatch log groups
- ✅ IAM roles and policies
- ✅ S3 event notifications
- ❌ S3 bucket (retained for safety)

### Step 2: Delete S3 Bucket (Required)

**Important**: The S3 bucket has a `RETAIN` removal policy to prevent accidental data loss. You **must** manually delete it to avoid storage costs:

```bash
# Get bucket name from stack outputs (before destroying)
BUCKET_NAME=$(aws cloudformation describe-stacks --stack-name EmailProcessingStack \
  --query 'Stacks[0].Outputs[?OutputKey==`EmailBucketName`].OutputValue' --output text)

# Empty the bucket first (required before deletion)
aws s3 rm s3://$BUCKET_NAME --recursive

# Delete the bucket
aws s3 rb s3://$BUCKET_NAME

# Verify deletion
aws s3 ls | grep email
```

### Step 3: Verify All Resources Deleted

```bash
# Check CloudFormation stacks
aws cloudformation list-stacks --stack-status-filter DELETE_COMPLETE \
  --query 'StackSummaries[?StackName==`EmailProcessingStack`]'

# Check S3 buckets
aws s3 ls | grep email

# Check Lambda functions
aws lambda list-functions --query 'Functions[?contains(FunctionName, `EmailProcessing`)]'

# Check SQS queues
aws sqs list-queues --queue-name-prefix email
```

### Cost Breakdown (If Not Deleted)

**Ongoing costs if resources remain:**
- S3 Storage: ~$0.023 per GB/month
- CloudWatch Logs: $0.50 per GB ingested
- Lambda: Minimal (only charged when invoked)
- SQS: Minimal (only charged for requests)

**Total estimated cost if idle**: ~$1-5/month depending on log retention and S3 storage

### Troubleshooting Cleanup

**Issue**: `cdk destroy` fails
- **Solution**: Check if Lambda functions are still processing messages. Wait a few minutes and retry.

**Issue**: S3 bucket deletion fails with "BucketNotEmpty"
- **Solution**: Ensure you ran `aws s3 rm s3://$BUCKET_NAME --recursive` first

**Issue**: Stack shows DELETE_FAILED
- **Solution**: Check CloudFormation console for specific resource errors. May need to manually delete stuck resources.

## Architecture Details

### Security Features

- **S3 Bucket**: 
  - Private access only
  - Encryption at rest (SSE-S3)
  - SSL/TLS enforced
  - Server access logging enabled
  - Versioning enabled
- **IAM Roles**: 
  - Custom roles with least privilege permissions
  - No AWS managed policies (except internal CDK constructs)
  - Granular permissions scoped to specific resources
- **SQS Queues**: 
  - Server-side encryption (SQS-managed)
  - Dead Letter Queues configured (max 3 retries)
  - SSL/TLS enforcement via resource policies
- **Lambda**: 
  - Python 3.13 runtime (latest available)
  - Custom IAM roles with minimal permissions
  - Environment variables encrypted with AWS-managed keys
- **Security Compliance**: 
  - cdk-nag integration for automated security checks
  - AWS Solutions best practices enforced
  - All findings documented and addressed

### Data Flow

1. Email file uploaded to S3 bucket
2. S3 event notification triggers Email Processor Lambda
3. Lambda reads email content from S3 and classifies based on keywords
4. Message (with S3 reference) sent to appropriate SQS queue
5. Queue Consumer Lambda polls both queues via event source mappings
6. Consumer implements priority queue pattern:
   - General queue messages check if priority queue has messages
   - If priority messages exist, general message is returned to queue (yields)
   - Priority messages are always processed immediately
7. Consumer reads full email from S3 and sends via SES
8. Messages processed with different batch configurations:
   - General queue: Batch size 10, 5-minute batching window
   - Priority queue: Batch size 5, immediate processing

### Routing Logic

The Email Processor classifies emails based on content:
- **High Priority Keywords**: urgent, critical, alert, outage, emergency, immediate
- Checks both subject and body for keywords (case-insensitive)
- Routes to priority queue if any keyword found
- Default: Routes to general queue

### Priority Queue Pattern Details

**How it works:**
1. Both queues have Event Source Mappings to the same Lambda
2. Lambda checks `eventSourceARN` to identify source queue
3. For general queue messages:
   - Calls `sqs:GetQueueAttributes` on priority queue
   - Checks `ApproximateNumberOfMessages` and `ApproximateNumberOfMessagesNotVisible`
   - If either > 0, raises exception to return message to queue
4. For priority queue messages: Processes immediately
5. Uses partial batch response to return yielded messages

## Cost Considerations

### Estimated Monthly Costs (Low Volume)

- **S3**: ~$0.023 per GB stored
- **Lambda**: First 1M requests free, then $0.20 per 1M requests
- **SQS**: First 1M requests free, then $0.40 per 1M requests
- **CloudWatch Logs**: $0.50 per GB ingested

### Cost Optimization Tips

- Use S3 lifecycle policies to transition old emails to cheaper storage classes
- Set appropriate Lambda memory sizes (currently 256 MB and 512 MB)
- Use SQS long polling to reduce empty receive requests
- Set CloudWatch log retention policies (currently 7 days)

## Future Enhancements

Potential improvements to consider:

- Add email parsing and content extraction
- Add SNS notifications for processing failures
- Implement email archival to S3 Glacier
- Implement email validation and virus scanning
- Add metrics dashboard with CloudWatch
- Implement X-Ray tracing for debugging

## Project Structure

```
email-processing-stack/
├── README.md
├── pyproject.toml              # Python project configuration
├── app.py                      # CDK app entry point
├── cdk.json                    # CDK configuration
├── .gitignore
├── email_processing_stack/
│   ├── __init_y_.py
│   └── email_processing_stack.py   # Main CDK stack definition
└── lambda_functions/
    ├── email_processor/
    │   ├── __init__.py
    │   └── handler.py          # Email processing logic
    └── queue_consumer/
        ├── __init__.py
        └── handler.py          # Queue consumption logic
```

## Support

For issues or questions:
- Review CloudWatch logs for detailed error messages
- Check AWS service quotas and limits
- Review security compliance details in the Security Features section
- Consult AWS CDK documentation: https://docs.aws.amazon.com/cdk/
- Review Lambda best practices: https://docs.aws.amazon.com/lambda/latest/dg/best-practices.html
