"""
Azure Cost Data Fetching Service
"""
import requests
import time
from datetime import datetime
from typing import Optional, Dict, Any


class CostDataService:
    """Fetch cost data from Azure Cost Management API"""
    
    def __init__(self, access_token: str):
        self.access_token = access_token
    
    def get_cost_data_range(
        self, 
        subscription_id: str, 
        start_date: datetime, 
        end_date: datetime,
        retry_count: int = 0,
        max_retries: int = 3
    ) -> Optional[Dict[str, Any]]:
        """Get cost data for a date range"""
        
        usage_url = f'https://management.azure.com/subscriptions/{subscription_id}/providers/Microsoft.CostManagement/query?api-version=2023-03-01'
        
        usage_data = {
            'type': 'Usage',
            'timeframe': 'Custom',
            'timePeriod': {
                'from': start_date.strftime('%Y-%m-%dT00:00:00Z'),
                'to': end_date.strftime('%Y-%m-%dT23:59:59Z')
            },
            'dataset': {
                'granularity': 'Daily',
                'aggregation': {
                    'totalCost': {
                        'name': 'Cost',
                        'function': 'Sum'
                    }
                },
                'grouping': [
                    {
                        'type': 'Dimension',
                        'name': 'ResourceType'
                    }
                ]
            }
        }
        
        try:
            response = requests.post(
                usage_url,
                headers={'Authorization': f'Bearer {self.access_token}'},
                json=usage_data,
                timeout=30
            )
            
            # Handle rate limiting
            if response.status_code == 429:
                if retry_count < max_retries:
                    retry_after = int(response.headers.get('Retry-After', 2 ** retry_count))
                    print(f"Rate limit hit. Waiting {retry_after} seconds...")
                    time.sleep(retry_after)
                    return self.get_cost_data_range(
                        subscription_id, start_date, end_date, retry_count + 1, max_retries
                    )
                else:
                    raise Exception("Max retries reached due to rate limiting")
            
            response.raise_for_status()
            return response.json()['properties']
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error fetching cost data: {str(e)}")
    
    def parse_range_response(self, response_data: Dict[str, Any]) -> Dict[int, list]:
        """Parse the range API response and organize by date"""
        
        if not response_data or 'rows' not in response_data:
            return {}
        
        columns = response_data.get('columns', [])
        date_idx = next((i for i, col in enumerate(columns) if col['name'] == 'UsageDate'), 1)
        
        daily_data = {}
        for row in response_data['rows']:
            date = row[date_idx]
            if date not in daily_data:
                daily_data[date] = []
            daily_data[date].append(row)
        
        return daily_data