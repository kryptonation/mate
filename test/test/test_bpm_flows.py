import os
import openpyxl
import pytest
import pandas as pd 
import json
from datetime import datetime
from fastapi.testclient import TestClient
from app.utils.logger import get_logger
from app.core.db import get_db, Base
from app.main import bat_app as fast_api_app
from app.users import schemas
from app.users.models import User
from app.bpm import utils
from app.bpm_flows.update_driver_address import flows
from app.bpm_flows.new_vehicle import flows
from app.bpm_flows.newdriver import flows
from app.bpm_flows.updatedmv import flows
from app.bpm_flows.updatetlc import flows
from app.bpm_flows.newmed import flows
from app.bpm_flows.update_driver_payee import flows
from app.bpm_flows.renmed import flows
from app.bpm_flows.stomed import flows
from app.bpm_flows.retrieve_medallion import flows
from app.bpm_flows.allocate_medallion_vehicle import flows
from app.bpm_flows.update_medallion_address import flows
from app.bpm_flows.update_medallion_payee import flows
from app.bpm_flows.driverlease import flows
from app.core.db import step_registry
from app.bat import utils as bat_utils  
from starlette.responses import Response
from test import utils
from app.bpm_flows.newdriver import test_utils
from test.test_db import db_session, client, test_step_registry, mock_redis
from test.config import GENERIC_FLOW_NAMES, FLOW_CONFIG, document_to_upload_path
from test.utils import TestingFlows, update_excel_outcome_flows, compare_response, deep_compare


# Logging setup
logger = get_logger(__name__)


@pytest.fixture
def case_data(flow_data):
    flow_name, test_case = flow_data
    case_type = FLOW_CONFIG[flow_name]["sheet_name"]
    
    return {
        "case_type": case_type,
    }

# Load the Test Case table from Excel
def load_test_cases(file_path, sheet):

    df = pd.read_excel(file_path, sheet_name= sheet, header=3)
    return df.to_dict(orient="records")  


def read_payloads_from_sheet(file_path , sheet_name):

    df = pd.read_excel(file_path, sheet_name=sheet_name, header=3)
    payloads = []
    for _, row in df.iterrows():
        step_id, operation, process_payload, expected_status_code, expected_fetch_response, is_seed_step = row

        # Convert NaN values to proper types
        process_payload = {} if pd.isna(process_payload) else json.loads(process_payload)
        expected_fetch_response = {} if pd.isna(expected_fetch_response) else json.loads(expected_fetch_response)

        payloads.append({
            "step_id": step_id,
            "operation": operation,
            "process_payload": process_payload,
            "expected_status_code": expected_status_code,
            "expected_fetch_response": expected_fetch_response,
            "is_seed_step": is_seed_step
        })
    return payloads


def get_flow_test_cases(flow_name: str) -> list:
    """
    Given a flow name, load the test cases from the flow’s configured Excel file and main sheet.
    Each test case dictionary is augmented with:
      - "excel_file": the absolute path of the workbook.
      - "flow_name": the name of the flow.
    """
    flow_conf = FLOW_CONFIG[flow_name]
    file_path = os.path.abspath(flow_conf["excel_file"])
    main_sheet = flow_conf["sheet_name"]
    test_cases = load_test_cases(file_path, main_sheet)
    for tc in test_cases:
        tc["excel_file"] = file_path
        tc["flow_name"] = flow_name
    return test_cases



def run_test(client: TestClient, db_session, test_case, case_data):
    client.cookies.clear() 
    test_case_id = test_case["TestCaseID"]
    step_id = test_case["Step id"]  # Step being tested
    user_name = test_case["User"]
    payload_sheet_name = test_case["PayloadSheetName"]
    skip_test = test_case["Skip"]


    # Skip test case if Skip == "Y"
    if skip_test == "Y":
        logger.info(f"Skipping test case {test_case_id} as Skip is set to 'Y'.")
        pytest.skip(f"TestCaseID {test_case_id} is marked to be skipped.")

    if pd.isna(payload_sheet_name) or str(payload_sheet_name).strip() == "":
        pytest.skip()

    logger.info("Running test case %s for Step ID: %s (Flow: %s)",
                test_case_id, step_id, test_case["flow_name"])
    
    # Read Payloads
    file_path = test_case["excel_file"]
    payloads = read_payloads_from_sheet(file_path, payload_sheet_name)

    logger.info(f"Loaded payloads: {payloads}")

    flow = TestingFlows(client, db_session)

    # Fetch login data
    user = flow.db_session.query(User).filter(User.first_name == user_name).first()
    if not user:
        raise ValueError(f"No user found with first name {user_name}")

    login_data = schemas.LoginRequest(email_id=user.email_address, password=user.password)
    logger.info(f"Fetched login data: {login_data}")

    flow.login(login_data)
    flow.create_case(case_data)
    
    try:
        for step in payloads:
            is_seed_step = step["is_seed_step"]
            step_id = step["step_id"]
            operation = step["operation"]
            payload = step["process_payload"]
            expected_status_code = step["expected_status_code"]
            expected_fetch_response = step["expected_fetch_response"]
            logger.info(f"Processing actual test step {step_id}.")
            if is_seed_step == "N":
                step = "Test"
            else:
                step = "Seed"
            # If expected_response is empty, None, NaN, or the string "None", set it to an empty dictionary
            if not expected_fetch_response or expected_fetch_response in ["None", "nan"] or (isinstance(expected_fetch_response, float) and pd.isna(expected_fetch_response)):
                expected_fetch_response = {}

            # Define key for checking in test_step_registry
            registry_key = f"{step_id}-{operation}"

            # Check if a function exists in `test_step_registry` for the specific step_id and operation
            if registry_key in test_step_registry:
                logger.info(f"Calling registered function for step {step_id} and operation {operation}.")
                payload = test_step_registry[registry_key]["function"](flow.db_session, payload, flow.case_no)
                logger.info(f"{payload}")
            if operation == "fetch":
                response = flow.fetch_step_data(step_id, payload)
            elif operation == "process":
                response = flow.process_step(step_id, payload)
                flow.move_step()
            elif operation == "upload-doc":
                response = flow.upload_document(step_id, payload, document_to_upload_path)

            response_json = response.json()
            logger.info(f"{response_json}")
            assert response.status_code == expected_status_code, (
                f"{step} step {step_id} failed. Expected status code {expected_status_code}, but got {response.status_code}."
                f"Response Body: {response.json()}"
            )
            logger.info(f"Expected response: {expected_fetch_response}")
            logger.info(f"Actual response: {response_json}")
            if expected_fetch_response == {}:
                outcome_text = "Pass"
            else:
                outcome_text = compare_response(expected_fetch_response, response_json)
            assert outcome_text == "Pass", outcome_text
    except AssertionError as e:
        logger.error(f"Test case {test_case_id} failed with error: {e}")
        outcome_text =f"Fail - {str(e)}"
        update_excel_outcome_flows(file_path, case_data["case_type"], test_case_id, outcome_text)
        raise
    finally:
        logger.info(f"Test case {test_case_id} completed successfully.")
        update_excel_outcome_flows(file_path, case_data["case_type"], test_case_id, outcome_text)

def pytest_generate_tests(metafunc):
    """
    Dynamically generates tests.
    
    For each flow in GENERIC_FLOW_NAMES, load its test cases and generate a test parameter
    as a tuple (flow_name, test_case). The id for each test is set to "<flow_name>_<TestCaseID>".
    """
    if "flow_data" in metafunc.fixturenames:
        all_params = []
        all_ids = []
        for flow_name in GENERIC_FLOW_NAMES:
            test_cases = get_flow_test_cases(flow_name)
            for tc in test_cases:
                all_params.append((flow_name, tc))
                test_id = f"{flow_name}_{tc.get('TestCaseID', 'Unknown')}"
                all_ids.append(test_id)
        metafunc.parametrize("flow_data", all_params, ids=all_ids)



@pytest.mark.usefixtures("case_data")
def test_flow_cases(flow_data, client: TestClient, db_session, case_data):
    """
    A single test function that is parameterized with a tuple (flow_name, test_case)
    for each generated test. It runs the test case using the shared _run_test_case helper.
    """
    flow_name, test_case = flow_data
    # You can adjust or supply different case data based on the flow if needed.
    run_test(client, db_session,test_case, case_data)