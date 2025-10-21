#!/usr/bin/env python3
"""
Quick verification script to show the contents of the generated Excel file
"""

import pandas as pd
import os

def verify_excel_file(file_path):
    """Verify and display information about the Excel file"""
    if not os.path.exists(file_path):
        print(f"Excel file not found: {file_path}")
        return
    
    print(f"Excel file found: {file_path}")
    print(f"File size: {os.path.getsize(file_path)} bytes")
    
    # Read the Excel file
    excel_file = pd.ExcelFile(file_path)
    
    print(f"\nNumber of sheets: {len(excel_file.sheet_names)}")
    print("\nSheet names:")
    for i, sheet_name in enumerate(excel_file.sheet_names, 1):
        print(f"{i:2d}. {sheet_name}")
    
    # Show summary sheet content
    print("\n" + "="*50)
    print("SUMMARY SHEET CONTENT:")
    print("="*50)
    summary_df = pd.read_excel(file_path, sheet_name='Summary')
    print(summary_df.to_string(index=False))
    
    # Show a sample model sheet
    if len(excel_file.sheet_names) > 1:
        sample_sheet = excel_file.sheet_names[1]  # First model sheet
        print(f"\n" + "="*50)
        print(f"SAMPLE MODEL SHEET: {sample_sheet}")
        print("="*50)
        sample_df = pd.read_excel(file_path, sheet_name=sample_sheet)
        print(sample_df.to_string(index=False))
        print(f"\nColumns in this sheet: {list(sample_df.columns)}")

if __name__ == "__main__":
    verify_excel_file("/Users/dd/playground/apple-ref/backend/models_analysis.xlsx")
