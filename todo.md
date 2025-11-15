# TODO: Bedrock vs Anthropic 1P API Latency Benchmark

## Section 10: Cross-Region Inference Tracking ✅
**Goal**: Track Bedrock cross-region inference requests to understand performance impact

### Background
Bedrock uses Cross Region Inference (https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html) which may route requests to other regions at request level, potentially impacting latency.

### Tasks
- [x] Update CSV schema to add columns:
  - `total_bedrock_requests` - Total number of Bedrock API calls for this task
  - `cross_region_requests` - Number of requests that were cross-region
  - `request_ids` - Comma-separated list of request IDs
- [x] Modify Bedrock executor to capture request IDs:
  - Extract request ID from Bedrock response metadata
  - Store in results data structure
- [x] Create CloudTrail query script:
  - Input: List of Bedrock request IDs
  - Query CloudTrail logs for InvokeModel events
  - Parse `requestParameters.inferenceProfileArn` or region info
  - Determine if request was cross-region
  - Output: Mapping of request_id → is_cross_region
- [x] Update benchmark runner to:
  - Collect all request IDs during benchmark run
  - After benchmark completes, query CloudTrail
  - Update CSV with cross-region information
- [x] Update analysis script to:
  - Calculate % of cross-region requests
  - Compare latency: cross-region vs same-region
  - Add cross-region stats to comparison report
- [x] Document CloudTrail setup requirements:
  - Required IAM permissions
  - CloudTrail trail configuration
  - Query delay considerations (CloudTrail lag)

### Implementation Notes
- CloudTrail query can be disabled with `--no-cloudtrail` flag for development
- Request IDs are captured from `ResponseMetadata.RequestId` in Bedrock responses
- Cross-region detection checks inference profile ARN, event region, and resource ARNs
- Analysis separates pure same-region vs pure cross-region requests for cleaner comparison
- See `benchmark/CLOUDTRAIL_SETUP.md` for detailed setup instructions
