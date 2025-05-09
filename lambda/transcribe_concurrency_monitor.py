import boto3
import os
from datetime import datetime


def lambda_handler(event, context):
    """
    Lambda function that:
    1. Calls ListTranscriptionJobs API to get all IN_PROGRESS jobs
    2. Counts the number of concurrent jobs
    3. Publishes this count as a CloudWatch metric
    """
    # Initialize AWS clients
    transcribe_client = boto3.client("transcribe")
    cloudwatch_client = boto3.client("cloudwatch")

    # Get all IN_PROGRESS transcription jobs
    concurrent_jobs = 0
    next_token = None

    try:
        while True:
            # Prepare parameters for ListTranscriptionJobs
            params = {
                "Status": "IN_PROGRESS",
                "MaxResults": 100,  # Maximum allowed by the API
            }

            # Add NextToken if we have one from a previous call
            if next_token:
                params["NextToken"] = next_token

            # Call the API
            response = transcribe_client.list_transcription_jobs(**params)

            # Count jobs from this response
            jobs_in_response = len(response.get("TranscriptionJobSummaries", []))
            concurrent_jobs += jobs_in_response

            # Check if there are more results
            next_token = response.get("NextToken")
            if not next_token:
                break

        # Get namespace from environment variable or use default
        namespace = os.environ.get("CLOUDWATCH_NAMESPACE", "TranscribeMonitoring")

        # Publish metric to CloudWatch
        cloudwatch_client.put_metric_data(
            Namespace=namespace,
            MetricData=[
                {
                    "MetricName": "ConcurrentTranscribeJobs",
                    "Value": concurrent_jobs,
                    "Unit": "Count",
                    "Timestamp": datetime.utcnow(),
                    "Dimensions": [{"Name": "Service", "Value": "Transcribe"}],
                }
            ],
        )

        print(
            f"Successfully published metric. Current concurrent jobs: {concurrent_jobs}"
        )
        return {
            "statusCode": 200,
            "body": f"Current concurrent Transcribe jobs: {concurrent_jobs}",
        }

    except Exception as e:
        print(f"Error monitoring Transcribe concurrency: {str(e)}")
        raise e
