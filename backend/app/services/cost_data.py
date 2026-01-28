"""
Azure Cost Data Fetching Service - Fixed Version

FIXES APPLIED:
1. Added flexible column name detection for monthly queries
2. Enhanced error messages to show actual available columns
3. Made parse_monthly_response more robust with fallback column names
4. Better handling of edge cases in grouped responses

ISSUE RESOLVED:
Monthly queries were failing because Azure API uses different column names
(e.g., 'BillingMonth' instead of 'UsageDate' for monthly granularity)
"""
import requests
import time
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List
from enum import Enum


class Granularity(str, Enum):
    """Cost data granularity options"""
    DAILY = "Daily"
    MONTHLY = "Monthly"


class GroupingDimension(str, Enum):
    """Available dimensions for grouping cost data"""
    SERVICE_NAME = "ServiceName"
    RESOURCE_GROUP = "ResourceGroupName"
    METER_CATEGORY = "MeterCategory"
    METER_SUBCATEGORY = "MeterSubCategory"
    RESOURCE_TYPE = "ResourceType"
    RESOURCE_LOCATION = "ResourceLocation"


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
        """
        Get cost data for a date range with DAILY granularity.
        
        UNCHANGED: Maintains backward compatibility with existing code.
        Limited to 90 days for daily granularity.
        """
        
        # Validate date range for daily granularity (max 90 days)
        if (end_date - start_date).days > 90:
            raise ValueError("Daily granularity is limited to 90 days. Use get_monthly_costs for longer periods.")
        
        return self._fetch_costs(
            subscription_id=subscription_id,
            start_date=start_date,
            end_date=end_date,
            granularity=Granularity.DAILY,
            grouping=[GroupingDimension.SERVICE_NAME],
            retry_count=retry_count,
            max_retries=max_retries
        )
    
    def get_monthly_costs(
        self,
        subscription_id: str,
        start_date: datetime,
        end_date: datetime,
        grouping: List[GroupingDimension] = None,
        retry_count: int = 0,
        max_retries: int = 3
    ) -> Optional[Dict[str, Any]]:
        """
        Get cost data with MONTHLY granularity.
        
        Supports up to 12 months of data.
        """
        
        # Validate date range for monthly granularity (max 12 months)
        months_diff = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month
        if months_diff > 12:
            raise ValueError("Monthly granularity is limited to 12 months.")
        
        if grouping is None:
            grouping = [GroupingDimension.SERVICE_NAME]
        
        return self._fetch_costs(
            subscription_id=subscription_id,
            start_date=start_date,
            end_date=end_date,
            granularity=Granularity.MONTHLY,
            grouping=grouping,
            retry_count=retry_count,
            max_retries=max_retries
        )
    
    def get_costs_by_resource_group(
        self,
        subscription_id: str,
        start_date: datetime,
        end_date: datetime,
        granularity: Granularity = Granularity.MONTHLY,
        retry_count: int = 0,
        max_retries: int = 3
    ) -> Optional[Dict[str, Any]]:
        """Get costs grouped by both ServiceName and ResourceGroupName."""
        
        return self._fetch_costs(
            subscription_id=subscription_id,
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
            grouping=[GroupingDimension.SERVICE_NAME, GroupingDimension.RESOURCE_GROUP],
            retry_count=retry_count,
            max_retries=max_retries
        )
    
    def get_costs_by_dimension(
        self,
        subscription_id: str,
        start_date: datetime,
        end_date: datetime,
        grouping: List[GroupingDimension],
        granularity: Granularity = Granularity.MONTHLY,
        retry_count: int = 0,
        max_retries: int = 3
    ) -> Optional[Dict[str, Any]]:
        """Get costs grouped by custom dimensions."""
        
        return self._fetch_costs(
            subscription_id=subscription_id,
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
            grouping=grouping,
            retry_count=retry_count,
            max_retries=max_retries
        )
    
    def _fetch_costs(
        self,
        subscription_id: str,
        start_date: datetime,
        end_date: datetime,
        granularity: Granularity,
        grouping: List[GroupingDimension],
        retry_count: int = 0,
        max_retries: int = 3
    ) -> Optional[Dict[str, Any]]:
        """Core method to fetch costs from Azure Cost Management API."""
        
        print(f"\nDEBUG: _fetch_costs called")
        print(f"  subscription_id: {subscription_id}")
        print(f"  start_date: {start_date.strftime('%Y-%m-%d')}")
        print(f"  end_date: {end_date.strftime('%Y-%m-%d')}")
        print(f"  granularity: {granularity.value}")
        print(f"  grouping: {[g.value for g in grouping]}")
        
        usage_url = f'https://management.azure.com/subscriptions/{subscription_id}/providers/Microsoft.CostManagement/query?api-version=2023-03-01'
        
        # Build grouping structure
        grouping_config = [
            {
                'type': 'Dimension',
                'name': dimension.value
            }
            for dimension in grouping
        ]
        
        # Build request body
        usage_data = {
            'type': 'Usage',
            'timeframe': 'Custom',
            'timePeriod': {
                'from': start_date.strftime('%Y-%m-%dT00:00:00Z'),
                'to': end_date.strftime('%Y-%m-%dT23:59:59Z')
            },
            'dataset': {
                'granularity': granularity.value,
                'aggregation': {
                    'totalCost': {
                        'name': 'Cost',
                        'function': 'Sum'
                    }
                },
                'grouping': grouping_config
            }
        }
        
        print(f"DEBUG: Request body:")
        print(json.dumps(usage_data, indent=2))
        
        try:
            print(f"DEBUG: Sending POST request to Azure...")
            response = requests.post(
                usage_url,
                headers={'Authorization': f'Bearer {self.access_token}'},
                json=usage_data,
                timeout=30
            )
            
            print(f"DEBUG: Response status code: {response.status_code}")
            
            # Handle rate limiting with exponential backoff
            if response.status_code == 429:
                if retry_count < max_retries:
                    retry_after = min(
                        int(response.headers.get('Retry-After', 2 ** retry_count)),
                        60
                    )
                    print(f"Rate limit hit. Waiting {retry_after} seconds... (Retry {retry_count + 1}/{max_retries})")
                    time.sleep(retry_after)
                    return self._fetch_costs(
                        subscription_id, start_date, end_date, granularity, 
                        grouping, retry_count + 1, max_retries
                    )
                else:
                    raise Exception("Max retries reached due to rate limiting")
            
            if response.status_code != 200:
                print(f"DEBUG: Error response body:")
                print(response.text)
            
            response.raise_for_status()
            
            response_json = response.json()
            print(f"DEBUG: Response received successfully")
            print(f"  Response keys: {list(response_json.keys())}")
            
            properties = response_json['properties']
            print(f"  Properties keys: {list(properties.keys())}")
            print(f"  Number of rows: {len(properties.get('rows', []))}")
            print(f"  Number of columns: {len(properties.get('columns', []))}")
            
            # Add metadata for easier processing
            properties['_metadata'] = {
                'granularity': granularity.value,
                'grouping': [g.value for g in grouping],
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d')
            }
            
            return properties
            
        except requests.exceptions.RequestException as e:
            print(f"DEBUG: Request exception: {type(e).__name__}")
            print(f"DEBUG: Error message: {str(e)}")
            raise Exception(f"Error fetching cost data: {str(e)}")
    
    def _get_column_indices(self, columns: list) -> Dict[str, int]:
        """
        Get column indices dynamically from API response.
        
        Returns dictionary mapping column names to indices.
        """
        
        indices = {}
        for idx, col in enumerate(columns):
            indices[col['name']] = idx
        
        # Validate required columns exist
        required_cols = ['Cost']
        for col in required_cols:
            if col not in indices:
                raise ValueError(f"Missing required column: {col}")
        
        return indices
    
    def _find_date_column(self, columns: list) -> Optional[int]:
        """
        FIXED: Find date column index with fallback options.
        
        Azure API uses different column names:
        - Daily granularity: 'UsageDate'
        - Monthly granularity: 'BillingMonth' or 'UsageDate'
        
        Returns:
            Column index if found, None otherwise
        """
        # Try common date column names in order of preference
        date_column_names = ['UsageDate', 'BillingMonth', 'Date', 'CostDate']
        
        for col_idx, col in enumerate(columns):
            if col['name'] in date_column_names:
                return col_idx
        
        return None
    
    def _find_service_column(self, columns: list) -> Optional[int]:
        """
        FIXED: Find service name column index with fallback options.
        
        Returns:
            Column index if found, None otherwise
        """
        # Try common service column names
        service_column_names = ['ServiceName', 'ServiceFamily', 'Service']
        
        for col_idx, col in enumerate(columns):
            if col['name'] in service_column_names:
                return col_idx
        
        return None
    
    def parse_range_response(self, response_data: Dict[str, Any]) -> Dict[int, list]:
        """
        Parse the range API response and organize by date (DAILY granularity).
        
        UNCHANGED: Maintains backward compatibility.
        """
        
        if not response_data or 'rows' not in response_data:
            return {}
        
        columns = response_data.get('columns', [])
        indices = self._get_column_indices(columns)
        
        # Required indices
        cost_idx = indices['Cost']
        date_idx = self._find_date_column(columns)
        service_idx = self._find_service_column(columns)
        currency_idx = indices.get('Currency', -1)
        
        if date_idx is None or service_idx is None:
            # ENHANCED: Show what columns are actually available
            available_columns = [col['name'] for col in columns]
            raise ValueError(
                f"Missing required columns. Available columns: {available_columns}. "
                f"Expected date column (UsageDate) and service column (ServiceName)."
            )
        
        daily_data = {}
        
        for row in response_data['rows']:
            date = row[date_idx]
            cost = float(row[cost_idx])
            service_name = row[service_idx]
            currency = row[currency_idx] if currency_idx >= 0 and len(row) > currency_idx else 'USD'
            
            # Create normalized row structure
            normalized_row = [cost, date, service_name, currency]
            
            if date not in daily_data:
                daily_data[date] = []
            daily_data[date].append(normalized_row)
        
        return daily_data
    
    def parse_monthly_response(self, response_data: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
        """
        FIXED: Parse monthly cost data response with robust date parsing.
        
        ISSUE FIXED: Azure API returns dates in different formats:
        - Sometimes: 20241201 (integer YYYYMMDD)
        - Sometimes: '2025-11-01T00:00:00' (ISO datetime string)
        
        This function now handles both formats correctly.
        
        Returns:
            Dictionary mapping dates to service costs
            Format: {
                'YYYYMM': {
                    'ServiceName1': cost1,
                    'ServiceName2': cost2,
                    ...
                }
            }
        """
        
        print("\nDEBUG: parse_monthly_response called")
        
        if not response_data or 'rows' not in response_data:
            print("DEBUG: No response_data or no 'rows' key")
            return {}
        
        columns = response_data.get('columns', [])
        
        # Debug: Print available columns
        available_columns = [col['name'] for col in columns]
        print(f"DEBUG: Available columns in monthly response: {available_columns}")
        
        indices = self._get_column_indices(columns)
        print(f"DEBUG: Column indices: {indices}")
        
        # Get column indices with fallback
        cost_idx = indices['Cost']
        date_idx = self._find_date_column(columns)
        service_idx = self._find_service_column(columns)
        
        print(f"DEBUG: Found indices - cost: {cost_idx}, date: {date_idx}, service: {service_idx}")
        
        if date_idx is None or service_idx is None:
            # ENHANCED: Provide detailed error message
            error_msg = (
                f"Missing required columns for monthly data. "
                f"Available columns: {available_columns}. "
                f"Expected: date column (UsageDate/BillingMonth) and service column (ServiceName)"
            )
            print(f"DEBUG ERROR: {error_msg}")
            raise ValueError(error_msg)
        
        rows = response_data.get('rows', [])
        print(f"DEBUG: Processing {len(rows)} rows")
        
        monthly_data = {}
        
        for idx, row in enumerate(rows):
            if idx < 3:  # Print first 3 rows for debugging
                print(f"DEBUG: Row {idx}: {row}")
            
            # Handle both date formats
            date_value = row[date_idx]
            cost = float(row[cost_idx])
            service_name = row[service_idx]
            
            # FIXED: Parse date value correctly based on type
            month_key = self._parse_date_to_month_key(date_value)
            
            if not month_key:
                print(f"WARNING: Could not parse date: {date_value}, skipping row")
                continue
            
            if month_key not in monthly_data:
                monthly_data[month_key] = {}
            
            if service_name in monthly_data[month_key]:
                monthly_data[month_key][service_name] += cost
            else:
                monthly_data[month_key][service_name] = cost
        
        print(f"DEBUG: Parsed {len(monthly_data)} unique months")
        for month_key in sorted(monthly_data.keys()):
            service_count = len(monthly_data[month_key])
            total_cost = sum(monthly_data[month_key].values())
            print(f"  {month_key}: {service_count} services, ${total_cost:.2f} total")
        
        return monthly_data


    def _parse_date_to_month_key(self, date_value: Any) -> Optional[str]:
        """
        NEW METHOD: Parse date value to YYYYMM format.
        
        Handles multiple date formats from Azure API:
        1. Integer: 20241201 → "202412"
        2. ISO datetime string: "2025-11-01T00:00:00" → "202511"
        3. Date string: "2025-11-01" → "202511"
        
        Returns:
            Month key in YYYYMM format (e.g., "202511")
            None if parsing fails
        """
        
        try:
            # Case 1: Integer format (YYYYMMDD)
            if isinstance(date_value, int):
                date_str = str(date_value)
                if len(date_str) >= 6:
                    return date_str[:6]  # Take YYYYMM
                else:
                    print(f"WARNING: Integer date too short: {date_value}")
                    return None
            
            # Case 2: String format (ISO datetime or date)
            if isinstance(date_value, str):
                # Try to parse as datetime
                # Handles both "2025-11-01T00:00:00" and "2025-11-01"
                if 'T' in date_value:
                    # ISO datetime format
                    dt = datetime.strptime(date_value.split('T')[0], '%Y-%m-%d')
                elif '-' in date_value:
                    # Simple date format
                    dt = datetime.strptime(date_value, '%Y-%m-%d')
                else:
                    # Try as YYYYMMDD string
                    if len(date_value) >= 6:
                        return date_value[:6]
                    else:
                        print(f"WARNING: Unknown string date format: {date_value}")
                        return None
                
                # Convert datetime to YYYYMM
                return dt.strftime('%Y%m')
            
            # Unknown type
            print(f"WARNING: Unknown date type: {type(date_value)}, value: {date_value}")
            return None
            
        except Exception as e:
            print(f"ERROR: Failed to parse date {date_value}: {e}")
            return None
    
    def parse_grouped_response(
        self, 
        response_data: Dict[str, Any],
        grouping_dimensions: List[str]
    ) -> List[Dict[str, Any]]:
        """
        FIXED: Parse response with multiple grouping dimensions.
        
        Enhanced with better column detection and error handling.
        """
        
        if not response_data or 'rows' not in response_data:
            return []
        
        columns = response_data.get('columns', [])
        available_columns = [col['name'] for col in columns]
        
        print(f"DEBUG: Available columns in grouped response: {available_columns}")
        
        indices = self._get_column_indices(columns)
        
        # Find date column if present
        date_idx = self._find_date_column(columns)
        
        results = []
        
        for row in response_data['rows']:
            item = {
                'cost': float(row[indices['Cost']])
            }
            
            # Add date if present
            if date_idx is not None:
                item['date'] = row[date_idx]
            
            # Add all grouping dimensions (with flexible lookup)
            for dim in grouping_dimensions:
                # Try exact match first
                if dim in indices:
                    item[dim] = row[indices[dim]]
                else:
                    # Try to find similar column
                    # For example, 'ServiceName' might also appear as 'Service'
                    found = False
                    for col_name, col_idx in indices.items():
                        if dim.lower() in col_name.lower() or col_name.lower() in dim.lower():
                            item[dim] = row[col_idx]
                            found = True
                            break
                    
                    if not found:
                        print(f"WARNING: Dimension '{dim}' not found in columns")
                        item[dim] = 'Unknown'
            
            # Add currency if present
            if 'Currency' in indices:
                item['currency'] = row[indices['Currency']]
            else:
                item['currency'] = 'USD'
            
            results.append(item)
        
        print(f"DEBUG: Parsed {len(results)} grouped records")
        return results