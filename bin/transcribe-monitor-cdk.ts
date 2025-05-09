#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { TranscribeMonitorCdkStack } from '../lib/transcribe-monitor-cdk-stack';

const app = new cdk.App();
new TranscribeMonitorCdkStack(app, 'TranscribeMonitorCdkStack', {
  /* This stack uses the AWS account and region from the current CLI configuration */
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION,
  },

  /* Stack description */
  description:
    'Monitors Amazon Transcribe job concurrency and creates CloudWatch metrics and alarms',
});
