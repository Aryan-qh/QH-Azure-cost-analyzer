"""
Anomaly Detection Service

CHANGE: Updated to handle dynamic subscription lists
- Previously: Hardcoded list ['prod', 'dev', 'test', 'main']
- Now: Accepts any subscription dictionary provided by user

Logic remains the same for detection:
- Compare target date against rolling calendar average
- Flag anomalies based on threshold
- Return detailed results per service
"""
from datetime import datetime, timedelta
import calendar
from typing import Dict, List, Optional
from app.services.cost_data import CostDataService
from app.services.cost_processor import CostProcessorService


class AnomalyDetectorService:
    """
    Detect cost anomalies by comparing against rolling calendar averages.
    
    Rolling Calendar Logic:
    - If target is Dec 11, compares against Nov 1 to Nov 11 (11 days)
    - If target is Dec 30, compares against Nov 1 to Nov 30 (30 days)
    - This provides a month-over-month comparison for the same day-of-month
    """
    
    # Threshold for treating costs as effectively zero (1 cent)
    ZERO_THRESHOLD = 0.01
    
    def __init__(self, cost_data_service: CostDataService, cost_processor: CostProcessorService):
        self.cost_data_service = cost_data_service
        self.cost_processor = cost_processor
    
    def detect_anomalies(
        self,
        subscription_id: str,
        subscription_name: str,
        target_date: datetime,
        threshold_percent: float = 25.0
    ) -> Optional[Dict]:
        """
        Detect cost anomalies for a specific date using rolling calendar average.
        
        Args:
            subscription_id: Azure subscription ID
            subscription_name: Display name for subscription
            target_date: Date to check for anomalies
            threshold_percent: Percentage threshold for anomaly detection (default 25%)
        
        Returns:
            Dictionary containing anomaly detection results or None if no data
        """
        
        # Calculate rolling calendar average period
        target_day = target_date.day
        
        # Get previous month
        if target_date.month == 1:
            avg_month = 12
            avg_year = target_date.year - 1
        else:
            avg_month = target_date.month - 1
            avg_year = target_date.year
        
        # Start from 1st of previous month
        avg_start_date = datetime(avg_year, avg_month, 1)
        
        # End on same day number in previous month (or last day if day doesn't exist)
        try:
            avg_end_date = datetime(avg_year, avg_month, target_day)
        except ValueError:
            # Handle case where day doesn't exist in previous month (e.g., Jan 31 -> Feb 28)
            last_day = calendar.monthrange(avg_year, avg_month)[1]
            avg_end_date = datetime(avg_year, avg_month, last_day)
        
        print(f"\n{'='*60}")
        print(f"Anomaly Detection for {subscription_name.upper()}")
        print(f"Target Date: {target_date.strftime('%Y-%m-%d')} (Day {target_day})")
        print(f"Average Period: {avg_start_date.strftime('%Y-%m-%d')} to {avg_end_date.strftime('%Y-%m-%d')}")
        print(f"Days in average: {(avg_end_date - avg_start_date).days + 1}")
        print(f"{'='*60}\n")
        
        # Fetch data for average period
        avg_response_data = self.cost_data_service.get_cost_data_range(
            subscription_id, avg_start_date, avg_end_date
        )
        
        if not avg_response_data:
            print(f"WARNING: No data found for average period")
            return None
        
        avg_daily_data = self.cost_data_service.parse_range_response(avg_response_data)
        
        # Fetch data for target date
        target_response_data = self.cost_data_service.get_cost_data_range(
            subscription_id, target_date, target_date
        )
        
        if not target_response_data:
            print(f"WARNING: No data found for target date")
            return None
        
        target_daily_data = self.cost_data_service.parse_range_response(target_response_data)
        
        # Get target date data
        target_date_key = int(target_date.strftime('%Y%m%d'))
        target_rows = target_daily_data.get(target_date_key, [])
        
        if not target_rows:
            print(f"WARNING: No cost rows for target date key {target_date_key}")
            return None
        
        # Normalized row structure: [Cost, UsageDate, ServiceName, Currency]
        # Index 0: Cost, Index 1: UsageDate, Index 2: ServiceName, Index 3: Currency
        
        # Get all unique services from target date
        target_services = {}
        for row in target_rows:
            cost = float(row[0])
            service_name = row[2]
            if service_name in target_services:
                target_services[service_name] += cost
            else:
                target_services[service_name] = cost
        
        print(f"Found {len(target_services)} unique services on target date")
        
        # Calculate averages for each service from the rolling period
        service_averages = {}
        days_count = 0
        
        for date_key, rows in avg_daily_data.items():
            days_count += 1
            for row in rows:
                cost = float(row[0])
                service_name = row[2]
                if service_name in service_averages:
                    service_averages[service_name] += cost
                else:
                    service_averages[service_name] = cost
        
        # Calculate average by dividing by number of days
        if days_count > 0:
            for service in service_averages:
                service_averages[service] = service_averages[service] / days_count
        
        print(f"Calculated averages across {days_count} days")
        
        # Detect anomalies
        anomalies = []
        results = []
        
        for service_name, current_cost in target_services.items():
            avg_cost = service_averages.get(service_name, 0.0)
            
            # Calculate percentage change with special handling for very small values
            percent_change = self._calculate_safe_percentage_change(avg_cost, current_cost)
            
            # Only flag as anomaly if:
            # 1. Percentage change exceeds threshold, AND
            # 2. At least one of the costs is meaningful (> $0.01)
            is_meaningful_cost = (avg_cost >= self.ZERO_THRESHOLD or 
                                 current_cost >= self.ZERO_THRESHOLD)
            is_anomaly = percent_change > threshold_percent and is_meaningful_cost
            
            results.append({
                'service': service_name,
                'average_cost': round(avg_cost, 2),
                'current_cost': round(current_cost, 2),
                'percent_change': round(percent_change, 2),
                'is_anomaly': is_anomaly
            })
            
            if is_anomaly:
                anomalies.append({
                    'service': service_name,
                    'average_cost': round(avg_cost, 2),
                    'current_cost': round(current_cost, 2),
                    'percent_change': round(percent_change, 2)
                })
                print(f"  ⚠️  ANOMALY: {service_name} - ${current_cost:.2f} vs ${avg_cost:.2f} avg ({percent_change:+.2f}%)")
        
        # Sort results by current cost (descending)
        results.sort(key=lambda x: x['current_cost'], reverse=True)
        anomalies.sort(key=lambda x: x['current_cost'], reverse=True)
        
        print(f"\nResults: {len(results)} services, {len(anomalies)} anomalies detected\n")
        
        return {
            'subscription': subscription_name,
            'target_date': target_date.strftime('%Y-%m-%d'),
            'start_date': avg_start_date.strftime('%Y-%m-%d'),
            'end_date': avg_end_date.strftime('%Y-%m-%d'),
            'days_in_average': days_count,
            'threshold': threshold_percent,
            'results': results,
            'anomalies': anomalies,
            'has_anomalies': len(anomalies) > 0
        }
    
    def _calculate_safe_percentage_change(self, previous: float, current: float) -> float:
        """
        Calculate percentage change with special handling for very small values.
        
        Logic:
        - If both values are < $0.01, return 0% (ignore noise)
        - If previous is < $0.01 but current is >= $0.01, return 100%
        - Otherwise, calculate normal percentage change
        """
        
        # Both values are negligible - no meaningful change
        if previous < self.ZERO_THRESHOLD and current < self.ZERO_THRESHOLD:
            return 0.0
        
        # Previous was negligible but current is not - treat as 100% increase
        if previous < self.ZERO_THRESHOLD:
            return 100.0 if current > 0 else -100.0
        
        # Normal percentage calculation
        return ((current - previous) / previous) * 100
    
    def check_all_subscriptions(
        self,
        subscriptions: Dict[str, str],
        target_date: Optional[datetime] = None,
        threshold_percent: float = 25.0
    ) -> Dict:
        """
        Check all subscriptions for anomalies.
        
        CHANGE: Now accepts subscriptions dictionary as parameter
        - Previously: Used hardcoded subscription list from settings
        - Now: Accepts any dictionary of {name: id} pairs
        
        Args:
            subscriptions: Dict mapping subscription names to IDs
            target_date: Date to check (defaults to yesterday)
            threshold_percent: Anomaly threshold
        
        Returns:
            Dictionary with results for all subscriptions and summary
        """
        
        if target_date is None:
            target_date = datetime.now() - timedelta(days=1)
        
        all_results = {}
        
        # Process each subscription dynamically
        for sub_name, sub_id in subscriptions.items():
            print(f"\nProcessing subscription: {sub_name} ({sub_id[:8]}...)")
            
            try:
                result = self.detect_anomalies(
                    sub_id,
                    sub_name,
                    target_date,
                    threshold_percent
                )
                
                if result:
                    all_results[sub_name] = result
                    print(f"✓ Completed {sub_name}")
                else:
                    print(f"⚠ No data for {sub_name}")
            
            except Exception as e:
                print(f"✗ Error processing {sub_name}: {str(e)}")
                # Continue with other subscriptions even if one fails
                continue
        
        # Generate summary
        subscriptions_with_anomalies = [
            sub_name for sub_name, result in all_results.items()
            if result['has_anomalies']
        ]
        
        return {
            'target_date': target_date.strftime('%Y-%m-%d'),
            'threshold': threshold_percent,
            'subscriptions': all_results,
            'summary': {
                'total_subscriptions': len(all_results),
                'subscriptions_with_anomalies': len(subscriptions_with_anomalies),
                'anomaly_detected': len(subscriptions_with_anomalies) > 0
            }
        }