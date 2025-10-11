import os
import openpyxl
import pytest
import pandas as pd
import json
from datetime import datetime
from fastapi.testclient import TestClient
from app.utils.logger import get_logger
from app.users import schemas
from app.users.models import User
from test.utils import TestingSearchDriver, TestingMedallionOwnerListing, TestingListMedallions, TestingDocumentUpload, TestingDocumentDelete, TestingDeactivateMedallions , TestingVehicleEntitySearch ,TestingManageVehicleList
from test.config import API_CONFIG, GENERIC_API_NAMES
from app.core.db import get_db, Base
from app.main import bat_app as fast_api_app
from app.bat import utils as bat_utils  
from starlette.responses import Response
from test import utils
from test.utils import update_excel_outcome, compare_response
from test.test_db import db_session, client, mock_redis

# Logging setup
logger = get_logger(__name__)

# Function to load test cases dynamically for each API file
def load_test_cases(file_path):
    """
    Loads test cases from the specified Excel file.
    Assumes the first sheet is used, and the headers are on the first row.
    """
    df = pd.read_excel(file_path, header=3)  # No need for sheet_name since we are using the first sheet
    return df.to_dict(orient="records")  # Convert to a list of dictionaries


# This function prepares the test case data dynamically
def get_test_case_data(api_name):
    """
    Loads the test cases based on api_name from the API_CONFIG.
    """
    excel_file = API_CONFIG[api_name]["excel_file"]
    test_cases = load_test_cases(excel_file)
    return [(api_name, test_case) for test_case in test_cases]

# A single test function to run for all workbooks dynamically
@pytest.mark.parametrize("api_name, test_case", [item for api_name in GENERIC_API_NAMES for item in get_test_case_data(api_name)])  # Parametrize test cases for each API
def test_api_flow(client: TestClient, db_session, api_name, test_case):
    """
    A generic test function that works for both test_medallion_owner_listing and test_search_drivers.
    This function runs the test dynamically for each Excel file mentioned in GENERIC_API_NAMES.
    """
    client.cookies.clear() 
    test_case_id = test_case["TestCaseID"]
    user_name = test_case["User"]
    search_data = test_case["SearchData"]
    skip_test = test_case["Skip"]
    expected_status_code = test_case["ExpectedStatusCode"]
    expected_response = test_case.get("ExpectedResponse", "{}")

    # If SearchData is an empty string, None, or NaN, set it to an empty dictionary
    if not search_data or search_data in ["None", "nan"] or (isinstance(search_data, float) and pd.isna(search_data)):
        search_data = {}

    # If expected_response is empty, None, NaN, or the string "None", set it to an empty dictionary
    if not expected_response or expected_response in ["None", "nan"] or (isinstance(expected_response, float) and pd.isna(expected_response)):
        expected_response = {}

    # Skip test case if Skip == "Y"
    if skip_test == "Y":
        logger.info(f"Skipping test case {test_case_id} as Skip is set to 'Y'.")
        pytest.skip(f"Skipping test case {test_case_id} as Skip is set to 'Y'.")

    if isinstance(search_data, str):
        try:
            search_data = json.loads(search_data)  # Convert string to dictionary
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON search data: {search_data}")
            outcome_text = f"Fail - Invalid JSON format in SearchData: {search_data}"
            update_excel_outcome(API_CONFIG[api_name]["excel_file"], test_case_id, outcome_text)
            pytest.fail(f"Invalid JSON format in SearchData for test case {test_case_id}")

    if isinstance(expected_response, str):
        try:
            expected_response = json.loads(expected_response.replace("'", '"'))  # Fix single quotes
        except json.JSONDecodeError:
            logger.error(f"Failed to decode expected response JSON: {expected_response}")
            outcome_text = f"Fail - Invalid JSON format in ExpectedResponse: {expected_response}"
            update_excel_outcome(API_CONFIG[api_name]["excel_file"], test_case_id, outcome_text)
            pytest.fail(f"Invalid JSON format in ExpectedResponse for test case {test_case_id}")


    logger.info(f"Running test case {test_case_id} for {api_name}")
    logger.info(f"Test search data {search_data}")

    # Dynamically select the appropriate testing class and method
    class_name = API_CONFIG[api_name]["class"]
    method_name = API_CONFIG[api_name]["method"]
    test_class = globals().get(class_name)  # Retrieve the class dynamically from globals()

    if not test_class:
        raise ValueError(f"Unknown class {class_name} in API_CONFIG for {api_name}")

    # Instantiate the test class
    test_instance = test_class(client, db_session)

    # Fetch login data
    user = test_instance.db_session.query(User).filter(User.first_name == user_name).first()
    if not user:
        raise ValueError(f"No user found with first name {user_name}")
    
    login_data = schemas.LoginRequest(email_id=user.email_address, password=user.password)
    logger.info(f"Fetched login data: {login_data}")
    
    test_instance.login(login_data)

    # Dynamically call the method based on the class instance
    if hasattr(test_instance, method_name):
        method = getattr(test_instance, method_name)
        response = method(search_data)
    else:
        raise ValueError(f"No method {method_name} found for class {class_name}")

    response_json = response.json()

    try:
        assert response.status_code == expected_status_code, (
                    f"Test {test_case_id} failed. Expected status code {expected_status_code}, but got {response.status_code}."
                    f"Response Body: {response.json()}"
                )
        if expected_response == {}:
            outcome_text = "Pass but did not compare responses"
            return
        outcome_text = compare_response(expected_response, response_json)
        logger.info(f"Expected response: {expected_response}")
        logger.info(f"Actual response: {response_json}")
        assert outcome_text == "Pass", outcome_text
    except AssertionError as e:
        logger.error(f"Test case {test_case_id} failed with error: {e}")
        outcome_text = f"Fail - {str(e)}"
        update_excel_outcome(API_CONFIG[api_name]["excel_file"], test_case_id, outcome_text)
        raise
    finally:
        logger.info(f"Test case {test_case_id} completed successfully.")
        update_excel_outcome(API_CONFIG[api_name]["excel_file"], test_case_id, outcome_text)
