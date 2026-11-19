import os

import boto3

s3 = boto3.client("s3")
queue = boto3.resource("sqs")
# boto3.client("kinesis")  <- commented out, must be ignored
BUCKET = os.environ["S3_BUCKET"]
KEY = "AKIAABCDEFGHIJKLMNOP"
