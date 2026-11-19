import json
import boto3
import os
import logging
from datetime import datetime
from typing import Dict, Any, Tuple
from urllib.parse import unquote_plus

# Configure structured logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

s3_client = boto3.client('s3')
sqs_client = boto3.client('sqs')

GENERAL_QUEUE_URL = os.environ['GENERAL_QUEUE_URL']
PRIORITY_QUEUE_URL = os.environ['PRIORITY_QUEUE_URL']


def log_structured(level: str, message: str, **kwargs):
    """Log structured JSON for easy CloudWatch Insights queries."""
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'level': level,
        'message': message,
        'function': 'email_processor',
        **kwargs
    }
    print(json.dumps(log_entry))


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Process S3 event and route email to appropriate SQS queue based on content classification.
    """
    request_id = context.aws_request_id
    
    log_structured('INFO', 'Email processor invoked', 
                   request_id=request_id,
                   record_count=len(event.get('Records', [])))
    
    try:
        processed_count = 0
        
        for record in event['Records']:
            bucket = record['s3']['bucket']['name']
            key = unquote_plus(record['s3']['object']['key'])
            event_name = record['eventName']
            object_size = record['s3']['object']['size']
            
            log_structured('INFO', 'Processing S3 event',
                          request_id=request_id,
                          bucket=bucket,
                          key=key,
                          event_name=event_name)
            
            # Get email content for classification
            response = s3_client.get_object(Bucket=bucket, Key=key)
            email_content = response['Body'].read().decode('utf-8')
            
            # Parse and classify email
            subject, body = parse_email_content(email_content)
            priority = classify_email(subject, body)
            
            # Determine queue based on classification
            is_priority = priority == 'high'
            queue_url = PRIORITY_QUEUE_URL if is_priority else GENERAL_QUEUE_URL
            queue_type = 'priority' if is_priority else 'general'
            
            log_structured('INFO', 'Email classified and routing decision made',
                          request_id=request_id,
                          key=key,
                          queue_type=queue_type,
                          priority=priority,
                          size_bytes=object_size,
                          subject=subject[:100])  # Log first 100 chars of subject
            
            # Prepare message
            message = {
                'bucket': bucket,
                'key': key,
                's3_url': f's3://{bucket}/{key}',
                'priority': priority,
                'size': object_size,
                'timestamp': record['eventTime'],
                'subject': subject,
                'processor_request_id': request_id,
                'queue_type': queue_type
            }
            
            # Send to SQS
            sqs_response = sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(message)
            )
            
            log_structured('INFO', 'Message sent to SQS',
                          request_id=request_id,
                          key=key,
                          queue_type=queue_type,
                          priority=priority,
                          message_id=sqs_response['MessageId'],
                          queue_url=queue_url)
            
            processed_count += 1
        
        log_structured('INFO', 'Email processor completed successfully',
                      request_id=request_id,
                      processed_count=processed_count)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Processing complete',
                'processed_count': processed_count
            })
        }
    
    except Exception as e:
        log_structured('ERROR', 'Email processor failed',
                      request_id=request_id,
                      error=str(e),
                      error_type=type(e).__name__)
        raise


def parse_email_content(content: str) -> Tuple[str, str]:
    """
    Parse email content to extract subject and body.
    """
    lines = content.strip().split('\n')
    subject = ""
    body = ""
    body_start_index = 0
    
    for i, line in enumerate(lines):
        if line.startswith('Subject:'):
            subject = line[8:].strip()
        elif line.startswith('To:'):
            # Continue parsing, don't break yet
            pass
        elif line.strip() == '' and subject:
            # Empty line after headers indicates body starts
            body_start_index = i + 1
            break
    
    if body_start_index > 0:
        body = '\n'.join(lines[body_start_index:]).strip()
    
    return subject, body


def classify_email(subject: str, body: str) -> str:
    """
    Classify email priority based on content.
    Returns 'high' or 'low'.
    """
    high_priority_keywords = ['urgent', 'critical', 'alert', 'outage', 'emergency', 'immediate']
    text_to_check = f"{subject} {body}".lower()
    
    return 'high' if any(keyword in text_to_check for keyword in high_priority_keywords) else 'low'
