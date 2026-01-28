"""
Cost Data Processing Service

CHANGES MADE:
1. REMOVED: "Others" category that grouped unmapped services
2. ADDED: Dynamic service tracking - all Azure services are now shown individually
3. UPDATED: process_cost_data now returns a dict with all unique services found in the data
4. UPDATED: get_relevant_categories now returns all services found, not a fixed list

This module handles the categorization and processing of Azure cost data.
Now shows ALL Azure services individually instead of grouping them.
"""
from typing import Dict, List


class CostProcessorService:
    """Process and categorize cost data"""
    
    @staticmethod
    def process_cost_data(raw_data: List[list]) -> Dict[str, float]:
        """
        Process raw cost data and track ALL services individually.
        
        CHANGE: Instead of mapping to predefined categories with "Others",
        this now tracks every unique Azure service found in the data.
        
        Logic:
        1. Iterate through all cost rows
        2. Track each unique service name with its total cost
        3. Calculate overall total
        4. Return dictionary with all services + Total
        
        Args:
            raw_data: List of cost rows with format [cost, date, service_name, currency]
        
        Returns:
            Dictionary with all service costs and total
            Example: {
                'Virtual Machines': 150.25,
                'Storage': 45.30,
                'Azure Databricks': 320.50,
                'Bandwidth': 12.75,
                'Virtual Network': 8.20,
                'Azure Monitor': 5.50,
                ... (all other services)
                'Total': 542.50
            }
        """
        
        # Initialize with Total only
        costs = {'Total': 0.0}
        
        for row in raw_data:
            cost = float(row[0])
            service_name = row[2] if len(row) > 2 else 'Unknown Service'
            
            # Track each service individually
            if service_name in costs:
                costs[service_name] += cost
            else:
                costs[service_name] = cost
            
            costs['Total'] += cost
        
        return costs
    
    @staticmethod
    def calculate_percentage_change(previous: float, current: float) -> float:
        """
        Calculate percentage change between two values.
        
        UNCHANGED: This logic remains the same.
        
        Logic:
        - If previous is 0 and current > 0: return +100% (new cost appeared)
        - If previous is 0 and current is 0: return 0% (no change)
        - Otherwise: calculate standard percentage change formula
        
        Args:
            previous: Previous period cost
            current: Current period cost
        
        Returns:
            Percentage change as float
        """
        
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        
        return ((current - previous) / previous) * 100
    
    @staticmethod
    def get_relevant_categories(costs_list: List[Dict[str, float]], subscription_name: str) -> List[str]:
        """
        Determine which services have data for a subscription.
        
        CHANGE: Instead of returning a fixed list of categories,
        this now returns ALL unique services found across all days,
        sorted by total cost (descending).
        
        Logic:
        1. Collect all unique service names from all days
        2. Calculate total cost per service across all days
        3. Sort services by total cost (highest first)
        4. Return sorted list (excludes 'Total' which is handled separately)
        
        Args:
            costs_list: List of cost dictionaries for each day
            subscription_name: Name of the subscription being processed (unused now)
        
        Returns:
            List of service names sorted by total cost, descending
        """
        
        # Track total cost per service across all days
        service_totals = {}
        
        for costs in costs_list:
            for service_name, cost in costs.items():
                # Skip 'Total' as it's handled separately
                if service_name == 'Total':
                    continue
                
                if service_name in service_totals:
                    service_totals[service_name] += cost
                else:
                    service_totals[service_name] = cost
        
        # Sort services by total cost (descending)
        sorted_services = sorted(
            service_totals.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Return just the service names
        return [service_name for service_name, _ in sorted_services]