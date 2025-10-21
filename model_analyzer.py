#!/usr/bin/env python3
"""
Model Analyzer Script
This script analyzes all SQLAlchemy models in the application and generates an Excel document
with detailed information about each model's fields, types, constraints, and relationships.
"""

import os
import re
import ast
import inspect
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional
import importlib.util


class ModelAnalyzer:
    def __init__(self, app_path: str):
        self.app_path = Path(app_path)
        self.models_data = {}
        
    def find_all_models_files(self) -> List[Path]:
        """Find all models.py files in the application"""
        models_files = []
        for root, dirs, files in os.walk(self.app_path):
            for file in files:
                if file == "models.py":
                    models_files.append(Path(root) / file)
        return models_files
    
    def extract_sqlalchemy_type_info(self, type_str: str) -> tuple:
        """Extract SQLAlchemy type information including size constraints"""
        type_name = type_str
        size = None
        
        # Common type patterns
        if "String(" in type_str:
            match = re.search(r'String\((\d+)\)', type_str)
            if match:
                size = int(match.group(1))
                type_name = "String"
        elif "CHAR(" in type_str:
            match = re.search(r'CHAR\((\d+)\)', type_str)
            if match:
                size = int(match.group(1))
                type_name = "CHAR"
        elif "DECIMAL(" in type_str:
            match = re.search(r'DECIMAL\((\d+),\s*(\d+)\)', type_str)
            if match:
                size = f"{match.group(1)},{match.group(2)}"
                type_name = "DECIMAL"
        elif "Numeric(" in type_str:
            match = re.search(r'Numeric\((\d+),\s*(\d+)\)', type_str)
            if match:
                size = f"{match.group(1)},{match.group(2)}"
                type_name = "Numeric"
        elif "BigInteger" in type_str:
            type_name = "BigInteger"
        elif "Integer" in type_str:
            type_name = "Integer"
        elif "Boolean" in type_str:
            type_name = "Boolean"
        elif "Date" in type_str and "DateTime" not in type_str:
            type_name = "Date"
        elif "DateTime" in type_str:
            type_name = "DateTime"
        elif "Float" in type_str:
            type_name = "Float"
        elif "Text" in type_str:
            type_name = "Text"
        elif "Enum(" in type_str:
            type_name = "Enum"
        
        return type_name, size
    
    def extract_column_info_from_text(self, file_content: str, class_name: str) -> List[Dict]:
        """Extract column information from model class using text parsing"""
        columns = []
        
        # Find the class definition
        class_pattern = rf'class\s+{class_name}\s*\([^)]*\):'
        class_match = re.search(class_pattern, file_content)
        if not class_match:
            return columns
        
        # Get the class content (indented lines after class definition)
        lines = file_content[class_match.end():].split('\n')
        class_lines = []
        for line in lines:
            if line.strip() == '' or line.startswith('    ') or line.startswith('\t'):
                class_lines.append(line)
            else:
                break
        
        class_content = '\n'.join(class_lines)
        
        # Find column definitions using various patterns
        patterns = [
            # mapped_column pattern: field: Mapped[type] = mapped_column(...)
            r'(\w+)\s*:\s*Mapped\[[^\]]+\]\s*=\s*mapped_column\(([^)]*(?:\([^)]*\))*[^)]*)\)',
            # Column pattern: field = Column(...)
            r'(\w+)\s*=\s*Column\(([^)]*(?:\([^)]*\))*[^)]*)\)',
            # relationship pattern: field = relationship(...)
            r'(\w+)\s*=\s*relationship\(([^)]*(?:\([^)]*\))*[^)]*)\)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, class_content, re.MULTILINE | re.DOTALL)
            for match in matches:
                field_name = match.group(1)
                field_definition = match.group(2)
                
                # Skip certain fields
                if field_name in ['__tablename__', '__table_args__', 'metadata']:
                    continue
                
                column_info = self.parse_column_definition(field_name, field_definition, pattern)
                if column_info:
                    columns.append(column_info)
        
        return columns
    
    def parse_column_definition(self, field_name: str, definition: str, pattern: str) -> Optional[Dict]:
        """Parse a column definition to extract information"""
        column_info = {
            'name': field_name,
            'type': 'Unknown',
            'size': None,
            'is_nullable': True,
            'constraint': '',
            'description': '',
            'relationship': ''
        }
        
        # Check if it's a relationship
        if 'relationship(' in definition:
            column_info['type'] = 'Relationship'
            column_info['relationship'] = self.extract_relationship_info(definition)
            return column_info
        
        # Extract type information
        type_match = re.search(r'(String|Integer|Boolean|Date|DateTime|Float|Text|CHAR|DECIMAL|Numeric|BigInteger|Enum)\s*(\([^)]+\))?', definition)
        if type_match:
            full_type = type_match.group(0)
            type_name, size = self.extract_sqlalchemy_type_info(full_type)
            column_info['type'] = type_name
            column_info['size'] = size
        
        # Extract nullable information
        if 'nullable=False' in definition:
            column_info['is_nullable'] = False
        elif 'nullable=True' in definition:
            column_info['is_nullable'] = True
        
        # Extract constraints
        constraints = []
        if 'primary_key=True' in definition:
            constraints.append('PRIMARY KEY')
        if 'unique=True' in definition:
            constraints.append('UNIQUE')
        if 'index=True' in definition:
            constraints.append('INDEX')
        if 'ForeignKey(' in definition:
            fk_match = re.search(r'ForeignKey\(["\']([^"\']+)["\']', definition)
            if fk_match:
                constraints.append(f'FOREIGN KEY -> {fk_match.group(1)}')
        
        column_info['constraint'] = ', '.join(constraints)
        
        # Extract comment/description
        comment_match = re.search(r'comment=["\']([^"\']*)["\']', definition)
        if comment_match:
            column_info['description'] = comment_match.group(1)
        
        return column_info
    
    def extract_relationship_info(self, definition: str) -> str:
        """Extract relationship information"""
        # Extract the target model
        model_match = re.search(r'["\']([^"\']+)["\']', definition)
        target_model = model_match.group(1) if model_match else 'Unknown'
        
        # Determine relationship type
        if 'back_populates' in definition:
            return f'Bidirectional -> {target_model}'
        elif 'backref' in definition:
            return f'Backref -> {target_model}'
        else:
            return f'One-way -> {target_model}'
    
    def analyze_models_file(self, file_path: Path) -> Dict[str, List[Dict]]:
        """Analyze a single models.py file"""
        models_in_file = {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find all class definitions that inherit from Base
            class_pattern = r'class\s+(\w+)\s*\([^)]*Base[^)]*\):'
            classes = re.findall(class_pattern, content)
            
            for class_name in classes:
                # Skip Mixin classes
                if 'Mixin' in class_name:
                    continue
                    
                columns = self.extract_column_info_from_text(content, class_name)
                if columns:
                    models_in_file[class_name] = columns
            
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
        
        return models_in_file
    
    def analyze_all_models(self):
        """Analyze all models in the application"""
        models_files = self.find_all_models_files()
        
        for file_path in models_files:
            print(f"Analyzing: {file_path}")
            models_in_file = self.analyze_models_file(file_path)
            
            # Add module info
            module_name = str(file_path.relative_to(self.app_path)).replace('/', '.').replace('.py', '')
            
            for model_name, columns in models_in_file.items():
                full_model_name = f"{module_name}.{model_name}"
                self.models_data[model_name] = {
                    'module': module_name,
                    'columns': columns
                }
        
        print(f"Found {len(self.models_data)} models")
    
    def generate_excel_report(self, output_path: str = "models_analysis.xlsx"):
        """Generate Excel report with model information"""
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            
            # Create summary sheet
            summary_data = []
            for model_name, model_info in self.models_data.items():
                summary_data.append({
                    'Model Name': model_name,
                    'Module': model_info['module'],
                    'Total Fields': len(model_info['columns']),
                    'Relationships': len([c for c in model_info['columns'] if c['type'] == 'Relationship'])
                })
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Create individual sheets for each model
            for model_name, model_info in self.models_data.items():
                # Prepare data for this model
                model_data = []
                for column in model_info['columns']:
                    model_data.append({
                        'name': column['name'],
                        'type': column['type'],
                        'size': column['size'] if column['size'] else '',
                        'is_nullable': 'Yes' if column['is_nullable'] else 'No',
                        'constraint': column['constraint'],
                        'description': column['description'],
                        'relationship': column['relationship']
                    })
                
                if model_data:
                    df = pd.DataFrame(model_data)
                    # Excel sheet names have a 31 character limit
                    sheet_name = model_name[:31] if len(model_name) > 31 else model_name
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        print(f"Excel report generated: {output_path}")


def main():
    """Main function to run the model analysis"""
    app_path = "/Users/dd/playground/apple-ref/backend/app"
    
    print("Starting model analysis...")
    analyzer = ModelAnalyzer(app_path)
    analyzer.analyze_all_models()
    analyzer.generate_excel_report("models_analysis.xlsx")
    print("Analysis complete!")


if __name__ == "__main__":
    main()
