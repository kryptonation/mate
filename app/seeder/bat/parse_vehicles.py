# Standard library imports
from datetime import datetime

# Third party imports
import pandas as pd
from sqlalchemy.orm import Session

# Local imports
from app.core.db import SessionLocal
from app.core.config import settings
from app.utils.logger import get_logger
from app.utils.s3_utils import s3_utils
from app.vehicles.models import VehicleEntity
from app.medallions.models import Medallion
from app.vehicles.models import Vehicle

logger = get_logger(__name__)
SUPERADMIN_USER_ID = 1

def parse_date(date_str):
    """
    Parses a date string into a datetime object.
    If the string is invalid or empty, returns None.
    """
    try:
        return date_str.to_pydatetime() if pd.notnull(date_str) else None
    except ValueError:
        return None

def parse_vehicles(db: Session, df: pd.DataFrame):
    """
    Parses the vehicles data from the excel file and upserts the data into the database.
    """
    try:
        for _, row in df.iterrows():
            # Find the associated entity based on the entity name
            entity = db.query(VehicleEntity).filter(
                VehicleEntity.entity_name == row["entity_name"]).first()
            if not entity:
                raise ValueError(
                    f"Entity '{row['entity_name']}' does not exist in the database."
                )
            # Find associated medallion based in the medallion number
            medallion_id = None
            if "medallion_number" in row:
                if not pd.isnull(row["medallion_number"]) and not pd.isna(row["medallion_number"]):
                    medallion = db.query(Medallion).filter(Medallion.medallion_number == row["medallion_number"]).first()
                    if not medallion:
                        raise ValueError(
                            f"Medallion '{row['medallion_number']}' does not exist in the database."
                        )
                    medallion_id = medallion.id

            # Check if the vehicle already exists by VIN
            vehicle = db.query(Vehicle).filter(Vehicle.vin == row["vin"]).first()

            if vehicle:
                # Update existing vehicle record
                vehicle.make = row["make"]
                vehicle.model = row["model"]
                vehicle.year = row["year"]
                vehicle.cylinders = row["cylinders"]
                vehicle.color = row["color"]
                vehicle.vehicle_type = row["vehicle_type"]
                vehicle.is_hybrid = row["is_hybrid"]
                vehicle.base_price = row["base_price"]
                vehicle.sales_tax = row["sales_tax"]
                vehicle.vehicle_office = row["vehicle_office"]
                vehicle.is_delivered = row["is_delivered"]
                vehicle.expected_delivery_date = parse_date(
                    row["expected_delivery_date"])
                vehicle.delivery_location = row["delivery_location"]
                vehicle.is_insurance_procured = row["is_insurance_procured"]
                vehicle.tlc_hackup_inspection_date = parse_date(
                    row["tlc_hackup_inspection_date"])
                vehicle.is_medallion_assigned = row["is_medallion_assigned"]
                vehicle.vehicle_status = row["vehicle_status"]
                vehicle.entity_id = entity.id
                vehicle.medallion_id = medallion_id
                vehicle.vehicle_total_price = row["vehicle_total_price"]
                vehicle.vehicle_true_cost = row["vehicle_true_cost"]
                vehicle.vehicle_hack_up_cost = row["vehicle_hack_up_cost"]
                vehicle.vehicle_lifetime_cap = row["vehicle_lifetime_cap"]


            else:
                # Create a new vehicle record
                vehicle = Vehicle(
                    vin=row["vin"],
                    make=row["make"],
                    model=row["model"],
                    year=row["year"],
                    cylinders=row["cylinders"],
                    color=row["color"],
                    vehicle_type=row["vehicle_type"],
                    is_hybrid=row["is_hybrid"],
                    base_price=row["base_price"],
                    sales_tax=row["sales_tax"],
                    vehicle_office=row["vehicle_office"],
                    is_delivered=row["is_delivered"],
                    expected_delivery_date=parse_date(
                        row["expected_delivery_date"]),
                    delivery_location=row["delivery_location"],
                    is_insurance_procured=row["is_insurance_procured"],
                    tlc_hackup_inspection_date=parse_date(
                        row["tlc_hackup_inspection_date"]),
                    is_medallion_assigned= True if medallion_id else False,
                    vehicle_status=row["vehicle_status"],
                    entity_id=entity.id,
                    medallion_id=medallion_id,
                    vehicle_total_price=row["vehicle_total_price"],
                    vehicle_true_cost=row["vehicle_true_cost"],
                    vehicle_hack_up_cost=row["vehicle_hack_up_cost"],
                    vehicle_lifetime_cap=row["vehicle_lifetime_cap"]
                )
                db.add(vehicle)
                db.commit()
    except Exception as e:
        db.rollback()
        logger.error("Error parsing vehicles data: %s", e)
        raise

if __name__ == "__main__":
    db_session = SessionLocal()
    excel_file = pd.ExcelFile(s3_utils.download_file(settings.bat_file_key))
    vehicles_df = pd.read_excel(excel_file, 'vehicles')
    parse_vehicles(db_session, vehicles_df)
    db_session.close()



