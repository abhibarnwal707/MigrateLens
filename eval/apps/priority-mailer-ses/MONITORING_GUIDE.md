# CloudWatch Monitoring Guide

## Quick Start

### Run the Demo

```bash
# Update bucket name and recipient email in demo_priority_yielding.py
python3 demo_priority_yielding.py
```

**What happens:**
1. Uploads 5 general emails → Lambda starts processing (3-second delay per message)
2. Waits 5 seconds, then uploads 3 priority emails mid-processing
3. General messages yield when they detect priority messages
4. Priority messages process immediately
5. General messages resume after priority queue empties

### Watch Live

```bash
# Queue Consumer logs
aws logs tail /aws/lambda/EmailProcessingStack-QueueConsumer --follow

# Email Processor logs
aws logs tail /aws/lambda/EmailProcessingStack-EmailProcessor --follow
```

**Look for:**
- "Yielding to priority message" entries
- Priority emails processed first
- General emails processed after priority queue empties

---

## Log Analysis Tips

- Use structured JSON logs for easy querying in CloudWatch Insights
- Filter by `request_id` to track a single execution across logs
- Filter by `s3_key` or `key` to track a specific email through the pipeline
- Check `level = "ERROR"` to identify failures

---

## CloudWatch Insights Queries

### 1. Processing Timeline (Shows Priority Pattern)

```
fields @timestamp, message, queue_type, s3_key
| filter function = "queue_consumer"
| filter message = "Email sent successfully via SES" or message = "Yielding to priority message"
| sort @timestamp asc
```

### 2. Processing Summary by Queue

```
fields @timestamp, queue_type
| filter function = "queue_consumer" and message = "Email sent successfully via SES"
| stats count() by queue_type
```

### 3. Yield Events

```
fields @timestamp, message_id, s3_key
| filter function = "queue_consumer" and message = "Yielding to priority message"
| sort @timestamp asc
```

### 4. Email Classification

```
fields @timestamp, key, priority, queue_type, subject
| filter function = "email_processor" and message = "Email classified and routing decision made"
| sort @timestamp asc
```

### 5. Processing Duration by Queue

```
fields @timestamp, queue_type, processing_duration_seconds, s3_key
| filter function = "queue_consumer" and message = "Email sent successfully via SES"
| stats avg(processing_duration_seconds) as avg_duration by queue_type
```

### 6. Error Tracking

```
fields @timestamp, message, error, s3_key
| filter level = "ERROR"
| sort @timestamp desc
```

---

## Additional Queries

### Track Message Flow (S3 to SQS)

```
fields @timestamp, key, queue_type, message_id
| filter function = "email_processor" and message = "Message sent to SQS"
| sort @timestamp desc
| limit 100
```

### Validate Complete Workflow

Track a specific email through the entire pipeline:

```
fields @timestamp, function, message, queue_type, message_id
| filter s3_key = "test-email.txt" or key = "test-email.txt"
| sort @timestamp asc
```

---

## Check SQS Queue Depths

```bash
# Get queue URLs from stack outputs
GENERAL_QUEUE=$(aws cloudformation describe-stacks --stack-name EmailProcessingStack \
  --query 'Stacks[0].Outputs[?OutputKey==`GeneralQueueUrl`].OutputValue' --output text)

PRIORITY_QUEUE=$(aws cloudformation describe-stacks --stack-name EmailProcessingStack \
  --query 'Stacks[0].Outputs[?OutputKey==`PriorityQueueUrl`].OutputValue' --output text)

# Check general queue
aws sqs get-queue-attributes --queue-url $GENERAL_QUEUE \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible

# Check priority queue
aws sqs get-queue-attributes --queue-url $PRIORITY_QUEUE \
  --attribute-names ApproximateNumberOfMessages ApproximateNumberOfMessagesNotVisible
```

---

## Creating a Dashboard

1. **Go to CloudWatch Console** → Dashboards → Create dashboard
2. **Add widgets** using queries above:
   - Processing Timeline (Logs table)
   - Queue Distribution (Pie chart)
   - Yield Count (Number widget)
   - Processing Duration (Line graph)
   - Error Count (Number widget)
3. **Set auto-refresh** to 1 minute

---

## Expected Results

**Successful priority pattern:**
- ✓ All emails processed (5 general + 3 priority)
- ✓ Priority emails processed first
- ✓ "Yielding to priority message" logged for general messages
- ✓ Same general message IDs appear twice (yielded, then completed)
- ✓ All emails delivered via SES

---

## Troubleshooting

**No emails processing?**
- Check S3 event notification configured
- Verify Lambda has S3 read permissions

**Emails not sent via SES?**
- Verify SES identity (email/domain)
- Check SES sandbox mode (recipient must be verified)

**Not seeing yield behavior?**
- Verify reserved concurrency = 1
- Ensure 3-second delay uncommented in code
- Priority messages must arrive during general processing

**Messages stuck in queue?**
- Check Lambda event source mappings enabled
- Verify visibility timeout settings (30 seconds default)
