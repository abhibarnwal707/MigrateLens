#!/usr/bin/env python3
"""
Demonstrate priority queue yielding behavior.
"""

import boto3
import time
from datetime import datetime, timezone

BUCKET_NAME = "your-email-bucket-name"  # From CDK output
RECIPIENT_EMAIL = "recipient@example.com"  # Must be SES verified

s3 = boto3.client('s3')

print("\n=== Priority Queue Yielding Demo ===\n")

# Step 1: Upload 5 general emails
print("Step 1: Uploading 5 general emails...")
for i in range(1, 6):
    content = f"""To: {RECIPIENT_EMAIL}
Subject: General Email {i}

This is general email number {i}.
Generated at: {datetime.now(timezone.utc).isoformat()}
"""
    filename = f'general_{i}_{int(time.time() * 1000)}.txt'
    s3.put_object(Bucket=BUCKET_NAME, Key=filename, Body=content.encode('utf-8'))
    print(f"  ✓ {filename}")

# Wait for Lambda to start processing general messages before uploading priority ones
# This delay is intentional and necessary for demonstrating the yielding behavior
print("\nStep 2: Waiting 5 seconds for processing to start...")
time.sleep(5)

# Step 2: Upload 3 priority emails
print("\nStep 3: Uploading 3 URGENT priority emails...")
for i in range(1, 4):
    content = f"""To: {RECIPIENT_EMAIL}
Subject: URGENT: Priority Email {i}

This is URGENT priority email number {i}.
Generated at: {datetime.now(timezone.utc).isoformat()}
"""
    filename = f'priority_{i}_{int(time.time() * 1000)}.txt'
    s3.put_object(Bucket=BUCKET_NAME, Key=filename, Body=content.encode('utf-8'))
    print(f"  ✓ {filename}")

print("\n=== Demo Complete ===\n")
print("Now check CloudWatch Logs Insights with this query:")
print("""
fields @timestamp, message, queue_type, s3_key
| filter function = "queue_consumer" 
| filter message in ["Yielding to priority message", "Email sent successfully via SES"]
| sort @timestamp asc
""")
print("\nYou should see:")
print("  1. General messages being yielded (queue_type: general)")
print("  2. Priority messages processed immediately (queue_type: priority)")
print("  3. General messages processed after priority queue is empty\n")
