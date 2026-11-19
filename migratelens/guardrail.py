"""Evidence guardrail, enforced in code (not just in the prompt).

A plan is accepted only if:
  1. every AWS service it names exists in the detector inventory (evidence in the repo),
  2. every Google Cloud product it names exists in mapping.yaml,
  3. every file (and file:line) it cites exists in the repo (or is a generated artifact),
  4. it contains no dollar amounts (cost claims need a source we do not have).

Known limits: AWS/GCP names are recognised from fixed vocabularies, so a made-up product name
outside both lists is not caught. Generic 'IAM' is always allowed because it is ambiguous.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from migratelens.tools import mapper, repo_reader

GENERATED_ARTIFACTS = {"terraform/main.tf", "Dockerfile", ".github/workflows/ci.yml"}

# surface name -> canonical name used in mapping.yaml / the detector
AWS_ALIASES = {
    "Fargate": "ECS", "Simple Storage Service": "S3", "Simple Queue Service": "SQS",
    "Simple Notification Service": "SNS", "Parameter Store": "SSM Parameter Store",
    "CloudWatch Logs": "CloudWatch", "Secrets Manager": "Secrets Manager",
    "Elastic Container Service": "ECS", "Relational Database Service": "RDS",
    "Simple Email Service": "SES", "Key Management Service": "KMS",
    "Elastic Container Registry": "ECR", "Step Functions": "Step Functions",
}  # fmt: skip
# Real AWS services the detector/mapping do not cover: naming one without evidence is a violation.
AWS_EXTRA = {
    "EC2", "Redshift", "Glue", "Athena", "EMR", "SageMaker", "Kendra", "Textract", "Rekognition",
    "Comprehend", "Bedrock", "Aurora", "Neptune", "DocumentDB", "MSK", "OpenSearch", "EKS", "ELB",
    "ALB", "VPC", "CodeBuild", "CodePipeline", "Amplify", "AppSync", "Glacier", "EFS", "EBS",
    "Lightsail", "Elastic Beanstalk", "QuickSight", "Timestream", "Keyspaces", "CloudTrail",
    "GuardDuty", "WAF", "Firehose", "App Runner", "Transfer Family", "Direct Connect",
}  # fmt: skip
AWS_EXEMPT = {"IAM"}

GCP_ALIASES = {
    "Cloud Firestore": "Firestore", "Cloud Pub/Sub": "Pub/Sub", "Cloud Bigtable": "Bigtable",
    "Google Cloud Storage": "Cloud Storage", "Cloud Key Management Service": "Cloud KMS",
}  # fmt: skip
# Real Google Cloud products that are NOT in mapping.yaml: naming one is a violation.
GCP_EXTRA = {
    "BigQuery", "Spanner", "Cloud Spanner", "Dataflow", "Cloud Functions", "GKE",
    "Google Kubernetes Engine", "Compute Engine", "App Engine", "Vertex AI", "Cloud Build",
    "Cloud Tasks", "Eventarc", "AlloyDB", "Cloud Armor", "Cloud Load Balancing", "Dataproc",
    "Cloud Composer", "Cloud Datastore", "Stackdriver", "Cloud Deploy", "Cloud Storage Transfer",
    "Datastream", "Cloud Endpoints", "Anthos", "Cloud VPN", "Cloud NAT",
}  # fmt: skip

FILE_RE = re.compile(
    r"(?<![\w/.-])((?:[\w.-]+/)*[\w.-]+\.(?:py|js|ts|tsx|jsx|tf|ya?ml|json|java|go|rb|sh|toml"
    r"|cfg|ini|properties|xml|gradle|txt|md|template)|(?:[\w.-]+/)*Dockerfile[\w.-]*)"
    r"(?::(\d+))?(?![\w/])"
)
# Capitalised single-word names like "Moment.js" are libraries, not files
LIB_NAME = re.compile(r"[A-Z][A-Za-z0-9]*\.js")
NOT_FILES = {"node.js", "next.js", "vue.js", "express.js", "nuxt.js"}
DOLLAR_RE = re.compile(r"\$\s?\d")


@dataclass(frozen=True)
class Violation:
    kind: str  # aws_service | gcp_resource | file | line | cost
    item: str
    detail: str


@dataclass
class GuardrailResult:
    violations: list[Violation]
    items_checked: int

    @property
    def ok(self) -> bool:
        return not self.violations

    def feedback(self) -> str:
        return "\n".join(f"- [{v.kind}] {v.item}: {v.detail}" for v in self.violations)


def _name_regex(names: set[str], prefixes: str = "") -> re.Pattern:
    alts = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    return re.compile(rf"(?<![\w/.-])(?:{prefixes})?({alts})(?![\w-])")


def _aws_surface() -> dict[str, str]:
    surface = {n: n for n in mapper.aws_services()}
    surface.update(AWS_ALIASES)
    surface.update({n: n for n in AWS_EXTRA})
    return surface


def _gcp_surface() -> dict[str, str]:
    surface = {n: n for n in mapper.gcp_resources()}
    surface.update(GCP_ALIASES)
    surface.update({n: n for n in GCP_EXTRA})
    return surface


def check_plan(plan: str, inventory: dict, repo_root: str | Path) -> GuardrailResult:
    repo_root = Path(repo_root)
    violations: list[Violation] = []
    checked = 0

    # 1. AWS services must appear in the detector inventory
    detected = {s["service"] for s in inventory["services"]}
    aws_surface = _aws_surface()
    seen: set[str] = set()
    for m in _name_regex(set(aws_surface), r"Amazon |AWS ").finditer(plan):
        canon = aws_surface[m.group(1)]
        if canon in AWS_EXEMPT or canon in seen:
            continue
        seen.add(canon)
        checked += 1
        if canon not in detected:
            violations.append(
                Violation("aws_service", canon, "named in the plan but not found in the repo")
            )

    # 2. GCP products must exist in mapping.yaml
    allowed = mapper.gcp_resources()
    gcp_surface = _gcp_surface()
    seen = set()
    for m in _name_regex(set(gcp_surface), r"Google ").finditer(plan):
        canon = gcp_surface[m.group(1)]
        if canon in seen:
            continue
        seen.add(canon)
        checked += 1
        if canon not in allowed:
            violations.append(
                Violation("gcp_resource", canon, "not in mapping.yaml, so it cannot be used")
            )

    # 3. cited files and lines must exist
    repo_files = set(repo_root.exists() and repo_reader.list_files(repo_root) or [])
    line_counts: dict[str, int] = {}
    cited: set[tuple[str, str | None]] = set()
    for m in FILE_RE.finditer(plan):
        path, line = m.group(1).removeprefix("./"), m.group(2)
        if path.lower() in NOT_FILES or LIB_NAME.fullmatch(path) or (path, line) in cited:
            continue
        cited.add((path, line))
        checked += 1
        if path not in repo_files:
            if path not in GENERATED_ARTIFACTS:
                violations.append(Violation("file", path, "cited file does not exist in the repo"))
            continue
        if line:
            if path not in line_counts:
                line_counts[path] = len(repo_reader.read_file(repo_root, path).splitlines())
            if not 1 <= int(line) <= line_counts[path]:
                violations.append(
                    Violation("line", f"{path}:{line}", f"file has {line_counts[path]} lines")
                )

    # 4. no unsourced dollar amounts
    if DOLLAR_RE.search(plan):
        violations.append(
            Violation("cost", "dollar amount", "cost figures need a source; use qualitative notes")
        )
    return GuardrailResult(violations, checked)
