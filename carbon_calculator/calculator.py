"""
Data Center Carbon Footprint Calculator Module
This module calculates the carbon footprint of a data center, including Scope 2 (electricity) and Scope 3 (hardware lifecycle) emissions, with AI workload modeling.
"""

import datetime
import logging
from typing import Dict, Optional
from .carbon_factors import CarbonFactors

# Configure logging
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DataCenterCarbonCalculator:
    """
    Calculator for determining the carbon footprint of data centers, including IT, cooling, and hardware lifecycle emissions.
    """
    
    def __init__(self, default_pue: float = 1.3, default_region: str = 'global_average', energy_cost_per_kwh: float = 0.12):
        """
        Initialize the calculator with configurable defaults.

        Args:
            default_pue (float): Default Power Usage Effectiveness.
            default_region (str): Default region for carbon intensity.
            energy_cost_per_kwh (float): Default energy cost ($/kWh).
        """
        try:
            self.carbon_factors = CarbonFactors()
            self.default_pue = default_pue
            self.default_region = default_region
            self.energy_cost_per_kwh = energy_cost_per_kwh
            # logging.info("Initialized DataCenterCarbonCalculator with PUE=%.2f, region=%s", default_pue, default_region)
        except Exception as e:
            # logging.error("Failed to initialize CarbonFactors: %s", e)
            raise

    def calculate_carbon_footprint(self, data: Dict) -> Dict:
        """
        Calculate the carbon footprint of a data center.

        Args:
            data (dict): Data center parameters (e.g., total_electricity, pue, num_servers, ai_compute_hours).

        Returns:
            dict: Carbon footprint results with emissions, costs, and savings.

        Raises:
            ValueError: If inputs are invalid.
        """
        # Input validation
        required_fields = ['num_servers', 'gpu_count', 'storage_capacity', 'utilization_hours']
        for field in required_fields:
            if field in data and data[field] < 0:
                raise ValueError(f"{field} cannot be negative")
        if 'pue' in data and data['pue'] < 1.0:
            raise ValueError("PUE must be at least 1.0")
        if 'renewable_percentage' in data and not (0 <= data['renewable_percentage'] <= 100):
            raise ValueError("Renewable percentage must be between 0 and 100")
        if 'cpu_utilization' in data and not (0 <= data['cpu_utilization'] <= 100):
            raise ValueError("CPU utilization must be between 0 and 100")
        if 'gpu_utilization' in data and not (0 <= data['gpu_utilization'] <= 100):
            raise ValueError("GPU utilization must be between 0 and 100")
        if 'utilization_hours' in data and not (0 <= data['utilization_hours'] <= 24):
            raise ValueError("Utilization hours must be between 0 and 24")

        # Extract data with defaults
        total_electricity = float(data.get('total_electricity', 0))  # kWh/day
        pue = float(data.get('pue', self.default_pue))
        renewable_percentage = float(data.get('renewable_percentage', 0))
        region = data.get('region', self.default_region)
        num_servers = int(data.get('num_servers', 0))
        cpu_utilization = float(data.get('cpu_utilization', 50))
        gpu_count = int(data.get('gpu_count', 0))
        gpu_utilization = float(data.get('gpu_utilization', 50))
        storage_capacity = float(data.get('storage_capacity', 0))
        storage_type = data.get('storage_type', 'HDD').upper()
        facility_area = float(data.get('facility_area', 0))
        cooling_efficiency = float(data.get('cooling_efficiency', 3.0))
        utilization_hours = float(data.get('utilization_hours', 24))
        ai_compute_hours = float(data.get('ai_compute_hours', 0))  # Hours of AI training/inference

        # Get carbon intensity (kg CO2e/kWh)
        carbon_intensity = self.carbon_factors.get_carbon_intensity(region)

        # Estimate electricity if not provided
        if total_electricity <= 0 and num_servers > 0:
            total_electricity = self._estimate_electricity_consumption(
                num_servers=num_servers,
                cpu_utilization=cpu_utilization,
                gpu_count=gpu_count,
                gpu_utilization=gpu_utilization,
                storage_capacity=storage_capacity,
                storage_type=storage_type,
                utilization_hours=utilization_hours,
                ai_compute_hours=ai_compute_hours
            )

        # Total energy with PUE
        total_energy_with_pue = total_electricity * pue

        # Non-renewable energy
        non_renewable_energy = total_energy_with_pue * (1 - (renewable_percentage / 100))

        # Daily and annual Scope 2 emissions
        daily_scope2_emissions = non_renewable_energy * carbon_intensity
        annual_scope2_emissions = daily_scope2_emissions * 365

        # Scope 3 emissions (hardware lifecycle)
        scope3_emissions_annual = self._estimate_scope3_emissions(
            num_servers=num_servers,
            gpu_count=gpu_count,
            storage_capacity=storage_capacity,
            storage_type=storage_type
        )

        # Total emissions
        annual_carbon_emissions = annual_scope2_emissions + scope3_emissions_annual
        daily_carbon_emissions = annual_carbon_emissions / 365

        # Emissions breakdown
        it_emissions = total_electricity * carbon_intensity * (1 - (renewable_percentage / 100))
        non_it_power = total_energy_with_pue - total_electricity
        cooling_power = non_it_power * (1 / cooling_efficiency) / (1 / cooling_efficiency + 1)  # Dynamic cooling ratio
        other_power = non_it_power - cooling_power
        cooling_emissions = cooling_power * carbon_intensity * (1 - (renewable_percentage / 100))
        other_emissions = other_power * carbon_intensity * (1 - (renewable_percentage / 100))

        # Efficiency metrics
        carbon_per_server = annual_carbon_emissions / num_servers if num_servers > 0 else 0
        emissions_per_sqm = annual_carbon_emissions / facility_area if facility_area > 0 else 0

        # Energy costs
        energy_cost_daily = total_energy_with_pue * self.energy_cost_per_kwh
        energy_cost_annual = energy_cost_daily * 365

        # Savings calculations
        pue_savings = self._calculate_pue_improvement_savings(
            total_electricity, pue, carbon_intensity, renewable_percentage, target_pue=1.2
        )
        renewable_savings = self._calculate_renewable_improvement_savings(
            total_energy_with_pue, carbon_intensity, renewable_percentage, target_renewable=80
        )
        utilization_savings = self._calculate_utilization_improvement_savings(
            num_servers, cpu_utilization, gpu_count, gpu_utilization, carbon_intensity, pue, renewable_percentage
        )

        # Compile results
        results = {
            'summary': {
                'daily_carbon_emissions': {'value': daily_carbon_emissions, 'unit': 'kg CO2e/day'},
                'annual_carbon_emissions': {'value': annual_carbon_emissions, 'unit': 'kg CO2e/year'},
                'energy_consumption': {'value': total_energy_with_pue, 'unit': 'kWh/day'}
            },
            'scope_breakdown': {
                'scope2': {'value': annual_scope2_emissions, 'unit': 'kg CO2e/year', 'percentage': (annual_scope2_emissions / annual_carbon_emissions * 100) if annual_carbon_emissions > 0 else 0},
                'scope3': {'value': scope3_emissions_annual, 'unit': 'kg CO2e/year', 'percentage': (scope3_emissions_annual / annual_carbon_emissions * 100) if annual_carbon_emissions > 0 else 0}
            },
            'emissions_breakdown': {
                'it_equipment': {'value': it_emissions, 'unit': 'kg CO2e/day', 'percentage': (it_emissions / daily_carbon_emissions * 100) if daily_carbon_emissions > 0 else 0},
                'cooling': {'value': cooling_emissions, 'unit': 'kg CO2e/day', 'percentage': (cooling_emissions / daily_carbon_emissions * 100) if daily_carbon_emissions > 0 else 0},
                'other_overhead': {'value': other_emissions, 'unit': 'kg CO2e/day', 'percentage': (other_emissions / daily_carbon_emissions * 100) if daily_carbon_emissions > 0 else 0}
            },
            'efficiency_metrics': {
                'carbon_per_server': {'value': carbon_per_server, 'unit': 'kg CO2e/server/year'},
                'emissions_per_sqm': {'value': emissions_per_sqm, 'unit': 'kg CO2e/sqm/year'}
            },
            'costs': {
                'energy_cost_daily': {'value': energy_cost_daily, 'unit': 'USD/day'},
                'energy_cost_annual': {'value': energy_cost_annual, 'unit': 'USD/year'}
            },
            'potential_savings': {
                'pue_improvement': {'value': pue_savings, 'unit': 'kg CO2e/year'},
                'renewable_improvement': {'value': renewable_savings, 'unit': 'kg CO2e/year'},
                'utilization_improvement': {'value': utilization_savings, 'unit': 'kg CO2e/year'}
            },
            'input_data': data,
            'timestamp': datetime.datetime.now().isoformat()
        }
        return results

    def _estimate_electricity_consumption(
        self,
        num_servers: int,
        cpu_utilization: float,
        gpu_count: int,
        gpu_utilization: float,
        storage_capacity: float,
        storage_type: str,
        utilization_hours: float,
        ai_compute_hours: float
    ) -> float:
        """
        Estimate electricity consumption for IT equipment.

        Args:
            num_servers (int): Number of servers.
            cpu_utilization (float): CPU utilization percentage (0-100).
            gpu_count (int): Number of GPUs.
            gpu_utilization (float): GPU utilization percentage (0-100).
            storage_capacity (float): Storage capacity in TB.
            storage_type (str): 'HDD' or 'SSD'.
            utilization_hours (float): Daily hours of operation (0-24).
            ai_compute_hours (float): Hours of AI training/inference.

        Returns:
            float: Daily electricity consumption in kWh.

        Raises:
            ValueError: If inputs are invalid.
        """
        if not (0 <= cpu_utilization <= 100 and 0 <= gpu_utilization <= 100):
            raise ValueError("Utilization must be between 0 and 100")
        if not (0 <= utilization_hours <= 24):
            raise ValueError("Utilization hours must be between 0 and 24")
        if storage_type not in ['HDD', 'SSD']:
            raise ValueError("Storage type must be 'HDD' or 'SSD'")
        if not (num_servers >= 0 and gpu_count >= 0 and storage_capacity >= 0 and ai_compute_hours >= 0):
            raise ValueError("Non-negative inputs required")

        # Server power (modern high-end server)
        server_idle_power = 200  # Watts
        server_max_power = 800   # Watts
        server_power = server_idle_power + (server_max_power - server_idle_power) * (cpu_utilization / 100)

        # GPU power (e.g., NVIDIA A100)
        gpu_idle_power = 50
        gpu_max_power = 400
        gpu_power = gpu_idle_power + (gpu_max_power - gpu_idle_power) * (gpu_utilization / 100)

        # AI workload adjustment (assume 10% higher GPU power for training)
        ai_gpu_power = gpu_power * (1.1 if ai_compute_hours > 0 else 1.0)
        total_gpu_power = gpu_count * ai_gpu_power

        # Storage power
        storage_power_per_tb = 5 if storage_type == 'HDD' else 15

        # Networking power (10W/port, 48 ports/switch, 1 switch/20 servers)
        num_switches = max(1, num_servers // 20)
        switch_power = num_switches * 48 * 10

        # Total IT power
        total_server_power = num_servers * server_power
        total_storage_power = storage_capacity * storage_power_per_tb
        total_networking_power = switch_power
        total_power_watts = total_server_power + total_gpu_power + total_storage_power + total_networking_power

        # Daily electricity in kWh
        daily_electricity = (total_power_watts / 1000) * utilization_hours
        # logging.info("Estimated electricity: %.2f kWh/day for %d servers, %d GPUs", daily_electricity, num_servers, gpu_count)
        return daily_electricity

    def _estimate_scope3_emissions(
        self,
        num_servers: int,
        gpu_count: int,
        storage_capacity: float,
        storage_type: str
    ) -> float:
        """
        Estimate annual Scope 3 emissions from hardware lifecycle.

        Args:
            num_servers (int): Number of servers.
            gpu_count (int): Number of GPUs.
            storage_capacity (float): Storage capacity in TB.
            storage_type (str): 'HDD' or 'SSD'.

        Returns:
            float: Annual Scope 3 emissions in kg CO2e.
        """
        # Assume 5-year lifecycle for hardware
        server_emissions = num_servers * 5000 / 5  # 5 tCO2e/server, annualized
        gpu_emissions = gpu_count * 15 / 5         # 15 kg CO2e/GPU, annualized
        storage_emissions = storage_capacity * (10 if storage_type == 'HDD' else 20) / 5  # kg CO2e/TB
        total_scope3 = server_emissions + gpu_emissions + storage_emissions
        # logging.info("Estimated Scope 3 emissions: %.2f kg CO2e/year", total_scope3)
        return total_scope3

    def _calculate_pue_improvement_savings(
        self,
        total_electricity: float,
        current_pue: float,
        carbon_intensity: float,
        renewable_percentage: float,
        target_pue: float = 1.2
    ) -> float:
        """
        Calculate carbon savings from improving PUE.

        Args:
            total_electricity (float): IT electricity in kWh/day.
            current_pue (float): Current PUE.
            carbon_intensity (float): kg CO2e/kWh.
            renewable_percentage (float): % renewable energy.
            target_pue (float): Target PUE.

        Returns:
            float: Annual carbon savings in kg CO2e.
        """
        if current_pue <= target_pue:
            return 0
        current_emissions = total_electricity * current_pue * carbon_intensity * (1 - renewable_percentage / 100) * 365
        improved_emissions = total_electricity * target_pue * carbon_intensity * (1 - renewable_percentage / 100) * 365
        savings = current_emissions - improved_emissions
        # logging.info("PUE savings: %.2f kg CO2e/year for PUE %.2f -> %.2f", savings, current_pue, target_pue)
        return savings

    def _calculate_renewable_improvement_savings(
        self,
        total_energy_with_pue: float,
        carbon_intensity: float,
        current_renewable_percentage: float,
        target_renewable: float = 80
    ) -> float:
        """
        Calculate carbon savings from increasing renewable energy.

        Args:
            total_energy_with_pue (float): Total energy in kWh/day.
            carbon_intensity (float): kg CO2e/kWh.
            current_renewable_percentage (float): Current % renewable.
            target_renewable (float): Target % renewable.

        Returns:
            float: Annual carbon savings in kg CO2e.
        """
        if current_renewable_percentage >= target_renewable:
            return 0
        current_emissions = total_energy_with_pue * carbon_intensity * (1 - current_renewable_percentage / 100) * 365
        improved_emissions = total_energy_with_pue * carbon_intensity * (1 - target_renewable / 100) * 365
        savings = current_emissions - improved_emissions
        # logging.info("Renewable savings: %.2f kg CO2e/year for %.1f%% -> %.1f%%", savings, current_renewable_percentage, target_renewable)
        return savings

    def _calculate_utilization_improvement_savings(
        self,
        num_servers: int,
        cpu_utilization: float,
        gpu_count: int,
        gpu_utilization: float,
        carbon_intensity: float,
        pue: float,
        renewable_percentage: float
    ) -> float:
        """
        Estimate carbon savings from increasing CPU and GPU utilization.

        Args:
            num_servers (int): Number of servers.
            cpu_utilization (float): Current CPU utilization (%).
            gpu_count (int): Number of GPUs.
            gpu_utilization (float): Current GPU utilization (%).
            carbon_intensity (float): kg CO2e/kWh.
            pue (float): PUE.
            renewable_percentage (float): % renewable.

        Returns:
            float: Annual carbon savings in kg CO2e.
        """
        target_cpu_util = 65.0
        target_gpu_util = 80.0  # Higher for AI workloads
        savings = 0

        # CPU utilization savings
        if cpu_utilization < target_cpu_util and num_servers > 0:
            servers_needed = num_servers * (cpu_utilization / target_cpu_util)
            servers_removed = num_servers - servers_needed
            server_power = 500  # Average watts (modern server)
            energy_saved = (servers_removed * server_power / 1000) * 24 * 365 * pue
            savings += energy_saved * carbon_intensity * (1 - renewable_percentage / 100)

        # GPU utilization savings
        if gpu_utilization < target_gpu_util and gpu_count > 0:
            gpus_needed = gpu_count * (gpu_utilization / target_gpu_util)
            gpus_removed = gpu_count - gpus_needed
            gpu_power = 225  # Average watts (e.g., A100)
            energy_saved = (gpus_removed * gpu_power / 1000) * 24 * 365 * pue
            savings += energy_saved * carbon_intensity * (1 - renewable_percentage / 100)

        # logging.info("Utilization savings: %.2f kg CO2e/year", savings)
        return savings


if __name__ == "__main__":
    calculator = DataCenterCarbonCalculator()
    data = {
        'total_electricity': 4109.59,  # kWh/day
        'pue': 1.5,
        'renewable_percentage': 40,
        'region': 'us',
        'num_servers': 1200,
        'cpu_utilization': 35,
        'gpu_count': 100,
        'gpu_utilization': 50,
        'storage_capacity': 5000,
        'storage_type': 'HDD',
        'facility_area': 30000,
        'cooling_efficiency': 0.85,
        'utilization_hours': 24,
        'ai_compute_hours': 10
    }
    result = calculator.calculate_carbon_footprint(data)
    import json
    print(json.dumps(result, indent=2))