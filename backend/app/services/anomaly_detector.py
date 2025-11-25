"""
Anomaly Detection Service
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from app.services.cost_data import CostDataService
from app.services.cost_processor import CostProcessorService


class AnomalyDetectorService:
    """Detect cost anomalies by comparing against historical averages"""
    
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
        """Detect cost anomalies for a specific date"""
        
        # Calculate date range: 7 days before target + target date
        end_date = target_date
        start_date = target_date - timedelta(days=7)
        
        # Fetch data
        response_data = self.cost_data_service.get_cost_data_range(
            subscription_id, start_date, end_date
        )
        
        if not response_data:
            return None
        
        daily_data = self.cost_data_service.parse_range_response(response_data)
        
        # Process costs for each day
        weekly_costs = []
        target_costs = None
        
        for i in range(8):  # 7 days for average + 1 target day
            date = start_date + timedelta(days=i)
            date_key = int(date.strftime('%Y%m%d'))
            day_rows = daily_data.get(date_key, [])
            costs = self.cost_processor.process_cost_data(day_rows)
            
            if i < 7:  # First 7 days for average
                weekly_costs.append(costs)
            else:  # 8th day is target
                target_costs = costs
        
        # Calculate averages
        categories = ['Databricks', 'Virtual Machine', 'Storage', 'Others', 'Total']
        averages = {}
        
        for category in categories:
            avg = sum(day[category] for day in weekly_costs) / 7
            averages[category] = avg
        
        # Detect anomalies
        anomalies = []
        results = []
        
        for category in categories:
            avg_cost = averages[category]
            current_cost = target_costs[category]
            
            percent_change = self.cost_processor.calculate_percentage_change(
                avg_cost, current_cost
            )
            
            is_anomaly = percent_change > threshold_percent
            
            results.append({
                'category': category,
                'average_cost': round(avg_cost, 2),
                'current_cost': round(current_cost, 2),
                'percent_change': round(percent_change, 2),
                'is_anomaly': is_anomaly
            })
            
            if is_anomaly:
                anomalies.append({
                    'category': category,
                    'average_cost': round(avg_cost, 2),
                    'current_cost': round(current_cost, 2),
                    'percent_change': round(percent_change, 2)
                })
        
        return {
            'subscription': subscription_name,
            'target_date': target_date.strftime('%Y-%m-%d'),
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'threshold': threshold_percent,
            'results': results,
            'anomalies': anomalies,
            'has_anomalies': len(anomalies) > 0
        }
    
    def check_all_subscriptions(
        self,
        subscriptions: Dict[str, str],
        target_date: Optional[datetime] = None,
        threshold_percent: float = 25.0
    ) -> Dict:
        """Check all subscriptions for anomalies"""
        
        if target_date is None:
            target_date = datetime.now() - timedelta(days=1)
        
        all_results = {}
        
        for sub_name in ['prod', 'dev', 'test', 'main']:
            result = self.detect_anomalies(
                subscriptions[sub_name],
                sub_name,
                target_date,
                threshold_percent
            )
            
            if result:
                all_results[sub_name] = result
        
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