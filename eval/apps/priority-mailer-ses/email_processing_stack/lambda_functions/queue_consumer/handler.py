import json
import os
import boto3
from datetime import datetime
from typing import Dict, Any

s3_client = boto3.client('s3')
ses_client = boto3.client('ses')
sqs_client = boto3.client('sqs')

PRIORITY_QUEUE_URL = os.environ['PRIORITY_QUEUE_URL']
PRIORITY_QUEUE_ARN = os.environ['PRIORITY_QUEUE_ARN']
VERIFIED_SENDER_EMAIL_OR_DOMAIN = os.environ['VERIFIED_SENDER_EMAIL_OR_DOMAIN']


class PriorityMessageAvailable(Exception):
    """Raised when priority queue has messages available."""
    pass


def log_structured(level: str, message: str, **kwargs):
    """Log structured JSON for easy CloudWatch Insights queries."""
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'level': level,
        'message': message,
        'function': 'queue_consumer',
        **kwargs
    }
    print(json.dumps(log_entry))


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Process messages from SQS queues with priority queue pattern.
    """
    request_id = context.aws_request_id
    batch_size = len(event.get('Records', []))
    
    log_structured('INFO', 'Queue consumer invoked',
                   request_id=request_id,
                   batch_size=batch_size)
    
    returned_messages = []
    
    for record in event['Records']:
        message_id = record['messageId']
        body = json.loads(record['body'])
        is_priority = record['eventSourceARN'] == PRIORITY_QUEUE_ARN
        queue_type = 'priority' if is_priority else 'general'
        s3_key = body.get('key', 'unknown')
        
        try:
            process_record(record, request_id)
        except PriorityMessageAvailable:
            log_structured('INFO', 'Yielding to priority message',
                          request_id=request_id,
                          message_id=message_id,
                          queue_type=queue_type,
                          s3_key=s3_key)
            returned_messages.append(message_id)
        except Exception as exc:
            log_structured('ERROR', 'Failed to process message',
                          request_id=request_id,
                          message_id=message_id,
                          error=str(exc),
                          error_type=type(exc).__name__)
            returned_messages.append(message_id)
    
    success_count = batch_size - len(returned_messages)
    
    log_structured('INFO', 'Queue consumer completed',
                   request_id=request_id,
                   batch_size=batch_size,
                   success_count=success_count,
                   returned_count=len(returned_messages))
    
    return {
        'batchItemFailures': [
            {'itemIdentifier': msg_id} for msg_id in returned_messages
        ]
    }


def process_record(record: Dict[str, Any], request_id: str) -> None:
    """
    Handle the record or raise error when higher priority messages are available.
    """
    message_id = record['messageId']
    body = json.loads(record['body'])
    
    # Determine if this is a priority message
    is_priority_msg = record['eventSourceARN'] == PRIORITY_QUEUE_ARN
    queue_type = 'priority' if is_priority_msg else 'general'
    
    log_structured('INFO', 'Processing message from queue',
                  request_id=request_id,
                  message_id=message_id,
                  queue_type=queue_type,
                  s3_key=body.get('key'),
                  processor_request_id=body.get('processor_request_id'))
    
    # If not priority message, check if priority queue has messages
    if not is_priority_msg:
        check_priority_messages_available()
    
    # Process the message
    handle_record(record, request_id)


def check_priority_messages_available() -> None:
    """
    Check if priority queue has messages available.
    Raises PriorityMessageAvailable if messages exist.
    """
    response = sqs_client.get_queue_attributes(
        QueueUrl=PRIORITY_QUEUE_URL,
        AttributeNames=[
            'ApproximateNumberOfMessages',
            'ApproximateNumberOfMessagesNotVisible',
        ],
    )
    
    for key, value in response['Attributes'].items():
        if int(value) > 0:
            raise PriorityMessageAvailable(f'{key}: {value}')


def handle_record(record: Dict[str, Any], request_id: str) -> None:
    """
    Process individual email message: read from S3 and send via SES.
    """
    message_id = record['messageId']
    body = json.loads(record['body'])
    
    bucket = body['bucket']
    key = body['key']
    size = body['size']
    timestamp = body['timestamp']
    is_priority = record['eventSourceARN'] == PRIORITY_QUEUE_ARN
    queue_type = 'priority' if is_priority else 'general'
    
    processing_start = datetime.utcnow()
    
    log_structured('INFO', 'Starting email processing',
                   request_id=request_id,
                   message_id=message_id,
                   queue_type=queue_type,
                   s3_bucket=bucket,
                   s3_key=key,
                   size_bytes=size,
                   email_timestamp=timestamp)
    
    # DEMO/TESTING: Uncomment the lines below to add a delay for general messages.
    # This makes the yielding behavior more visible during demonstrations.
    # For production use, keep these lines commented out.
    # if not is_priority:
    #     import time
    #     time.sleep(3)  # 3 second delay for general messages
    
    try:
        # Read email content from S3
        log_structured('DEBUG', 'Reading email from S3',
                      request_id=request_id,
                      message_id=message_id,
                      s3_bucket=bucket,
                      s3_key=key)
        
        s3_response = s3_client.get_object(Bucket=bucket, Key=key)
        email_content = s3_response['Body'].read().decode('utf-8')
        
        # Parse email content
        to_address, subject, email_body = parse_email_content(email_content)
        
        log_structured('INFO', 'Email parsed from S3',
                      request_id=request_id,
                      message_id=message_id,
                      to_address=to_address,
                      subject=subject[:100],
                      body_length=len(email_body))
        
        # Send email via SES
        log_structured('INFO', 'Sending email via SES',
                      request_id=request_id,
                      message_id=message_id,
                      to_address=to_address,
                      subject=subject[:100])
        
        ses_response = ses_client.send_email(
            Source=VERIFIED_SENDER_EMAIL_OR_DOMAIN,
            Destination={
                'ToAddresses': [to_address]
            },
            Message={
                'Subject': {
                    'Data': subject,
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Text': {
                        'Data': email_body,
                        'Charset': 'UTF-8'
                    }
                }
            }
        )
        
        ses_message_id = ses_response['MessageId']
        processing_duration = (datetime.utcnow() - processing_start).total_seconds()
        
        log_structured('INFO', 'Email sent successfully via SES',
                      request_id=request_id,
                      message_id=message_id,
                      ses_message_id=ses_message_id,
                      queue_type=queue_type,
                      s3_key=key,
                      to_address=to_address,
                      processing_duration_seconds=processing_duration)
    
    except s3_client.exceptions.NoSuchKey:
        log_structured('ERROR', 'S3 object not found',
                      request_id=request_id,
                      message_id=message_id,
                      s3_bucket=bucket,
                      s3_key=key,
                      error_type='NoSuchKey')
        raise
    
    except Exception as e:
        log_structured('ERROR', 'Failed to process and send email',
                      request_id=request_id,
                      message_id=message_id,
                      s3_bucket=bucket,
                      s3_key=key,
                      error=str(e),
                      error_type=type(e).__name__)
        raise


def parse_email_content(content: str) -> tuple[str, str, str]:
    """
    Parse email content to extract To, Subject, and Body.
    Returns: (to_address, subject, body)
    """
    lines = content.strip().split('\n')
    to_address = ""
    subject = ""
    body = ""
    body_start_index = 0
    
    for i, line in enumerate(lines):
        if line.startswith('To:'):
            to_address = line[3:].strip()
        elif line.startswith('Subject:'):
            subject = line[8:].strip()
        elif line.strip() == '' and to_address and subject:
            # Empty line after headers indicates body starts
            body_start_index = i + 1
            break
    
    if body_start_index > 0:
        body = '\n'.join(lines[body_start_index:]).strip()
    
    return to_address, subject, body
