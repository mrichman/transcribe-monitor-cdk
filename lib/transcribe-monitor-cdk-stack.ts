import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as path from 'path';

export class TranscribeMonitorCdkStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Define the Lambda function
    const monitoringFunction = new lambda.Function(
      this,
      'TranscribeConcurrencyMonitor',
      {
        runtime: lambda.Runtime.PYTHON_3_13,
        memorySize: 128,
        architecture: lambda.Architecture.ARM_64,
        handler: 'transcribe_concurrency_monitor.lambda_handler',
        code: lambda.Code.fromAsset(path.join(__dirname, '../lambda')),
        timeout: cdk.Duration.seconds(30),
        environment: {
          CLOUDWATCH_NAMESPACE: 'TranscribeMonitoring',
        },
        description:
          'Monitors Amazon Transcribe job concurrency and publishes metrics to CloudWatch',
      },
    );

    // Add IAM permissions for the Lambda function
    monitoringFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['transcribe:ListTranscriptionJobs'],
        resources: ['*'],
      }),
    );

    monitoringFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['cloudwatch:PutMetricData'],
        resources: ['*'],
      }),
    );

    // Create an EventBridge Rule to trigger the Lambda every minute
    const rule = new events.Rule(this, 'ScheduleRule', {
      schedule: events.Schedule.rate(cdk.Duration.minutes(1)),
      description:
        'Triggers the Transcribe concurrency monitoring Lambda function every minute',
    });

    // Add the Lambda function as a target of the rule
    rule.addTarget(new targets.LambdaFunction(monitoringFunction));

    // Create a CloudWatch Alarm for when concurrency approaches limit
    // Assuming a limit of 100 concurrent jobs (adjust as needed)
    const metric = new cloudwatch.Metric({
      namespace: 'TranscribeMonitoring',
      metricName: 'ConcurrentTranscribeJobs',
      dimensionsMap: {
        Service: 'Transcribe',
      },
      statistic: 'Maximum',
      period: cdk.Duration.minutes(1),
    });

    // Create an alarm that triggers at 80% of the concurrency limit
    // Adjust the threshold based on your actual service quota
    const alarm = new cloudwatch.Alarm(this, 'TranscribeConcurrencyAlarm', {
      metric: metric,
      threshold: 80, // 80% of assumed 100 job limit - adjust as needed
      evaluationPeriods: 1,
      datapointsToAlarm: 1,
      comparisonOperator:
        cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
      alarmDescription:
        'Alarm when Transcribe job concurrency exceeds 80% of the limit',
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    });

    // Output the Lambda function ARN and CloudWatch Alarm ARN
    new cdk.CfnOutput(this, 'MonitoringFunctionArn', {
      value: monitoringFunction.functionArn,
      description:
        'ARN of the Transcribe concurrency monitoring Lambda function',
    });

    new cdk.CfnOutput(this, 'ConcurrencyAlarmArn', {
      value: alarm.alarmArn,
      description: 'ARN of the CloudWatch Alarm for Transcribe concurrency',
    });
  }
}
