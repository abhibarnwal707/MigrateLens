#!/usr/bin/env python3
import os
import aws_cdk as cdk
from cdk_nag import AwsSolutionsChecks, NagSuppressions
from email_processing_stack.email_processing_stack import EmailProcessingStack

app = cdk.App()

stack = EmailProcessingStack(
    app, "EmailProcessingStack",
    description="Email processing pipeline with S3, Lambda, SQS and SES",
    env=cdk.Environment(
        account=os.environ.get('CDK_DEFAULT_ACCOUNT'),
        region=os.environ.get('CDK_DEFAULT_REGION')
    )
)

# Add cdk-nag checks
cdk.Aspects.of(app).add(AwsSolutionsChecks(verbose=True))

# Suppress legitimate wildcard permissions with justifications
NagSuppressions.add_stack_suppressions(
    stack,
    [
        {
            "id": "AwsSolutions-IAM5",
            "reason": "S3 wildcard permissions required to read any email object from bucket. Scope limited to specific bucket ARN.",
            "appliesTo": [
                "Resource::<EmailBucket843A740F.Arn>/*"
            ]
        },
        {
            "id": "AwsSolutions-IAM5",
            "reason": "SES wildcard permissions required to send emails from any verified identity (email or domain). Scope limited to SES identities in this account/region.",
            "appliesTo": [
                {
                    "regex": "/^Resource::arn:aws:ses:.*:identity/\\*$/g"
                }
            ]
        },
        {
            "id": "AwsSolutions-L1",
            "reason": "Using Python 3.13 which is the latest available runtime. cdk-nag may not have updated its runtime version database yet."
        },
        {
            "id": "AwsSolutions-IAM4",
            "reason": "BucketNotificationsHandler is an internal CDK construct that manages S3 event notifications. AWS managed policy is acceptable for this infrastructure component.",
            "appliesTo": [
                "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
            ]
        }
    ]
)

app.synth()
