import os

TEST_DATABASE_FILE = os.getenv("TEST_DATABASE_FILE", "testcase.db")
TEST_DATABASE_URL = f"sqlite:///{TEST_DATABASE_FILE}"
BPM_SEED_DATA = os.getenv("BAT_BPM_SEED_DATA", "static/seed_data/bat-bpm-seed-data.xlsx")
APP_SEED_DATA = os.getenv("BAT_APP_SEED_DATA", "static/seed_data/bat-app-seed-data.xlsx")
document_to_upload_path = "static/test_documents/test_document.pdf"

# Mapping of flow names to their Excel file and sheet name.
FLOW_CONFIG = {
        "new_driver": {
        "excel_file": "static/test_data/test_driver_data.xlsx",
        "sheet_name": "NEWDR",
    },
    "update_driver_address": {
        "excel_file": "static/test_data/test_manage_driver_data.xlsx",
        "sheet_name": "DRVUPDADR",
    },
     "update_dmv": {
        "excel_file": "static/test_data/test_manage_driver_dmv_data.xlsx",
        "sheet_name": "UPDMVL",
    },
    "update_tlc": {
        "excel_file": "static/test_data/test_manage_driver_tlc_data.xlsx",
        "sheet_name": "UPDTLC",
    },
    "update_driver_payee": {
        "excel_file": "static/test_data/test_update_driver_payee_data.xlsx",
        "sheet_name": "DRVUPDPAY",
    },
        "new_medallion": {
        "excel_file": "static/test_data/test_new_medallion_data.xlsx",
        "sheet_name": "NEWMED",
    },
    "renew_medallion": {
        "excel_file": "static/test_data/test_renew_medallion_data.xlsx",
        "sheet_name": "RENMED",
    },
    "store_medallion": {
        "excel_file": "static/test_data/test_store_medallion_data.xlsx",
        "sheet_name": "STOMED",
    },
    "retrieve_medallion": {
        "excel_file": "static/test_data/test_retrieve_medallion_data.xlsx",
        "sheet_name": "RETMED",
    },
    "allocate_medallion": {
        "excel_file": "static/test_data/test_allocate_medallion_data.xlsx",
        "sheet_name": "ALLMED",
    },
    "update_medallion_address": {
        "excel_file": "static/test_data/test_update_address_medallion_data.xlsx",
        "sheet_name": "UPDADRMED",
    },
    "update_medallion_payee": {
        "excel_file": "static/test_data/test_update_payee_medallion_data.xlsx",
        "sheet_name": "UPDPAY",
    },
    "driver_lease": {
        "excel_file": "static/test_data/test_driver_lease_data.xlsx",
        "sheet_name": "DRVLEA",
    },
    "new_vehicle":{
       "excel_file":"static/test_data/test_new_vehicle_flow.xlsx",
       "sheet_name":"NEWVR"
    }
    ,

}

# A list of flows you want to run with the generic parser.
#GENERIC_FLOW_NAMES = list(FLOW_CONFIG.keys())
GENERIC_FLOW_NAMES = ["new_vehicle"]


API_CONFIG = {
    "test_medallion_owner_listing" :{
       "excel_file": "static/test_data/test_medallion_owner_listing_v2.xlsx",
        "class": "TestingMedallionOwnerListing",
        "method": "search_medallion_owner",
    },
    "test_search_drivers" :{
        "excel_file": "static/test_data/test_search_drivers.xlsx",
        "class": "TestingSearchDriver",
        "method": "search_driver",
    },
    "test_list_medallions" :{
        "excel_file": "static/test_data/test_list_medallions.xlsx",
        "class": "TestingListMedallions",
        "method": "search_medallion",
    },
    "test_upload_document" :{
        "excel_file": "static/test_data/test_upload_document.xlsx",
        "class": "TestingDocumentUpload",
        "method": "upload_document",
    },
    "test_delete_document" :{
        "excel_file": "static/test_data/test_delete_document.xlsx",
        "class": "TestingDocumentDelete",
        "method": "delete_document",
    },
    "test_deactivate_medallions" :{
        "excel_file": "static/test_data/test_deactivate_medallions.xlsx",
        "class": "TestingDeactivateMedallions",
        "method": "deactivate_medallions",
    },
    "test_vehicle_entity_search":{
        "excel_file":"static/test_data/test_vehicle_entity_search.xlsx",
        "class":"TestingVehicleEntitySearch",
        "method":"search_vehicle_entity"
    },
    "test_manage_vehicle_list":{
        "excel_file":"static/test_data/test_manage_vehicle_list.xlsx",
        "class":"TestingManageVehicleList",
        "method":"search_manage_vehicle_list"
    }
}



#GENERIC_API_NAMES = list(API_CONFIG.keys())
GENERIC_API_NAMES = ["test_vehicle_entity_search"]

# test_medallion_owner_listing = "static/test_data/test_medallion_owner_listing_v2.xlsx"
# test_search_driver = "static/test_data/test_search_drivers.xlsx"