# Transcribe Concurrency Monitoring Solution

This CDK project deploys a solution for monitoring Amazon Transcribe job concurrency and creating CloudWatch alarms when approaching service quotas.

## Disclaimer

This Transcribe Concurrency Monitoring Solution is provided "as is" without warranties of any kind, either express or implied. Amazon Web Services (AWS) and its affiliates make no representations or warranties regarding the accuracy, reliability, or performance of this solution.

By using this solution, you acknowledge and agree that AWS shall not be liable for any direct, indirect, incidental, special, consequential, or exemplary damages, including but not limited to damages for loss of profits, goodwill, use, data, or other intangible losses resulting from the use or inability to use this solution.

The cost estimates provided are approximations only and actual costs may vary based on your specific usage patterns, AWS region, and other factors. You are solely responsible for monitoring and managing your AWS costs.

This solution is not an official AWS product and is not covered by AWS Support. For assistance with this solution, please refer to community resources or engage AWS Professional Services.

## Architecture

The solution consists of:

1. **Lambda Function**: Runs every minute to query the Transcribe service for `IN_PROGRESS` jobs
2. **CloudWatch Metric**: Custom metric that tracks the number of concurrent Transcribe jobs
3. **CloudWatch Alarm**: Alerts when job concurrency approaches the service quota limit

## Prerequisites

- AWS CLI configured with appropriate credentials
- Node.js 14.x or later
- AWS CDK v2 installed

## Deployment Instructions

1. Install dependencies:

   ```
   npm install
   ```

2. Build the TypeScript code:

   ```
   npm run build
   ```

3. Deploy the stack:
   ```
   npx cdk deploy
   ```

## Configuration

You can adjust the following parameters in the stack:

- **Alarm Threshold**: Currently set to 80% of the assumed limit (modify in `transcribe-monitor-cdk-stack.ts`)
- **CloudWatch Namespace**: Set via environment variable in the Lambda function (default: "TranscribeMonitoring")
- **Monitoring Frequency**: Currently set to run every minute (modify the EventBridge rule in the stack)

## Customization

To adjust the service quota threshold, modify the `threshold` parameter in the CloudWatch Alarm definition in `lib/transcribe-monitor-cdk-stack.ts`.

## Cost estimate

Lambda Costs:

- 1,440 invocations per day × 30 days = 43,200 invocations per month
- Assuming each execution takes ~500ms with 128MB memory:
  - Request pricing: $0.20 per 1M requests
    - 43,200 requests × $0.20/1M = $0.00864
  - Compute pricing: $0.0000166667 per GB-second
    - 43,200 invocations × 0.5 seconds × 0.128 GB × $0.0000166667 = $0.046
  - Lambda cost: $0.00864 + $0.046 = ~$0.05

CloudWatch Costs:

- Custom metrics: $0.30 per metric per month
- Alarm: $0.10 per alarm per month
- API requests (from Lambda to publish metrics):
  - 43,200 PutMetricData calls per month
  - $0.01 per 1,000 API calls
  - 43,200 × $0.01/1,000 = $0.432

Total Estimated Monthly Cost (Outside Free Tier):

- Lambda: $0.05
- CloudWatch metric: $0.30
- CloudWatch alarm: $0.10
- CloudWatch API calls: $0.43
- **Total: ~$0.88 per month**

## Cleanup

To remove all resources created by this stack:

```sh
npx cdk destroy
```
