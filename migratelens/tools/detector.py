"""Deterministic AWS usage detector (no LLM). Every finding carries file:line evidence.

detect_repo(root) -> {"services": [...], "signals": [...], "possible_secrets": [...]}
Each service: {"service", "evidence": [{"file","line","snippet"}], "confidence"}.
Known limitation: matching is per line, so a client created across several lines is missed.
"""

from __future__ import annotations

import re
from pathlib import Path

from migratelens.tools.repo_reader import list_files, read_file

# raw SDK / resource name (lowercase, no hyphens/underscores) -> canonical service name
CANON = {
    "s3": "S3", "sqs": "SQS", "sns": "SNS", "dynamodb": "DynamoDB", "lambda": "Lambda",
    "secretsmanager": "Secrets Manager", "ses": "SES", "sesv2": "SES", "ecs": "ECS",
    "rds": "RDS", "rdsdata": "RDS", "dbinstance": "RDS", "cloudwatch": "CloudWatch",
    "cloudwatchlogs": "CloudWatch", "logs": "CloudWatch", "iam": "IAM", "ecr": "ECR",
    "kinesis": "Kinesis", "stepfunctions": "Step Functions", "sfn": "Step Functions",
    "sfnstatemachine": "Step Functions", "events": "EventBridge", "eventbridge": "EventBridge",
    "ssm": "SSM Parameter Store", "kms": "KMS", "sts": "STS", "apigateway": "API Gateway",
    "apigatewayv2": "API Gateway", "cognitoidp": "Cognito", "cognito": "Cognito",
    "elasticache": "ElastiCache", "cloudfront": "CloudFront", "route53": "Route 53",
    "fargate": "ECS",
}  # fmt: skip

RANK = {"low": 0, "medium": 1, "high": 2}


def canon(raw: str) -> str | None:
    return CANON.get(re.sub(r"[-_.]", "", raw.lower()))


# SAM (AWS::Serverless::*) resource types and function event types
SAM_TYPE = {
    "function": "Lambda", "layerversion": "Lambda", "api": "API Gateway", "httpapi": "API Gateway",
    "simpletable": "DynamoDB", "statemachine": "Step Functions",
}  # fmt: skip
SAM_EVENT = re.compile(
    r"^\s+Type:\s*(SQS|SNS|S3|Api|HttpApi|Schedule|DynamoDB|Kinesis|EventBridgeRule|CloudWatchEvent)\s*$"
)
SAM_EVENT_SERVICE = {
    "sqs": "SQS", "sns": "SNS", "s3": "S3", "api": "API Gateway", "httpapi": "API Gateway",
    "schedule": "EventBridge", "dynamodb": "DynamoDB", "kinesis": "Kinesis",
    "eventbridgerule": "EventBridge", "cloudwatchevent": "EventBridge",
}  # fmt: skip
# CDK imports: `aws_s3 as s3`, `aws_cdk.aws_s3`, `aws-cdk-lib/aws-s3`
CDK_PY = re.compile(r"\baws_([a-z0-9]+)(?:_[a-z0-9_]+)?\s+as\s+\w+|\baws_cdk\.aws_([a-z0-9]+)")
CDK_TS = re.compile(r"aws-cdk-lib/aws-([a-z0-9]+)")
PY_CLIENT = re.compile(r"""\b(?:client|resource)\(\s*['"]([A-Za-z0-9_-]+)['"]""")
JS_V3 = re.compile(r"""@aws-sdk/(?:client|lib)-([a-z0-9-]+)""")
JS_V2 = re.compile(r"""\bnew\s+AWS\.([A-Za-z0-9]+)\(""")
JAVA = re.compile(r"""(?:software\.amazon\.awssdk|com\.amazonaws)\.services\.([a-z0-9]+)""")
TF_RES = re.compile(r"""^\s*resource\s+"aws_([a-z0-9]+)(?:_[a-z0-9_]+)?"\s+"[^"]+"\s*{""")
CFN = re.compile(r"""["']?Type["']?\s*:\s*["']?AWS::([A-Za-z0-9]+)::""")
SLS_EVENT = re.compile(r"^\s*-\s*(sqs|s3|sns|schedule|http|httpApi|stream)\s*:")
SLS_EVENT_SERVICE = {
    "sqs": "SQS", "s3": "S3", "sns": "SNS", "schedule": "EventBridge",
    "http": "API Gateway", "httpapi": "API Gateway", "stream": "Kinesis",
}  # fmt: skip
ENV_VAR = re.compile(
    r"\b(S3_BUCKET\w*|SQS_QUEUE\w*|SNS_TOPIC\w*|DYNAMODB_TABLE\w*|"
    r"AWS_REGION|AWS_DEFAULT_REGION|AWS_PROFILE)\b"
)
ENV_SERVICE = {
    "S3_BUCKET": "S3", "SQS_QUEUE": "SQS", "SNS_TOPIC": "SNS", "DYNAMODB_TABLE": "DynamoDB",
}  # fmt: skip
SECRET = [
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"""aws_secret_access_key\s*[=:]\s*['"]?[A-Za-z0-9/+=]{30,}""", re.I),
]
COMPOSE_IMAGE = re.compile(r"^\s*image:\s*['\"]?([^\s'\"]+)")
ECR_LAMBDA_BASE = re.compile(r"^\s*FROM\s+public\.ecr\.aws/lambda/", re.I)


def _is_compose(name: str) -> bool:
    return name.startswith(("docker-compose", "compose")) and name.endswith((".yml", ".yaml"))


def _scan_file(rel: str, text: str):
    """Yield (service, line, snippet, confidence) tuples for one file."""
    name = Path(rel).name
    suffix = Path(rel).suffix.lower()
    lines = text.splitlines()
    in_sls = name in ("serverless.yml", "serverless.yaml")
    has_boto = suffix == ".py" and ("boto3" in text or "botocore" in text)

    for i, line in enumerate(lines, 1):
        snip = line.strip()[:160]
        stripped = line.lstrip()
        if stripped.startswith(("#", "//")) and not in_sls:
            continue
        if has_boto and (m := PY_CLIENT.search(line)) and (s := canon(m.group(1))):
            yield s, i, snip, "high"
        for m in JS_V3.finditer(line):
            if s := canon(m.group(1)):
                yield s, i, snip, "medium"
        for m in JS_V2.finditer(line):
            if s := canon(m.group(1)):
                yield s, i, snip, "high"
        for m in JAVA.finditer(line):
            if s := canon(m.group(1)):
                yield s, i, snip, "medium"
        if suffix == ".tf" and (m := TF_RES.match(line)):
            if s := canon(m.group(1)):
                yield s, i, snip, "high"
        if suffix in (".yml", ".yaml", ".json", ".template") and (m := CFN.search(line)):
            if s := canon(m.group(1)):
                yield s, i, snip, "high"
            elif m.group(1) == "Serverless":
                kind = re.search(r"AWS::Serverless::([A-Za-z]+)", line)
                if kind and (s := SAM_TYPE.get(kind.group(1).lower())):
                    yield s, i, snip, "high"
        if suffix in (".yml", ".yaml", ".template") and (m := SAM_EVENT.match(line)):
            yield SAM_EVENT_SERVICE[m.group(1).lower()], i, snip, "medium"
        if suffix == ".py" and ("aws_cdk" in text):
            for m in CDK_PY.finditer(line):
                if s := canon(m.group(1) or m.group(2)):
                    yield s, i, snip, "medium"
        if suffix in (".ts", ".js") and (m := CDK_TS.search(line)):
            if s := canon(m.group(1)):
                yield s, i, snip, "medium"
        if in_sls:
            if re.match(r"^functions\s*:", line):
                yield "Lambda", i, snip, "high"
            if m := SLS_EVENT.match(line):
                yield SLS_EVENT_SERVICE[m.group(1).lower()], i, snip, "high"
            if re.search(r"iamRoleStatements|iam\s*:", line):
                yield "IAM", i, snip, "medium"
        if _is_compose(name) and (m := COMPOSE_IMAGE.match(line)):
            img = m.group(1).lower()
            if "dynamodb-local" in img:
                yield "DynamoDB", i, snip, "medium"
        if name.startswith("Dockerfile") and ECR_LAMBDA_BASE.match(line):
            yield "Lambda", i, snip, "high"
        for m in ENV_VAR.finditer(line):
            var = m.group(1)
            base = next((k for k in ENV_SERVICE if var.startswith(k)), None)
            if base:
                yield ENV_SERVICE[base], i, snip, "low"


def detect_repo(root: str | Path) -> dict:
    root = Path(root)
    services: dict[str, dict] = {}
    signals: list[dict] = []
    secrets: list[dict] = []

    for rel in list_files(root):
        try:
            text = read_file(root, rel)
        except (FileNotFoundError, ValueError):
            continue
        name = Path(rel).name

        if name.startswith("Dockerfile"):
            signals.append({"signal": "dockerfile", "file": rel, "line": 1})
        if _is_compose(name):
            signals.append({"signal": "docker-compose", "file": rel, "line": 1})
        for i, line in enumerate(text.splitlines(), 1):
            if _is_compose(name) and "localstack" in line.lower() and COMPOSE_IMAGE.match(line):
                signals.append({"signal": "localstack", "file": rel, "line": i})
            if any(p.search(line) for p in SECRET):
                secrets.append({"file": rel, "line": i, "note": f"possible secret in file {rel}"})

        for service, line_no, snippet, conf in _scan_file(rel, text):
            entry = services.setdefault(
                service, {"service": service, "evidence": [], "confidence": "low"}
            )
            ev = {"file": rel, "line": line_no, "snippet": _redact(snippet)}
            if ev not in entry["evidence"]:
                entry["evidence"].append(ev)
            if RANK[conf] > RANK[entry["confidence"]]:
                entry["confidence"] = conf

    return {
        "services": sorted(services.values(), key=lambda s: s["service"]),
        "signals": signals,
        "possible_secrets": secrets,
    }


def _redact(snippet: str) -> str:
    """Never echo credential-looking values back, even inside an evidence snippet."""
    for p in SECRET:
        snippet = p.sub("<redacted>", snippet)
    return snippet


if __name__ == "__main__":
    import json
    import sys

    print(json.dumps(detect_repo(sys.argv[1]), indent=2))
