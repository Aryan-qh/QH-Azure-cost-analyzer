"""
Cost Data Processing Service
"""
from typing import Dict, List


class CostProcessorService:
    """Process and categorize cost data"""
    
    @staticmethod
    def process_cost_data(raw_data: List[list]) -> Dict[str, float]:
        """Process raw cost data into categories"""
        
        costs = {
            'Databricks': 0.0,
            'Virtual Machine': 0.0,
            'Storage': 0.0,
            'Others': 0.0,
            'Total': 0.0
        }
        
        for row in raw_data:
            cost = float(row[0])
            resource_type = row[2].lower() if len(row) > 2 else ''
            
            if 'databricks/workspaces' in resource_type or 'databricks/workspace' in resource_type:
                costs['Databricks'] += cost
            elif 'compute/virtualmachines' in resource_type or 'microsoft.compute/virtualmachines' in resource_type:
                costs['Virtual Machine'] += cost
            elif 'storage/storageaccounts' in resource_type or 'microsoft.storage/storageaccounts' in resource_type:
                costs['Storage'] += cost
            else:
                costs['Others'] += cost
            
            costs['Total'] += cost
        
        return costs
    
    @staticmethod
    def calculate_percentage_change(previous: float, current: float) -> float:
        """Calculate percentage change between two values"""
        
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        
        return ((current - previous) / previous) * 100
    
    @staticmethod
    def get_relevant_categories(costs_list: List[Dict[str, float]], subscription_name: str) -> List[str]:
        """Determine which categories have data for a subscription"""
        
        base_categories = ['Databricks', 'Virtual Machine', 'Storage', 'Others']
        
        # Check if subscription has Databricks costs
        if subscription_name.lower() == 'main':
            has_databricks = any(costs['Databricks'] > 0 for costs in costs_list)
            if not has_databricks:
                return ['Virtual Machine', 'Storage', 'Others']
        
        return base_categories