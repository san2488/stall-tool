# CloudTrail Setup for Cross-Region Inference Tracking

This document describes how to set up CloudTrail to enable cross-region inference tracking for Bedrock benchmarks.

## Overview

The benchmark uses CloudTrail to determine if Bedrock API requests were routed to other regions via Cross Region Inference (CRI). This requires:

1. A CloudTrail trail that logs Bedrock API calls
2. IAM permissions to query CloudTrail
3. Understanding of CloudTrail event delivery delays

## CloudTrail Trail Configuration

### Option 1: Use Existing Trail

If you already have a CloudTrail trail that logs management events in the region where you're running benchmarks (e.g., `us-east-1`), you can use it. Verify it's logging Bedrock events:

```bash
aws cloudtrail get-trail-status --name <trail-name> --region us-east-1
```

### Option 2: Create New Trail

Create a trail specifically for Bedrock monitoring:

```bash
# Create S3 bucket for CloudTrail logs
aws s3 mb s3://my-bedrock-cloudtrail-logs --region us-east-1

# Create trail
aws cloudtrail create-trail \
  --name bedrock-monitoring \
  --s3-bucket-name my-bedrock-cloudtrail-logs \
  --region us-east-1

# Start logging
aws cloudtrail start-logging --name bedrock-monitoring --region us-east-1
```

### Event Selectors

Ensure the trail captures Bedrock API calls. CloudTrail logs management events by default, which includes Bedrock `InvokeModel` calls.

To verify:

```bash
aws cloudtrail get-event-selectors --trail-name bedrock-monitoring --region us-east-1
```

Expected output should include:
```json
{
  "EventSelectors": [
    {
      "ReadWriteType": "All",
      "IncludeManagementEvents": true
    }
  ]
}
```

## IAM Permissions

The IAM user or role running the benchmark needs these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudtrail:LookupEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

### Minimal Policy Example

Create a policy named `BedrockBenchmarkCloudTrailAccess`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudTrailQuery",
      "Effect": "Allow",
      "Action": [
        "cloudtrail:LookupEvents"
      ],
      "Resource": "*"
    },
    {
      "Sid": "BedrockInvoke",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "*"
    }
  ]
}
```

Attach to your IAM user/role:

```bash
aws iam attach-user-policy \
  --user-name <your-username> \
  --policy-arn arn:aws:iam::<account-id>:policy/BedrockBenchmarkCloudTrailAccess
```

## CloudTrail Event Delivery Delay

**Important**: CloudTrail events are not available immediately. There's typically a 5-15 minute delay between when an API call is made and when it appears in CloudTrail.

### Implications for Benchmarking

1. **Run benchmarks first, query later**: The benchmark script automatically waits to query CloudTrail after all tasks complete
2. **Time window**: The query uses a 15-minute lookback window by default
3. **Missing events**: If events aren't found, they may not have been delivered yet

### Handling Delays

If you see warnings about missing request IDs:

```
Warning: Request ID abc-123 not found in CloudTrail
```

Options:
1. Wait a few minutes and re-run the CloudTrail query manually:
   ```bash
   python benchmark/query_cloudtrail.py \
     --request-ids abc-123 def-456 \
     --start-time "2024-01-15T10:00:00" \
     --region us-east-1
   ```

2. Increase the time window in the query (modify `query_cloudtrail.py`)

3. Skip CloudTrail querying during development:
   ```bash
   python benchmark/benchmark_bedrock.py --no-cloudtrail
   ```

## Verifying Setup

Test your CloudTrail setup:

```bash
# Make a test Bedrock call
aws bedrock-runtime invoke-model \
  --model-id anthropic.claude-3-sonnet-20240229-v1:0 \
  --body '{"prompt":"Hello","max_tokens":10}' \
  --region us-east-1 \
  output.json

# Wait 5-10 minutes, then query CloudTrail
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=EventName,AttributeValue=InvokeModel \
  --max-results 5 \
  --region us-east-1
```

You should see recent `InvokeModel` events in the output.

## Cross-Region Inference Detection

The benchmark determines if a request was cross-region by examining:

1. **Inference Profile ARN**: If present in `requestParameters.inferenceProfileArn`, extract the region
2. **Event Region**: Compare `awsRegion` field to the home region
3. **Resource ARNs**: Check regions in resource ARNs

Example CloudTrail event showing cross-region inference:

```json
{
  "eventName": "InvokeModel",
  "awsRegion": "us-west-2",
  "requestParameters": {
    "inferenceProfileArn": "arn:aws:bedrock:us-west-2:...",
    "modelId": "anthropic.claude-3-sonnet-20240229-v1:0"
  },
  "responseElements": {
    "x-amzn-requestid": "abc-123-def-456"
  }
}
```

If the benchmark runs in `us-east-1` but the event shows `us-west-2`, it's marked as cross-region.

## Troubleshooting

### No Events Found

**Problem**: CloudTrail query returns no events

**Solutions**:
1. Verify trail is active: `aws cloudtrail get-trail-status --name <trail-name>`
2. Check trail is in the correct region
3. Verify IAM permissions
4. Wait longer for event delivery (up to 15 minutes)

### Permission Denied

**Problem**: `AccessDeniedException` when querying CloudTrail

**Solution**: Verify IAM permissions include `cloudtrail:LookupEvents`

### High Costs

**Problem**: Concerned about CloudTrail costs

**Notes**:
- CloudTrail management events are free for the first trail
- `LookupEvents` API calls are free
- S3 storage costs apply for log files (minimal for benchmarking)

## Cost Optimization

For development/testing:
- Use `--no-cloudtrail` flag to skip queries
- Delete old CloudTrail logs from S3 regularly
- Use a single trail for all AWS services

## References

- [AWS CloudTrail Documentation](https://docs.aws.amazon.com/cloudtrail/)
- [Bedrock Cross Region Inference](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html)
- [CloudTrail LookupEvents API](https://docs.aws.amazon.com/awscloudtrail/latest/APIReference/API_LookupEvents.html)
