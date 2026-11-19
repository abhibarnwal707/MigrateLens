# Evaluation sample apps

Six real public repositories (all from the `aws-samples` GitHub organisation) plus one
**synthetic** fixture. Real apps are vendored at the pinned commit with `.git`, images and PDFs
removed; every other file is byte-identical to upstream (checked with `cmp`), with ONE exception: in
`twilio-apigw/README.md` (line 185, an example JSON payload) a Twilio account identifier was
replaced by `ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` because GitHub secret scanning blocks pushing it.
No code or evaluated file was changed. Licence files are
kept in each directory. Nothing in these apps is ever executed.

| Directory | Upstream | Pinned commit | Licence | Language / style |
|---|---|---|---|---|
| `sqs-max-concurrency` | aws-samples/aws-lambda-amazon-sqs-max-concurrency | `98ee964d8775c7348dbf562f30f62903129e28af` | MIT-0 | Python, SAM |
| `sam-messaging` | aws-samples/aws-sam-messaging-services-integration | `1fd81b29994c2624d1914c1a7a564a78a9db2905` | MIT-0 | Node.js, SAM |
| `twilio-apigw` | aws-samples/lambda-apigateway-twilio-tutorial | `d2c990dbe5ca870e50243ae50e208dfd1889ddef` | Apache-2.0 | Python, SAM |
| `sns-email-china` | aws-samples/sample-sns-email-notification-china-region | `0a1f4c4666973978e84549ab373be6bce62232e5` | MIT-0 | Python, CloudFormation |
| `priority-mailer-ses` | aws-samples/sample-priority-mailer-cdk-solution-using-amazon-ses | `da57aee4ea94f25f85d97b1199a19b459cc6682f` | MIT-0 | Python, CDK |
| `iot-sns-sqs-ddb` | aws-samples/iot-lambda-sns-sqs-lambda-dynamodb | `9e262b2f695dde7c9fa135500564af11fd35d295` | MIT-0 | Node.js, SAM |
| `java-synthetic-orders` | **synthetic**, written for this project | n/a | n/a | Java (AWS SDK v2) |

A seventh candidate, `aws-lambda-sqs-cost-estimator`, was rejected: it only mentions SQS and
Lambda in chart labels and never calls AWS, so it has no services to detect.

## Honest notes

- **Small n.** 7 apps; every confidence interval in the results is wide.
- **Java is synthetic.** No suitable small public Java sample was found, so the Java fixture was
  written by the project author. It is a weak test (the author knew what the detector looks for).
- **Not independent for the detector.** After a first detector run on these apps, SAM
  (`AWS::Serverless::*`) and CDK (`aws_cdk` imports) support was added because those formats
  caused every miss. Both runs are kept: `eval/results/detector_before_sam_cdk.json` and
  `eval/results/detector_after_sam_cdk.json`. The "after" scores are partly tuned on these apps.
- **Ground truth** (`eval/truth/*.json`) is a first draft with `"human_reviewed": false` until the
  project owner confirms each file. Truth separates `services_in_scope` (covered by
  `mapping.yaml`) from `services_out_of_scope` (for example EC2 and IoT Core), which no run
  can report; only in-scope services are scored.
