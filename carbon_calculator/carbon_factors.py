"""
Carbon Intensity Factors for Data Center Carbon Footprint Calculator
This module contains carbon intensity factors by region and other emission-related constants.

Climateiq APIs can be used to fetch various emission factors.
"""

from typing import Dict, Any, List, Tuple


class CarbonFactors:
    """
    Class containing carbon intensity factors and other emission-related constants.
    """
    
    # Carbon intensity factors by region (kg CO2e per kWh)
    # Based on average grid emission factors for electricity generation
    CARBON_INTENSITY = {
        'global': 0.475,  # Global average
        'us': 0.385,      # United States average
        'europe': 0.275,  # European average
        'asia': 0.555,    # Asia average
        'china': 0.610,   # China
        'india': 0.720,   # India
        'australia': 0.790, # Australia
        'brazil': 0.090,  # Brazil (high hydropower)
        'africa': 0.520,  # Africa average
        'canada': 0.120,  # Canada (high hydropower)
        'france': 0.055,  # France (high nuclear)
        'germany': 0.338, # Germany
        'uk': 0.233,      # United Kingdom
        'japan': 0.488,   # Japan
        'russia': 0.375   # Russia
    }
    
    # PUE (Power Usage Effectiveness) typical ranges
    PUE_RANGES = {
        'legacy': (1.8, 3.0),        # Legacy data centers
        'standard': (1.4, 1.7),      # Standard enterprise data centers
        'efficient': (1.2, 1.4),     # Efficient data centers
        'hyperscale': (1.07, 1.2),   # Hyperscale data centers
        'state-of-art': (1.01, 1.06) # Leading edge (e.g., Google, Facebook)
    }
    
    # Hardware emissions factors (kg CO2e per hour at 100% utilization)
    HARDWARE_EMISSIONS = {
        'cpu_server': 0.14,   # Standard server with CPUs kg (CO₂e/hour)
        'gpu_card': 0.15,     # GPU card additional emissions (kg CO₂e/hour)
        'storage_tb': 0.003,  # Per TB of storage (kg CO₂e/hour)
        'network_gb': 0.01   # Per GB of network traffic (kg CO₂e/GB) not per hour
    }
    
    # Cooling system efficiency (COP - Coefficient of Performance)
    COOLING_COP = {
        'poor': 1.5,            # Poor efficiency
        'average': 3.0,         # Average efficiency
        'good': 4.5,            # Good efficiency
        'excellent': 6.0        # Excellent efficiency
    }
    
    @classmethod
    def get_carbon_intensity(cls, region: str) -> float:
        """
        Get carbon intensity factor for a specific region.
        
        Args:
            region: Region code (lowercase)
            
        Returns:
            Carbon intensity factor (kg CO2e per kWh)
        """
        return cls.CARBON_INTENSITY.get(region.lower(), cls.CARBON_INTENSITY['global'])
    
    @classmethod
    def get_all_regions(cls) -> List[Tuple[str, float]]:
        """
        Get all available regions with their carbon intensity factors.
        
        Returns:
            List of tuples containing (region_name, intensity_factor)
        """
        return [(region, factor) for region, factor in cls.CARBON_INTENSITY.items()]
    
    @classmethod
    def get_pue_recommendation(cls, current_pue: float) -> Dict[str, Any]:
        """
        Get PUE improvement recommendations based on current PUE.
        
        Args:
            current_pue: Current PUE value
            
        Returns:
            Dictionary with PUE category and improvement recommendations
        """
        category = None
        recommendations = []
        
        # Determine PUE category
        for cat, (min_val, max_val) in cls.PUE_RANGES.items():
            if min_val <= current_pue <= max_val:
                category = cat
                break
        
        if current_pue > cls.PUE_RANGES['legacy'][1]:
            category = 'very_poor'
        
        # Generate recommendations
        if category in ['very_poor', 'legacy']:
            recommendations = [
                "Implement hot/cold aisle containment",
                "Upgrade to more efficient cooling systems",
                "Improve airflow management",
                "Consider raising data center temperature setpoints"
            ]
        elif category == 'standard':
            recommendations = [
                "Optimize cooling control systems",
                "Implement free cooling where possible",
                "Evaluate liquid cooling for high-density racks",
                "Consider renewable energy sources"
            ]
        elif category == 'efficient':
            recommendations = [
                "Fine-tune cooling parameters",
                "Implement advanced power management",
                "Consider AI-driven cooling optimization",
                "Explore heat reuse opportunities"
            ]
        else:  # hyperscale or state-of-art
            recommendations = [
                "Maintain current efficient practices",
                "Continue monitoring for new efficiency technologies",
                "Explore on-site renewable generation"
            ]
            
        return {
            'category': category,
            'current_pue': current_pue,
            'recommendations': recommendations,
            'typical_range': cls.PUE_RANGES.get(category, (None, None))
        }
        
    @classmethod
    def calculate_emission_reduction(cls, 
                                    current_pue: float, 
                                    target_pue: float, 
                                    energy_kwh: float, 
                                    carbon_intensity: float) -> Dict[str, float]:
        """
        Calculate potential emission reduction by improving PUE.
        
        Args:
            current_pue: Current PUE value
            target_pue: Target PUE value
            energy_kwh: Current IT equipment energy in kWh
            carbon_intensity: Carbon intensity factor for the region
            
        Returns:
            Dictionary with emission reduction metrics
        """
        # Current total energy with current PUE
        current_total_energy = energy_kwh * current_pue
        
        # Projected total energy with target PUE
        target_total_energy = energy_kwh * target_pue
        
        # Energy savings
        energy_savings = current_total_energy - target_total_energy
        
        # Emission reduction
        emission_reduction = energy_savings * carbon_intensity
        
        # Cost savings (assuming $0.10 per kWh on average)
        cost_savings = energy_savings * 0.10
        
        return {
            'energy_savings_kwh': round(energy_savings, 2),
            'energy_savings_percentage': round((energy_savings / current_total_energy) * 100, 2),
            'emission_reduction_kg': round(emission_reduction, 2),
            'cost_savings_usd': round(cost_savings, 2)
        }


# Example usage
if __name__ == "__main__":
    # Print all available regions with their carbon intensity factors
    print("Available regions and their carbon intensity factors (kg CO2e per kWh):")
    for region, factor in CarbonFactors.get_all_regions():
        print(f"  {region.capitalize()}: {factor}")
    
    # Get PUE recommendations
    pue_info = CarbonFactors.get_pue_recommendation(1.6)
    print(f"\nPUE Category: {pue_info['category']}")
    print("Recommendations:")
    for rec in pue_info['recommendations']:
        print(f"  - {rec}")
    
    # Calculate potential emission reduction
    reduction = CarbonFactors.calculate_emission_reduction(
        current_pue=1.7,
        target_pue=1.3,
        energy_kwh=10000,
        carbon_intensity=CarbonFactors.get_carbon_intensity('us')
    )
    print("\nPotential Emission Reduction:")
    print(f"  Energy Savings: {reduction['energy_savings_kwh']} kWh ({reduction['energy_savings_percentage']}%)")
    print(f"  Emission Reduction: {reduction['emission_reduction_kg']} kg CO2e")
    print(f"  Cost Savings: ${reduction['cost_savings_usd']}")