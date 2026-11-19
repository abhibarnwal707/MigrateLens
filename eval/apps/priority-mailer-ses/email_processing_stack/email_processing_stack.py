from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_s3 as s3,
    aws_lambda as lambda_,
    aws_sqs as sqs,
    aws_s3_notifications as s3n,
    aws_lambda_event_sources as lambda_event_sources,
    aws_logs as logs,
    aws_iam as iam,
    CfnOutput
)
from constructs import Construct
from cdk_nag import NagSuppressions


class EmailProcessingStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # S3 Access Logs Bucket
        access_logs_bucket = s3.Bucket(
            self, "AccessLogsBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.RETAIN,
            enforce_ssl=True
        )
        
        # S3 Bucket for email storage
        email_bucket = s3.Bucket(
            self, "EmailBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            versioned=True,
            removal_policy=RemovalPolicy.RETAIN,
            enforce_ssl=True,
            server_access_logs_bucket=access_logs_bucket,
            server_access_logs_prefix="email-bucket-logs/"
        )
        
        # Grant current AWS principal permissions to upload test emails
        email_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.AccountRootPrincipal()],
                actions=[
                    "s3:PutObject",
                    "s3:GetObject",
                    "s3:ListBucket"
                ],
                resources=[
                    email_bucket.bucket_arn,
                    email_bucket.arn_for_objects("*")
                ]
            )
        )
        
        # Dead Letter Queues
        general_dlq = sqs.Queue(
            self, "GeneralDLQ",
            queue_name="email-general-dlq",
            retention_period=Duration.days(14),
            encryption=sqs.QueueEncryption.SQS_MANAGED
        )
        
        priority_dlq = sqs.Queue(
            self, "PriorityDLQ",
            queue_name="email-priority-dlq",
            retention_period=Duration.days(14),
            encryption=sqs.QueueEncryption.SQS_MANAGED
        )
        
        # Add SSL enforcement to DLQs
        general_dlq.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.DENY,
                principals=[iam.AnyPrincipal()],
                actions=["sqs:*"],
                resources=[general_dlq.queue_arn],
                conditions={"Bool": {"aws:SecureTransport": "false"}}
            )
        )
        
        priority_dlq.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.DENY,
                principals=[iam.AnyPrincipal()],
                actions=["sqs:*"],
                resources=[priority_dlq.queue_arn],
                conditions={"Bool": {"aws:SecureTransport": "false"}}
            )
        )
        
        # SQS Queues with DLQs
        general_queue = sqs.Queue(
            self, "GeneralQueue",
            queue_name="email-general-queue",
            visibility_timeout=Duration.seconds(300),
            retention_period=Duration.days(4),
            receive_message_wait_time=Duration.seconds(20),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=general_dlq
            )
        )
        
        priority_queue = sqs.Queue(
            self, "PriorityQueue",
            queue_name="email-priority-queue",
            visibility_timeout=Duration.seconds(300),
            retention_period=Duration.days(4),
            receive_message_wait_time=Duration.seconds(20),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=priority_dlq
            )
        )
        
        # Add SSL enforcement to main queues
        general_queue.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.DENY,
                principals=[iam.AnyPrincipal()],
                actions=["sqs:*"],
                resources=[general_queue.queue_arn],
                conditions={"Bool": {"aws:SecureTransport": "false"}}
            )
        )
        
        priority_queue.add_to_resource_policy(
            iam.PolicyStatement(
                effect=iam.Effect.DENY,
                principals=[iam.AnyPrincipal()],
                actions=["sqs:*"],
                resources=[priority_queue.queue_arn],
                conditions={"Bool": {"aws:SecureTransport": "false"}}
            )
        )
        
        # Create log group for Email Processor Lambda
        email_processor_log_group = logs.LogGroup(
            self, "EmailProcessorLogGroup",
            log_group_name="/aws/lambda/EmailProcessingStack-EmailProcessor",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY
        )
        
        # Custom IAM role for Email Processor
        email_processor_role = iam.Role(
            self, "EmailProcessorRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Custom role for Email Processor Lambda"
        )
        
        # Add CloudWatch Logs permissions
        email_processor_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=[email_processor_log_group.log_group_arn]
            )
        )
        
        # Add S3 read permissions
        email_processor_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:GetObjectVersion"
                ],
                resources=[email_bucket.arn_for_objects("*")]
            )
        )
        
        # Add SQS send permissions
        email_processor_role.add_to_policy(
            iam.PolicyStatement(
                actions=["sqs:SendMessage"],
                resources=[general_queue.queue_arn, priority_queue.queue_arn]
            )
        )
        
        # Email Processor Lambda
        email_processor = lambda_.Function(
            self, "EmailProcessor",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("email_processing_stack/lambda_functions/email_processor"),
            timeout=Duration.seconds(60),
            memory_size=256,
            role=email_processor_role,
            environment={
                "GENERAL_QUEUE_URL": general_queue.queue_url,
                "PRIORITY_QUEUE_URL": priority_queue.queue_url,
                "LOG_LEVEL": "INFO"
            },
            log_group=email_processor_log_group
        )
        
        # Add S3 event notification
        email_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(email_processor)
        )
        
        # Create log group for Queue Consumer Lambda
        queue_consumer_log_group = logs.LogGroup(
            self, "QueueConsumerLogGroup",
            log_group_name="/aws/lambda/EmailProcessingStack-QueueConsumer",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY
        )
        
        # Custom IAM role for Queue Consumer
        queue_consumer_role = iam.Role(
            self, "QueueConsumerRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Custom role for Queue Consumer Lambda"
        )
        
        # Add CloudWatch Logs permissions
        queue_consumer_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogStream",
                    "logs:PutLogEvents"
                ],
                resources=[queue_consumer_log_group.log_group_arn]
            )
        )
        
        # Add S3 read permissions
        queue_consumer_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:GetObjectVersion"
                ],
                resources=[email_bucket.arn_for_objects("*")]
            )
        )
        
        # Add SQS permissions
        queue_consumer_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "sqs:ReceiveMessage",
                    "sqs:DeleteMessage",
                    "sqs:GetQueueAttributes",
                    "sqs:ChangeMessageVisibility"
                ],
                resources=[general_queue.queue_arn, priority_queue.queue_arn]
            )
        )
        
        # Add SES permissions
        ses_policy = iam.PolicyStatement(
            actions=["ses:SendEmail", "ses:SendRawEmail"],
            resources=[
                f"arn:aws:ses:{self.region}:{self.account}:identity/*",
                f"arn:aws:ses:{self.region}:{self.account}:configuration-set/*",
                f"arn:aws:ses:{self.region}:{self.account}:template/*"
            ]
        )
        queue_consumer_role.add_to_policy(ses_policy)
        
        # Suppress cdk-nag warnings for SES wildcard permissions
        NagSuppressions.add_resource_suppressions_by_path(
            self,
            "/EmailProcessingStack/QueueConsumerRole/DefaultPolicy/Resource",
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Wildcard permissions required for SES configuration-set and template resources. "
                              "Lambda needs access to default configuration set for email delivery tracking and "
                              "template resources for dynamic email content. These are standard SES features that "
                              "require wildcard access as resource names are not known at deployment time.",
                    "appliesTo": [
                        f"Resource::arn:aws:ses:{self.region}:<AWS::AccountId>:configuration-set/*",
                        f"Resource::arn:aws:ses:{self.region}:<AWS::AccountId>:template/*",
                        f"Resource::arn:aws:ses:{self.region}:{self.account}:configuration-set/*",
                        f"Resource::arn:aws:ses:{self.region}:{self.account}:template/*"
                    ]
                }
            ]
        )
        
        # Queue Consumer Lambda
        queue_consumer = lambda_.Function(
            self, "QueueConsumer",
            runtime=lambda_.Runtime.PYTHON_3_13,
            handler="handler.lambda_handler",
            code=lambda_.Code.from_asset("email_processing_stack/lambda_functions/queue_consumer"),
            timeout=Duration.seconds(300),
            memory_size=512,
            reserved_concurrent_executions=1,
            role=queue_consumer_role,
            environment={
                "PRIORITY_QUEUE_URL": priority_queue.queue_url,
                "PRIORITY_QUEUE_ARN": priority_queue.queue_arn,
                "VERIFIED_SENDER_EMAIL_OR_DOMAIN": "verified-email@example.com"
            },
            log_group=queue_consumer_log_group
        )
        
        # Add event source mappings for both queues
        queue_consumer.add_event_source(
            lambda_event_sources.SqsEventSource(
                general_queue,
                batch_size=10,
                max_batching_window=Duration.seconds(300),  # Maximum allowed: 5 minutes
                report_batch_item_failures=True
            )
        )
        
        queue_consumer.add_event_source(
            lambda_event_sources.SqsEventSource(
                priority_queue,
                batch_size=5,
                max_batching_window=Duration.seconds(0),  # Immediate processing
                report_batch_item_failures=True
            )
        )
        
        # Stack Outputs
        CfnOutput(
            self, "EmailBucketName",
            value=email_bucket.bucket_name,
            description="S3 bucket for email storage"
        )
        
        CfnOutput(
            self, "GeneralQueueUrl",
            value=general_queue.queue_url,
            description="General queue URL"
        )
        
        CfnOutput(
            self, "PriorityQueueUrl",
            value=priority_queue.queue_url,
            description="Priority queue URL"
        )
        
        CfnOutput(
            self, "EmailProcessorLogGroupOutput",
            value=email_processor_log_group.log_group_name,
            description="Email Processor Lambda log group"
        )
        
        CfnOutput(
            self, "QueueConsumerLogGroupOutput",
            value=queue_consumer_log_group.log_group_name,
            description="Queue Consumer Lambda log group"
        )
