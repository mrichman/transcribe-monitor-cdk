import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


def lambda_handler(event, context):
    """
    Lambda function that:
    1. Calls ListCallAnalyticsJobs API to get all IN_PROGRESS jobs
    2. Counts the number of concurrent jobs
    3. Publishes this count as a CloudWatch metric
    """
    # Initialize AWS clients
    transcribe_client = boto3.client("transcribe")
    cloudwatch_client = boto3.client("cloudwatch")

    # Get all IN_PROGRESS call analytics jobs
    concurrent_jobs = 0
    next_token = None

    try:
        while True:
            # Prepare parameters for ListCallAnalyticsJobs
            params = {
                "Status": "IN_PROGRESS",
                "MaxResults": 100,  # Maximum allowed by the API
            }

            # Add NextToken if we have one from a previous call
            if next_token:
                params["NextToken"] = next_token

            # Call the API with proper exception handling
            try:
                response = transcribe_client.list_call_analytics_jobs(**params)

                # Count jobs from this response
                jobs_in_response = len(response.get("CallAnalyticsJobSummaries", []))
                concurrent_jobs += jobs_in_response

                # Check if there are more results
                next_token = response.get("NextToken")
                if not next_token:
                    break

            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                error_message = e.response["Error"]["Message"]

                if error_code == "BadRequestException":
                    print(
                        f"Bad request error: {error_message}. Check your input parameters."
                    )
                    break
                elif error_code == "LimitExceededException":
                    print(f"Service limit exceeded: {error_message}")
                    # Still report the jobs we've counted so far
                    break
                elif error_code == "InternalFailureException":
                    print(f"Internal AWS service error: {error_message}.")
                    # Still report the jobs we've counted so far
                    break
                elif error_code == "ConflictException":
                    print(f"Conflict error: {error_message}")
                    # Still report the jobs we've counted so far
                    break
                elif error_code == "ServiceUnavailableException":
                    print(f"Service unavailable: {error_message}.")
                    # Still report the jobs we've counted so far
                    break
                else:
                    # Re-raise unexpected errors
                    raise

        # Get namespace from environment variable or use default
        namespace = os.environ.get("CLOUDWATCH_NAMESPACE", "TranscribeMonitoring")

        # Publish metric to CloudWatch with exception handling
        try:
            cloudwatch_client.put_metric_data(
                Namespace=namespace,
                MetricData=[
                    {
                        "MetricName": "ConcurrentCallAnalyticsJobs",
                        "Value": concurrent_jobs,
                        "Unit": "Count",
                        "Timestamp": datetime.now(timezone.utc),
                        "Dimensions": [{"Name": "Service", "Value": "Transcribe"}],
                    }
                ],
            )

            print(
                f"Successfully published metric. Current concurrent jobs: {concurrent_jobs}"
            )

        except ClientError as e:
            print(f"Error publishing CloudWatch metric: {str(e)}")
            # We still want to return the job count even if metric publishing fails

        return {
            "statusCode": 200,
            "body": f"Current concurrent Transcribe call analytics jobs: {concurrent_jobs}",
        }

    except Exception as e:
        print(f"Error monitoring Transcribe concurrency: {str(e)}")
        raise e
