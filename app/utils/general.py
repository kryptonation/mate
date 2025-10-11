### app/utils/general.py

# Standard library imports
import os
import random
import base64
import string
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# Third party imports
from fastapi import HTTPException

def split_name(full_name: str):
    parts = full_name.strip().split()
    first_name = parts[0] if len(parts) > 0 else None
    middle_name = " ".join(parts[1:-1]) if len(parts) > 2 else None
    last_name = parts[-1] if len(parts) > 1 else None
    return first_name, middle_name, last_name

def fill_if_missing(target: dict, key: str, source: dict, source_key: str):
            if not target.get(key):
                value = source.get(source_key , None)
                if isinstance(value, list) and value:
                    target[key] = value[0]
                elif value is not None:
                    target[key] = value

def parse_custom_time(t: str) -> datetime.time:
    meridiem = t[-1]
    if meridiem not in ['A', 'P']:
        raise ValueError("Invalid time format")
    
    formatted = t[:-1] + (' AM' if meridiem == 'A' else ' PM')
    return datetime.strptime(formatted, "%I%M %p").time()

def get_date_from_string(from_date, duration_str: str) -> datetime:

    if isinstance(from_date, str):
        from_date = datetime.fromisoformat(from_date)

    duration_str = duration_str.lower().strip()
    number = int(duration_str.split()[0])
    unit = duration_str.split()[1]

    if "month" in unit:
        return from_date + relativedelta(months=number)
    elif "week" in unit:
        return from_date + relativedelta(weeks=number)
    elif "day" in unit:
        return from_date + relativedelta(days=number)
    elif "year" in unit:
        return from_date + relativedelta(years=number)
    else:
        raise ValueError("Unsupported time unit in string")
    
def get_random_date(days = None ,  start_date = None , end_date = None):
    if days:
        today = datetime.today().date()
        start_date = today - timedelta(days=days)
        random_date = start_date + timedelta(days=random.randint(0, (today - start_date).days))
        return random_date
    else:
        if not start_date:
            start_date =start_date = datetime(2025, 1, 1).date()
        if not end_date:
            end_date = datetime.today().date()
        random_date = start_date + timedelta(days=random.randint(0, (end_date - start_date).days))
        return random_date


def get_file_from_local(file_path: str):
    """Retrieve a file from the local media directory and encode it in Base64."""
   
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File in path '{file_path}' not found.")

    with open(file_path, "rb") as file:
        return base64.b64encode(file.read()).decode("utf-8")
    
def generate_alphanumeric_code(length=6):
    """Generate a random alphanumeric code of a given length"""
    characters = string.ascii_uppercase + string.digits  # A-Z0-9
    return ''.join(random.choices(characters, k=length))

def generate_16_digit_mix():
    """Generate a 14-character alphanumeric string with 2 to 3 uppercase letters."""
    num_letters = random.choice([2, 3])  # Choose 2 or 3 letters
    num_digits = 16 - num_letters  # Remaining characters will be digits
    
    letters = random.choices(string.ascii_uppercase, k=num_letters)
    digits = random.choices(string.digits, k=num_digits)
    
    result = letters + digits
    random.shuffle(result)  # Shuffle to mix letters and digits
    
    return ''.join(result)

def generate_random_6_digit():
    """
    Generates a random 6-digit number.

    Returns:
        int: A random 6-digit number.
    """
    return random.randint(100000, 999999)