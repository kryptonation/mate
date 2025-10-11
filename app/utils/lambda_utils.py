### app/utils/lambda_utils.py

import json

import boto3
from botocore.exceptions import ClientError

from app.utils.logger import get_logger
from app.core.config import settings

logger = get_logger(__name__)

def invoke_lambda_function(function_name: str, payload: dict) -> dict:
    """
    Invokes an AWS Lambda function and returns the response.

    Args:
        function_name (str): Name or ARN of the Lambda function to invoke
        payload (dict): Data to be passed to the Lambda function

    Returns:
        dict: Response from the Lambda function

    Raises:
        ValueError: If the Lambda invocation fails or returns an error
    """
    try:
        lambda_client = boto3.client(
            'lambda',
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

        logger.info("Invoking Lambda function: %s with payload: %s", function_name, payload)
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )

        # Check if the invocation was successful
        if response['StatusCode'] != 200:
            error_msg = f"Lambda invocation failed with status code: {response['StatusCode']}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Parse the response payload
        response_payload = json.loads(response['Payload'].read())

        # Check if Lambda function returned an error
        if 'errorMessage' in response_payload:
            error_msg = f"Lambda function returned error: {response_payload['errorMessage']}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        return response_payload

    except ClientError as e:
        error_msg = f"AWS Lambda ClientError: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg) from e
    except Exception as e:
        error_msg = f"Error invoking Lambda function: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg) from e