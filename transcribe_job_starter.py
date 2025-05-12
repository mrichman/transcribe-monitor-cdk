#!/usr/bin/env python3
# pylint: disable=W0718

"""Generates load on the Transcribe service"""

import argparse
import sys
import time
import uuid
import random
import logging

import boto3


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="Start multiple Amazon Transcribe Call Analytics jobs"
    )
    parser.add_argument(
        "--input-bucket",
        required=True,
        help="S3 bucket containing the input audio files",
    )
    parser.add_argument(
        "--input-file", required=True, help="S3 key of the input audio file"
    )
    parser.add_argument(
        "--output-bucket",
        required=True,
        help="S3 bucket for storing transcription results",
    )
    parser.add_argument(
        "--role-arn", required=True, help="IAM role ARN for Transcribe to access S3"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10000,
        help="Number of jobs to start (default: 10000)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.1,
        help="Delay between job starts in seconds (default: 0.1)",
    )
    parser.add_argument(
        "--region", default="us-east-1", help="AWS region (default: us-east-1)"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Maximum number of retry attempts (default: 5)",
    )
    parser.add_argument(
        "--base-delay",
        type=float,
        default=1.0,
        help="Base delay for exponential backoff in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--max-delay",
        type=float,
        default=60.0,
        help="Maximum delay for exponential backoff in seconds (default: 60.0)",
    )

    return parser.parse_args()


def calculate_backoff_with_jitter(attempt, base_delay=1, max_delay=60):
    """
    Calculate exponential backoff with jitter

    Parameters:
    - attempt: The current retry attempt (0-based)
    - base_delay: The base delay in seconds
    - max_delay: The maximum delay in seconds

    Returns:
    - Backoff time with jitter in seconds
    """
    # Calculate exponential backoff: base_delay * 2^attempt
    backoff = base_delay * (2**attempt)

    # Apply a cap to the backoff
    backoff = min(backoff, max_delay)

    # Add jitter: random value between 0 and backoff
    jitter = random.uniform(0, backoff * 0.25)

    # Return backoff with jitter
    return backoff + jitter


def start_jobs(config):
    """Start multiple Transcribe jobs"""
    logger.info("Starting %d Transcribe Call Analytics jobs...", config.count)

    successful_jobs = 0
    failed_jobs = 0

    for i in range(config.count):
        success = start_job_with_retry(config)
        if success:
            successful_jobs += 1
        else:
            failed_jobs += 1

        # Log progress every 10 jobs or at the end
        if (i + 1) % 10 == 0 or i == config.count - 1:
            logger.info(
                "Progress: %d/%d jobs started (Success: %d, Failed: %d)",
                i + 1,
                config.count,
                successful_jobs,
                failed_jobs,
            )

        time.sleep(config.delay)

    logger.info(
        "Completed job submission. Successful: %d, Failed: %d",
        successful_jobs,
        failed_jobs,
    )


def start_job_with_retry(config, job_name=None):
    """
    Start a Transcribe job with retry logic

    Parameters:
    - config: Configuration object
    - job_name: Optional job name to use (for retries)

    Returns:
    - Boolean indicating success or failure
    """
    if not job_name:
        job_name = f"CallAnalyticsJob-{uuid.uuid4()}"

    transcribe_client = boto3.client("transcribe", region_name=config.region)

    for attempt in range(config.max_retries + 1):
        try:
            if attempt > 0:
                logger.info(
                    "Retry attempt %d/%d for job %s",
                    attempt,
                    config.max_retries,
                    job_name,
                )

            response = transcribe_client.start_call_analytics_job(
                CallAnalyticsJobName=job_name,
                Media={
                    "MediaFileUri": f"s3://{config.input_bucket}/{config.input_file}"
                },
                DataAccessRoleArn=config.role_arn,
                OutputLocation=f"s3://{config.output_bucket}/transcribe-results/",
                ChannelDefinitions=[
                    {"ChannelId": 0, "ParticipantRole": "AGENT"},
                    {"ChannelId": 1, "ParticipantRole": "CUSTOMER"},
                ],
            )

            status = response["CallAnalyticsJob"]["CallAnalyticsJobStatus"]
            logger.info(
                "Call Analytics Job started: %s -- Status: %s", job_name, status
            )
            return True

        except transcribe_client.exceptions.BadRequestException as e:
            logger.error("Bad request error: %s. Check your input parameters.", str(e))
            # Don't retry bad requests as they're unlikely to succeed
            return False

        except transcribe_client.exceptions.LimitExceededException as e:
            logger.warning("Service limit exceeded: %s", str(e))

            if attempt < config.max_retries:
                backoff = calculate_backoff_with_jitter(
                    attempt, config.base_delay, config.max_delay
                )
                logger.info("Backing off for %.2f seconds before retry", backoff)
                time.sleep(backoff)
            else:
                logger.error("Max retries reached for limit exceeded error")
                return False

        except transcribe_client.exceptions.ConflictException as e:
            logger.warning(
                "Conflict error: %s. A job with name %s may already exist.",
                str(e),
                job_name,
            )

            # Generate a new job name and try again immediately
            new_job_name = f"CallAnalyticsJob-{uuid.uuid4()}"
            logger.info("Retrying with new job name: %s", new_job_name)

            # Instead of recursion, we'll use the new job name in the next iteration
            job_name = new_job_name
            # Don't count this as a retry attempt since it's a name conflict
            continue

        except (
            transcribe_client.exceptions.InternalFailureException,
            transcribe_client.exceptions.ServiceUnavailableException,
        ) as e:
            error_type = (
                "Internal AWS service error"
                if isinstance(e, transcribe_client.exceptions.InternalFailureException)
                else "Service unavailable"
            )

            logger.warning("%s: %s", error_type, str(e))

            if attempt < config.max_retries:
                backoff = calculate_backoff_with_jitter(
                    attempt, config.base_delay, config.max_delay
                )
                logger.info("Backing off for %.2f seconds before retry", backoff)
                time.sleep(backoff)
            else:
                logger.error("Max retries reached for %s", error_type.lower())
                return False

        except Exception as e:
            logger.error("Unexpected error starting Call Analytics Job: %s", str(e))

            if attempt < config.max_retries:
                backoff = calculate_backoff_with_jitter(
                    attempt, config.base_delay, config.max_delay
                )
                logger.info("Backing off for %.2f seconds before retry", backoff)
                time.sleep(backoff)
            else:
                logger.error("Max retries reached for unexpected error")
                return False

    # If we get here, all retries failed
    return False


if __name__ == "__main__":
    try:
        args = parse_arguments()
        start_jobs(args)
    except KeyboardInterrupt:
        logger.info("Process interrupted by user. Exiting gracefully.")
        sys.exit(0)
    except Exception as e:
        logger.error("Unhandled exception: %s", str(e), exc_info=True)
        sys.exit(1)
