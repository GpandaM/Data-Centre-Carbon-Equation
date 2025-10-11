"""
Data Loader for Carbon Footprint Calculator
Handles loading and validating data from CSV, Excel, and API sources.
"""

import os
import json
import logging
import requests
import pandas as pd
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataLoader:
    """Class for loading and validating data from various sources."""
    
    # Required fields for calculation
    REQUIRED_FIELDS = ['total_electricity', 'pue']
    
    # Expected fields with default values
    DEFAULT_VALUES = {
        'total_electricity': 0.0,  # kWh/day
        'pue': 1.5,
        'renewable_percentage': 0.0,  # %
        'region': 'global_average',
        'num_servers': 0,
        'cpu_utilization': 0.0,  # %
        'gpu_count': 0,
        'gpu_utilization': 0.0,  # %
        'storage_capacity': 0.0,  # TB
        'storage_type': 'HDD',
        'facility_area': 0.0,  # sq m
        'cooling_efficiency': 3.0,  # COP
        'utilization_hours': 24.0,  # hours/day
        'ai_compute_hours': 0.0,  # hours/day
    }
    
    # Field mapping (alternative field names)
    FIELD_MAPPING = {
        'totalElectricity': 'total_electricity',
        'renewablePercentage': 'renewable_percentage',
        'numServers': 'num_servers',
        'cpuUtilization': 'cpu_utilization',
        'gpuCount': 'gpu_count',
        'gpuUtilization': 'gpu_utilization',
        'storageCapacity': 'storage_capacity',
        'storageType': 'storage_type',
        'facilityArea': 'facility_area',
        'coolingEfficiency': 'cooling_efficiency',
        'utilizationHours': 'utilization_hours',
        'aiComputeHours': 'ai_compute_hours',
    }
    
    # Validation rules
    VALIDATION_RULES = {
        'total_electricity': (float, lambda x: x >= 0, "Total electricity must be non-negative"),
        'pue': (float, lambda x: x >= 1.0, "PUE must be at least 1.0"),
        'renewable_percentage': (float, lambda x: 0 <= x <= 100, "Renewable percentage must be 0–100"),
        'region': (str, lambda x: x, "Region is required"),
        'num_servers': (int, lambda x: x >= 0, "Number of servers must be non-negative"),
        'cpu_utilization': (float, lambda x: 0 <= x <= 100, "CPU utilization must be 0–100"),
        'gpu_count': (int, lambda x: x >= 0, "GPU count must be non-negative"),
        'gpu_utilization': (float, lambda x: 0 <= x <= 100, "GPU utilization must be 0–100"),
        'storage_capacity': (float, lambda x: x >= 0, "Storage capacity must be non-negative"),
        'storage_type': (str, lambda x: x.upper() in ['HDD', 'SSD'], "Storage type must be HDD or SSD"),
        'facility_area': (float, lambda x: x >= 0, "Facility area must be non-negative"),
        'cooling_efficiency': (float, lambda x: x > 0, "Cooling efficiency must be positive"),
        'utilization_hours': (float, lambda x: 0 <= x <= 24, "Utilization hours must be 0–24"),
        'ai_compute_hours': (float, lambda x: 0 <= x <= 24, "AI compute hours must be 0–24"),
    }
    
    @staticmethod
    def load_csv(file_path: str) -> Dict[str, Any]:
        """
        Load data from a CSV file.
        
        Args:
            file_path: Path to the CSV file
            
        Returns:
            Dictionary with processed data
        """
        try:
            df = pd.read_csv(file_path)
            if len(df) == 0:
                raise ValueError("CSV file is empty")
            data = df.iloc[0].to_dict()
            logger.info("Loaded CSV data: %s", data)
            return DataLoader.process_data(data)
        except Exception as e:
            logger.error("Error loading CSV file %s: %s", file_path, str(e))
            raise ValueError(f"Error loading CSV file: {str(e)}")
    
    @staticmethod
    def load_excel(file_path: str) -> Dict[str, Any]:
        """
        Load data from an Excel file.
        
        Args:
            file_path: Path to the Excel file
            
        Returns:
            Dictionary with processed data
        """
        try:
            df = pd.read_excel(file_path)
            if len(df) == 0:
                raise ValueError("Excel file is empty")
            data = df.iloc[0].to_dict()
            logger.info("Loaded Excel data: %s", data)
            return DataLoader.process_data(data)
        except Exception as e:
            logger.error("Error loading Excel file %s: %s", file_path, str(e))
            raise ValueError(f"Error loading Excel file: {str(e)}")
    
    @staticmethod
    def load_api(api_url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Load data from an API endpoint.
        
        Args:
            api_url: URL of the API endpoint
            params: Optional query parameters
            headers: Optional request headers
            
        Returns:
            Dictionary with processed data
        """
        try:
            response = requests.get(api_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            logger.info("Loaded API data from %s: %s", api_url, data)
            return DataLoader.process_data(data)
        except requests.exceptions.RequestException as e:
            logger.error("Error fetching API data from %s: %s", api_url, str(e))
            raise ValueError(f"Error fetching data from API: {str(e)}")
        except json.JSONDecodeError:
            logger.error("Invalid JSON response from %s", api_url)
            raise ValueError("API response is not valid JSON")
    
    @staticmethod
    def process_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process and validate input data.
        
        Args:
            data: Raw input data
            
        Returns:
            Processed and validated data
        """
        processed_data = {}
        
        # Normalize field names
        for key, value in data.items():
            processed_key = DataLoader.FIELD_MAPPING.get(key, key.lower())
            if value == '' or value is None:
                value = DataLoader.DEFAULT_VALUES.get(processed_key, 0)
            processed_data[processed_key] = value
        
        # Apply defaults for missing fields
        for field, default in DataLoader.DEFAULT_VALUES.items():
            processed_data.setdefault(field, default)
        
        # Validate and convert types
        validated_data = {}
        for field, (type_fn, validator, error_msg) in DataLoader.VALIDATION_RULES.items():
            try:
                value = processed_data[field]
                if isinstance(value, str) and value.strip() == '':
                    validated_data[field] = DataLoader.DEFAULT_VALUES[field]
                else:
                    validated_data[field] = type_fn(value)
                    if not validator(validated_data[field]):
                        raise ValueError(error_msg)
            except (ValueError, TypeError) as e:
                logger.error("Validation failed for %s: %s", field, str(e))
                raise ValueError(f"Invalid {field}: {error_msg}")
        
        logger.info("Processed data: %s", validated_data)
        return validated_data
    
    @staticmethod
    def save_data(data: Dict[str, Any], file_path: str) -> None:
        """
        Save data to a JSON file.
        
        Args:
            data: Dictionary to save
            file_path: Path to save the file
        """
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info("Saved data to %s", file_path)
        except Exception as e:
            logger.error("Error saving data to %s: %s", file_path, str(e))
            raise ValueError(f"Error saving data: {str(e)}")
    
    @staticmethod
    def create_sample_csv(file_path: str) -> None:
        """
        Create a sample CSV file with default values.
        
        Args:
            file_path: Path to save the sample CSV
        """
        try:
            df = pd.DataFrame([DataLoader.DEFAULT_VALUES])
            df.to_csv(file_path, index=False)
            logger.info("Created sample CSV at %s", file_path)
        except Exception as e:
            logger.error("Error creating sample CSV at %s: %s", file_path, str(e))
            raise ValueError(f"Error creating sample CSV: {str(e)}")
    
    @staticmethod
    def create_sample_excel(file_path: str) -> None:
        """
        Create a sample Excel file with default values.
        
        Args:
            file_path: Path to save the sample Excel
        """
        try:
            df = pd.DataFrame([DataLoader.DEFAULT_VALUES])
            df.to_excel(file_path, index=False)
            logger.info("Created sample Excel at %s", file_path)
        except Exception as e:
            logger.error("Error creating sample Excel at %s: %s", file_path, str(e))
            raise ValueError(f"Error creating sample Excel: {str(e)}")

if __name__ == "__main__":
    os.makedirs('data', exist_ok=True)
    DataLoader.create_sample_csv('data/sample.csv')
    DataLoader.create_sample_excel('data/sample.xlsx')
