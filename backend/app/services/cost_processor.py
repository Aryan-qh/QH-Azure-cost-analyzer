"""
Cost Data Processing Service

This module handles the categorization and processing of Azure cost data.
It maps raw Azure service names to logical categories for reporting.
"""
from typing import Dict, List


class CostProcessorService:
    """Process and categorize cost data"""
    
    @staticmethod
    def process_cost_data(raw_data: List[list]) -> Dict[str, float]:
        """
        Process raw cost data into categories.
        
        CHANGE #2: Added two new cost categories
        - Bandwidth: Captures data transfer and bandwidth costs
        - Virtual Network: Captures VNet, VPN, and related networking costs
        
        Category Mapping Logic:
        - Databricks: 'Azure Databricks' service
        - Virtual Machine: 'Virtual Machines' service
        - Storage: 'Storage' service
        - Bandwidth: 'Bandwidth' service (NEW)
        - Virtual Network: 'Virtual Network' service (NEW)
        - Others: All other services
        
        Args:
            raw_data: List of cost rows with format [cost, date, service_name, currency]
        
        Returns:
            Dictionary with categorized costs and total
        """
        
        # Initialize all categories including the two new ones
        costs = {
            'Databricks': 0.0,
            'Virtual Machine': 0.0,
            'Storage': 0.0,
            'Bandwidth': 0.0,           
            'Virtual Network': 0.0,     
            'Others': 0.0,
            'Total': 0.0
        }
        
        for row in raw_data:
            cost = float(row[0])
            service_name = row[2] if len(row) > 2 else ''
            
            # Map Azure service names to our categories
            if service_name == 'Azure Databricks':
                costs['Databricks'] += cost
            elif service_name == 'Virtual Machines':
                costs['Virtual Machine'] += cost
            elif service_name == 'Storage':
                costs['Storage'] += cost
            elif service_name == 'Bandwidth':  
                costs['Bandwidth'] += cost
            elif service_name == 'Virtual Network':  
                costs['Virtual Network'] += cost
            else:
                # All unmapped services go to Others
                costs['Others'] += cost
            
            costs['Total'] += cost
        
        return costs
    
    @staticmethod
    def calculate_percentage_change(previous: float, current: float) -> float:
        """
        Calculate percentage change between two values.
        
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
        Determine which categories have data for a subscription.
        
        CHANGE #2: Updated to include new categories in the base list
        
        Logic:
        - Start with base categories (now includes Bandwidth and Virtual Network)
        - For 'main' subscription: check if Databricks has any costs
        - If no Databricks costs found in any day, exclude it from report
        - This keeps reports clean by only showing relevant categories
        
        Args:
            costs_list: List of cost dictionaries for each day
            subscription_name: Name of the subscription being processed
        
        Returns:
            List of category names to include in the report
        """
        
        # Base categories now include the two new ones
        base_categories = [
            'Databricks', 
            'Virtual Machine', 
            'Storage', 
            'Bandwidth',        # NEW
            'Virtual Network',  # NEW
            'Others'
        ]
        
        # Special handling for main subscription
        # Check if subscription has Databricks costs across all days
        if subscription_name.lower() == 'main':
            has_databricks = any(costs['Databricks'] > 0 for costs in costs_list)
            if not has_databricks:
                # Remove Databricks from categories if no costs found
                return [cat for cat in base_categories if cat != 'Databricks']
        
        return base_categories