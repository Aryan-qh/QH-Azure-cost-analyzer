"""
Azure Cost Data Fetching Service
"""
import requests
import time
from datetime import datetime
from typing import Optional, Dict, Any, Tuple


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
                        'name': 'ServiceName'
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
            
            # Handle rate limiting with proper retry logic
            if response.status_code == 429:
                if retry_count < max_retries:
                    # Respect Retry-After header, with a max cap of 60 seconds
                    retry_after = min(
                        int(response.headers.get('Retry-After', 2 ** retry_count)),
                        60
                    )
                    print(f"Rate limit hit. Waiting {retry_after} seconds... (Retry {retry_count + 1}/{max_retries})")
                    time.sleep(retry_after)
                    return self.get_cost_data_range(
                        subscription_id, start_date, end_date, retry_count + 1, max_retries
                    )
                else:
                    raise Exception("Max retries reached due to rate limiting")
            
            response.raise_for_status()
            properties = response.json()['properties']
            
            return properties
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Error fetching cost data: {str(e)}")
    
    def _get_column_indices(self, columns: list) -> Tuple[int, int, int, int]:
        """Get column indices dynamically from API response"""
        
        indices = {}
        for idx, col in enumerate(columns):
            indices[col['name']] = idx
        
        # Validate required columns exist
        required_cols = ['UsageDate', 'ServiceName', 'Cost']
        for col in required_cols:
            if col not in indices:
                raise ValueError(f"Missing required column: {col}")
        
        return (
            indices['Cost'],
            indices['UsageDate'],
            indices['ServiceName'],
            indices.get('Currency', -1)  # Currency might not always be present
        )
    
    def parse_range_response(self, response_data: Dict[str, Any]) -> Dict[int, list]:
        """
        Parse the range API response and organize by date.
        Returns normalized data structure: Dict[date_key, List[normalized_rows]]
        Each normalized_row: [cost, date, service_name, currency]
        """
        
        if not response_data or 'rows' not in response_data:
            return {}
        
        columns = response_data.get('columns', [])
        
        # Get column indices dynamically
        cost_idx, date_idx, service_idx, currency_idx = self._get_column_indices(columns)
        
        print(f"DEBUG: Column mapping - cost_idx={cost_idx}, date_idx={date_idx}, "
              f"service_idx={service_idx}, currency_idx={currency_idx}")
        
        daily_data = {}
        
        for row in response_data['rows']:
            # Extract values using correct indices
            date = row[date_idx]
            cost = float(row[cost_idx])
            service_name = row[service_idx]
            currency = row[currency_idx] if currency_idx >= 0 and len(row) > currency_idx else 'USD'
            
            # Create normalized row structure
            # [0: Cost, 1: Date, 2: ServiceName, 3: Currency]
            normalized_row = [cost, date, service_name, currency]
            
            if date not in daily_data:
                daily_data[date] = []
            daily_data[date].append(normalized_row)
        
        return daily_data