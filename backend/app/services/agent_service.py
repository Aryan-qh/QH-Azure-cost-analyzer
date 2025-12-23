"""
AI Agent Service - IMPROVED VERSION with Enhanced Empty Data Handling

KEY IMPROVEMENTS:
1. All tools now return user-friendly messages when no data is found
2. Clear differentiation between "no data" vs "zero costs"
3. Better error messages with actionable guidance
4. Enhanced system prompt to guide agent on empty data responses
5. Consistent response format across all tools

CHANGES MADE:
- Updated get_cost_summary: Added "no_data_found" flag and clear messages
- Updated get_monthly_cost_summary: Better empty data communication
- Updated detect_anomalies: Clear messages when no data available
- Updated compare_subscription_costs: Helpful response when no matching costs
- Enhanced system prompt: Added section on handling empty data scenarios
- All tools now include data_status field: "success", "no_data", "partial", "error"
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
import calendar
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from app.services.azure_auth import AzureAuthService
from app.services.cost_data import CostDataService, Granularity, GroupingDimension
from app.services.cost_processor import CostProcessorService
from app.services.anomaly_detector import AnomalyDetectorService
from app.services.configuration_manager import UserConfiguration


class AgentService:
    """LangChain-based AI Agent for Azure cost analysis with improved data handling."""
    
    def __init__(self, user_config: UserConfiguration):
        self.user_config = user_config
        self.llm = ChatOpenAI(
            model="gpt-4-turbo-preview",
            temperature=0,
            max_tokens=4096
        )
        self.tools = self._create_tools()
        self.agent = self._create_agent()
    
    def _create_agent(self) -> AgentExecutor:
        """Create LangChain agent with enhanced system prompt."""
        
        now = datetime.now()
        current_month = now.strftime('%Y-%m')
        current_month_num = now.month
        current_year = now.year
        prev_month = f"{now.year - 1}-12" if now.month == 1 else f"{now.year}-{now.month - 1:02d}"
        
        system_prompt = """You are an AI assistant for Azure cost analysis with a focus on clear communication about data availability.

**CRITICAL DATE HANDLING:**

For specific months: get_monthly_cost_summary with start_month="YYYY-MM", num_months=1
- "costs in November 2024" → start_month="2024-11", num_months=1
- "costs for December 2024" → start_month="2024-12", num_months=1

For relative periods: get_monthly_cost_summary with num_months=N
- "last 6 months" → num_months=6 (ends at current month)
- "last 3 months" → num_months=3

For year-to-date queries: calculate months from January to current
- "costs for 2024" → num_months={months_in_year} (January through {current_month})
- "year to date" → num_months={months_in_year}

For comparisons: use compare_subscription_costs
- "compare Virtual Machines" → resource_type="Virtual Machines", num_months=2

**Current context:**
- Today's date: {current_date}
- Current month: {current_month} (month #{current_month_num} of {current_year})
- Previous month: {prev_month}
- Available subscriptions: {subscriptions}

**HANDLING EMPTY DATA (VERY IMPORTANT):**

Tool responses now include a "data_status" field with these values:
- "success": Data was found and returned
- "no_data": No cost data exists for the requested period
- "partial": Some subscriptions have data, others don't
- "error": Technical error occurred

When you receive "no_data" or empty results:
1. **Be explicit and helpful**: "There were no costs recorded for [subscription] in [period]."
2. **Distinguish zero from missing**: 
   - Zero costs: "The costs were $0.00" (costs exist but are zero)
   - No data: "No cost data was recorded" (no data in Azure)
3. **Suggest alternatives**: "Would you like to check a different time period or subscription?"
4. **For partial data**: Clearly state which subscriptions have data and which don't

**Examples of good responses:**

❌ Bad: "Here are the costs: []"
✅ Good: "I checked November 2024 for the Production subscription, but there were no costs recorded during that period. This could mean either no resources were running, or data hasn't been synced yet. Would you like me to check a different month?"

❌ Bad: "No results found"
✅ Good: "I found data for 2 of your 3 subscriptions:
- Production: $1,234.56
- Development: $567.89
- Test: No cost data available for this period"

❌ Bad: "Error: no data"
✅ Good: "There are no Virtual Machines costs to compare across subscriptions for November 2024. This means none of your subscriptions had VM charges during this period."

**Data validation rules:**
- Always check response["data_status"] before presenting results
- If data_status is "no_data", explain clearly what this means
- If data_status is "partial", show which parts have data
- Never say "I don't have access to data" - you do have access, the data just might not exist
- Always offer to help with alternative queries when data is missing

**Important notes:**
- For year-to-date {current_year}, use num_months={months_in_year}
- This covers January {current_year} through {current_month}
- Maximum 12 months per query for monthly data
- If date format wrong, explain correct format YYYY-MM
""".format(
            current_date=now.strftime('%Y-%m-%d'),
            current_month=current_month,
            current_month_num=current_month_num,
            current_year=current_year,
            prev_month=prev_month,
            months_in_year=current_month_num,
            subscriptions=", ".join([sub.name for sub in self.user_config.subscriptions])
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        agent = create_tool_calling_agent(self.llm, self.tools, prompt)
        return AgentExecutor(agent=agent, tools=self.tools, verbose=True, 
                           handle_parsing_errors=True, max_iterations=10)
    
    def _create_tools(self) -> List:
        """Create all 7 tools with improved empty data handling."""
        
        user_config = self.user_config
        
        @tool
        def get_subscription_list() -> str:
            """Get list of configured Azure subscriptions."""
            subs = [{"name": s.name, "id": s.id[:8] + "..."} for s in user_config.subscriptions]
            return json.dumps({
                "data_status": "success",
                "subscriptions": subs, 
                "count": len(subs)
            }, indent=2)
        
        @tool
        def get_cost_summary(
            subscription_names: List[str], 
            num_days: Optional[int] = None,
            start_date: Optional[str] = None,
            end_date: Optional[str] = None
        ) -> str:
            """
            Get DAILY cost data (max 90 days).
            
            Returns data_status field to indicate if data was found.
            """
            
            if start_date and end_date:
                try:
                    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                    end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                    if start_dt > end_dt:
                        return json.dumps({
                            "data_status": "error",
                            "error": "start_date must be before end_date"
                        })
                    if (end_dt - start_dt).days > 90:
                        return json.dumps({
                            "data_status": "error",
                            "error": "Max 90 days for daily data. Use get_monthly_cost_summary for longer periods."
                        })
                except ValueError:
                    return json.dumps({
                        "data_status": "error",
                        "error": "Invalid date format. Use YYYY-MM-DD (e.g., 2024-12-15)"
                    })
            elif num_days:
                if not 1 <= num_days <= 90:
                    return json.dumps({
                        "data_status": "error",
                        "error": "num_days must be 1-90"
                    })
                end_dt = datetime.now() - timedelta(days=1)
                start_dt = end_dt - timedelta(days=num_days - 1)
            else:
                num_days = 7
                end_dt = datetime.now() - timedelta(days=1)
                start_dt = end_dt - timedelta(days=6)
            
            auth_service = AzureAuthService(
                user_config.tenant_id, user_config.client_id, user_config.client_secret
            )
            
            try:
                access_token = auth_service.get_access_token()
            except Exception as e:
                return json.dumps({
                    "data_status": "error",
                    "error": f"Authentication failed: {str(e)}"
                })
            
            cost_data_service = CostDataService(access_token)
            cost_processor = CostProcessorService()
            results = {}
            has_any_data = False
            
            for sub in user_config.subscriptions:
                if sub.name in subscription_names:
                    try:
                        response_data = cost_data_service.get_cost_data_range(sub.id, start_dt, end_dt)
                        
                        if not response_data or not response_data.get('rows'):
                            results[sub.name] = {
                                "data_status": "no_data",
                                "message": f"No cost data recorded for {sub.name} during this period",
                                "period": f"{start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')}",
                                "daily_costs": []
                            }
                            continue
                        
                        daily_data = cost_data_service.parse_range_response(response_data)
                        
                        if not daily_data:
                            results[sub.name] = {
                                "data_status": "no_data",
                                "message": f"No cost data found after parsing for {sub.name}",
                                "period": f"{start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')}",
                                "daily_costs": []
                            }
                            continue
                        
                        daily_costs = []
                        has_data_for_period = False
                        
                        for i in range((end_dt - start_dt).days + 1):
                            date = start_dt + timedelta(days=i)
                            date_key = int(date.strftime('%Y%m%d'))
                            rows = daily_data.get(date_key, [])
                            costs = cost_processor.process_cost_data(rows)
                            
                            if costs['Total'] > 0:
                                has_data_for_period = True
                            
                            daily_costs.append({
                                "date": date.strftime('%Y-%m-%d'),
                                "costs": costs,
                                "has_data": len(rows) > 0
                            })
                        
                        results[sub.name] = {
                            "data_status": "success" if has_data_for_period else "no_data",
                            "daily_costs": daily_costs,
                            "period": f"{start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')}",
                            "total_days": len(daily_costs),
                            "days_with_costs": sum(1 for d in daily_costs if d['costs']['Total'] > 0)
                        }
                        
                        if has_data_for_period:
                            has_any_data = True
                            
                    except Exception as e:
                        results[sub.name] = {
                            "data_status": "error",
                            "error": str(e)
                        }
            
            # Add overall status
            if not results:
                overall_status = "error"
                message = "No subscriptions matched the provided names"
            elif not has_any_data:
                overall_status = "no_data"
                message = "No cost data found for any subscription in the requested period"
            elif all(r.get("data_status") == "success" for r in results.values()):
                overall_status = "success"
                message = "Cost data retrieved successfully"
            else:
                overall_status = "partial"
                message = "Some subscriptions have data, others do not"
            
            return json.dumps({
                "data_status": overall_status,
                "message": message,
                "subscriptions": results,
                "query_info": {
                    "period": f"{start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')}",
                    "days_requested": (end_dt - start_dt).days + 1
                }
            }, indent=2)
        
        @tool
        def get_monthly_cost_summary(
            subscription_names: List[str],
            num_months: int = 6,
            start_month: Optional[str] = None
        ) -> str:
            """
            Get MONTHLY costs (max 12 months).
            
            IMPROVED: Now clearly indicates when no data is found vs when costs are zero.
            """
            
            if not 1 <= num_months <= 12:
                return json.dumps({
                    "data_status": "error",
                    "error": "num_months must be 1-12"
                })
            
            # Determine the date range
            if start_month:
                try:
                    target_dt = datetime.strptime(start_month, '%Y-%m')
                except ValueError:
                    return json.dumps({
                        "data_status": "error",
                        "error": "Invalid format. Use YYYY-MM (e.g., '2024-11')",
                        "example": "start_month='2024-11'"
                    })
                
                range_start_dt = target_dt.replace(day=1)
                last_day = calendar.monthrange(target_dt.year, target_dt.month)[1]
                end_dt = target_dt.replace(day=last_day)
                actual_months = 1
            else:
                current_dt = datetime.now().replace(day=1)
                last_day = calendar.monthrange(current_dt.year, current_dt.month)[1]
                end_dt = current_dt.replace(day=last_day)
                
                year, month = current_dt.year, current_dt.month - num_months + 1
                while month <= 0:
                    month += 12
                    year -= 1
                
                range_start_dt = datetime(year, month, 1)
                actual_months = num_months
            
            auth_service = AzureAuthService(
                user_config.tenant_id, user_config.client_id, user_config.client_secret
            )
            
            try:
                access_token = auth_service.get_access_token()
            except Exception as e:
                return json.dumps({
                    "data_status": "error",
                    "error": f"Authentication failed: {str(e)}"
                })
            
            cost_data_service = CostDataService(access_token)
            results = {}
            has_any_data = False
            
            for sub in user_config.subscriptions:
                if sub.name in subscription_names:
                    try:
                        response_data = cost_data_service.get_monthly_costs(sub.id, range_start_dt, end_dt)
                        
                        if not response_data or not response_data.get('rows'):
                            results[sub.name] = {
                                "data_status": "no_data",
                                "message": f"No cost data available for {sub.name} in this period. This could mean no resources were active or data hasn't synced yet.",
                                "period": f"{range_start_dt.strftime('%Y-%m')} to {end_dt.strftime('%Y-%m')}",
                                "monthly_costs": []
                            }
                            continue
                        
                        monthly_data = cost_data_service.parse_monthly_response(response_data)
                        
                        if not monthly_data:
                            results[sub.name] = {
                                "data_status": "no_data",
                                "message": f"No costs recorded for {sub.name}. The subscription may have had no active resources during this period.",
                                "period": f"{range_start_dt.strftime('%Y-%m')} to {end_dt.strftime('%Y-%m')}",
                                "monthly_costs": []
                            }
                            continue
                        
                        monthly_costs = []
                        total_cost_across_months = 0
                        
                        for month_key in sorted(monthly_data.keys()):
                            year_val, month_val = int(month_key[:4]), int(month_key[4:6])
                            month_str = datetime(year_val, month_val, 1).strftime('%Y-%m')
                            services = monthly_data[month_key]
                            total = sum(services.values())
                            total_cost_across_months += total
                            
                            monthly_costs.append({
                                "month": month_str,
                                "total_cost": round(total, 2),
                                "has_costs": total > 0.01,  # Distinguish zero from no data
                                "services": {k: round(v, 2) for k, v in sorted(services.items(), key=lambda x: x[1], reverse=True)[:10]}
                            })
                        
                        results[sub.name] = {
                            "data_status": "success" if total_cost_across_months > 0 else "no_data",
                            "monthly_costs": monthly_costs,
                            "period": f"{range_start_dt.strftime('%Y-%m')} to {end_dt.strftime('%Y-%m')}",
                            "total_months": len(monthly_costs),
                            "total_cost_all_months": round(total_cost_across_months, 2),
                            "average_monthly_cost": round(total_cost_across_months / len(monthly_costs), 2) if monthly_costs else 0
                        }
                        
                        if total_cost_across_months > 0:
                            has_any_data = True
                            
                    except Exception as e:
                        results[sub.name] = {
                            "data_status": "error",
                            "error": f"Failed to retrieve data: {str(e)}"
                        }
            
            # Determine overall status
            if not results:
                overall_status = "error"
                message = "No matching subscriptions found"
            elif not has_any_data:
                overall_status = "no_data"
                message = f"No costs recorded for any subscription from {range_start_dt.strftime('%Y-%m')} to {end_dt.strftime('%Y-%m')}"
            elif all(r.get("data_status") == "success" for r in results.values()):
                overall_status = "success"
                message = "Monthly cost data retrieved successfully"
            else:
                overall_status = "partial"
                message = "Data available for some subscriptions only"
            
            return json.dumps({
                "data_status": overall_status,
                "message": message,
                "subscriptions": results,
                "query_info": {
                    "period": f"{range_start_dt.strftime('%Y-%m')} to {end_dt.strftime('%Y-%m')}",
                    "months_requested": actual_months
                }
            }, indent=2)
        
        @tool
        def detect_anomalies(
            subscription_names: List[str],
            target_date: Optional[str] = None,
            threshold_percent: float = 25.0
        ) -> str:
            """
            Detect cost anomalies for a date.
            
            IMPROVED: Better messaging when no data is available for anomaly detection.
            """
            
            if not 0 <= threshold_percent <= 100:
                return json.dumps({
                    "data_status": "error",
                    "error": "threshold must be 0-100"
                })
            
            target_dt = datetime.strptime(target_date, '%Y-%m-%d') if target_date else datetime.now() - timedelta(days=1)
            
            auth_service = AzureAuthService(
                user_config.tenant_id, user_config.client_id, user_config.client_secret
            )
            
            try:
                access_token = auth_service.get_access_token()
            except Exception as e:
                return json.dumps({
                    "data_status": "error",
                    "error": f"Authentication failed: {str(e)}"
                })
            
            cost_data_service = CostDataService(access_token)
            cost_processor = CostProcessorService()
            anomaly_detector = AnomalyDetectorService(cost_data_service, cost_processor)
            
            subs = {s.name: s.id for s in user_config.subscriptions if s.name in subscription_names}
            
            if not subs:
                return json.dumps({
                    "data_status": "error",
                    "error": "No matching subscriptions found",
                    "requested": subscription_names,
                    "available": [s.name for s in user_config.subscriptions]
                })
            
            try:
                results = anomaly_detector.check_all_subscriptions(subs, target_dt, threshold_percent)
                
                # Check if any data was found
                subs_with_data = [name for name, data in results.get('subscriptions', {}).items() 
                                 if data and data.get('results')]
                
                if not subs_with_data:
                    return json.dumps({
                        "data_status": "no_data",
                        "message": f"No cost data available for anomaly detection on {target_dt.strftime('%Y-%m-%d')}. Cannot compare against historical averages without data.",
                        "target_date": target_dt.strftime('%Y-%m-%d'),
                        "subscriptions_checked": list(subs.keys()),
                        "suggestion": "Try a more recent date or check if resources were active during this period"
                    })
                
                # Add data status
                results['data_status'] = "success"
                results['subs_with_data'] = subs_with_data
                results['subs_without_data'] = [name for name in subs.keys() if name not in subs_with_data]
                
                return json.dumps(results, indent=2)
                
            except Exception as e:
                return json.dumps({
                    "data_status": "error",
                    "error": str(e)
                })
        
        @tool
        def compare_subscription_costs(
            resource_type: str,
            subscription_names: Optional[List[str]] = None,
            num_months: int = 2
        ) -> str:
            """
            Compare costs for a resource type ACROSS subscriptions (max 6 months).
            
            IMPROVED: Clear messaging when no costs exist for the specified resource type.
            """
            
            if not 1 <= num_months <= 6:
                return json.dumps({
                    "data_status": "error",
                    "error": "num_months must be 1-6"
                })
            
            if subscription_names is None:
                subscription_names = [s.name for s in user_config.subscriptions]
            
            end_dt = datetime.now().replace(day=1)
            last_day = calendar.monthrange(end_dt.year, end_dt.month)[1]
            end_dt = end_dt.replace(day=last_day)
            
            year, month = end_dt.year, end_dt.month - num_months + 1
            while month <= 0:
                month += 12
                year -= 1
            start_dt = datetime(year, month, 1)
            
            auth_service = AzureAuthService(
                user_config.tenant_id, user_config.client_id, user_config.client_secret
            )
            
            try:
                access_token = auth_service.get_access_token()
            except Exception as e:
                return json.dumps({
                    "data_status": "error",
                    "error": f"Authentication failed: {str(e)}"
                })
            
            cost_data_service = CostDataService(access_token)
            comparison_data = {}
            totals = {}
            
            for sub in user_config.subscriptions:
                if sub.name in subscription_names:
                    try:
                        response_data = cost_data_service.get_monthly_costs(sub.id, start_dt, end_dt)
                        if not response_data:
                            continue
                        
                        monthly_data = cost_data_service.parse_monthly_response(response_data)
                        sub_total = 0
                        
                        for month_key in sorted(monthly_data.keys()):
                            year_val, month_val = int(month_key[:4]), int(month_key[4:6])
                            month_str = datetime(year_val, month_val, 1).strftime('%Y-%m')
                            cost = monthly_data[month_key].get(resource_type, 0)
                            sub_total += cost
                            
                            if month_str not in comparison_data:
                                comparison_data[month_str] = {}
                            comparison_data[month_str][sub.name] = round(cost, 2)
                        
                        totals[sub.name] = round(sub_total, 2)
                    except Exception:
                        continue
            
            if not comparison_data:
                return json.dumps({
                    "data_status": "no_data",
                    "message": f"No '{resource_type}' costs found for any subscription from {start_dt.strftime('%Y-%m')} to {end_dt.strftime('%Y-%m')}",
                    "resource_type": resource_type,
                    "period": f"{start_dt.strftime('%Y-%m')} to {end_dt.strftime('%Y-%m')}",
                    "subscriptions_checked": subscription_names,
                    "suggestion": "This resource type may not have been used, or the name might not match exactly. Common types: 'Virtual Machines', 'Storage', 'Azure Databricks', 'Bandwidth', 'Virtual Network'"
                }, indent=2)
            
            table = [{"month": m, **comparison_data[m]} for m in sorted(comparison_data.keys())]
            
            return json.dumps({
                "data_status": "success",
                "resource_type": resource_type,
                "period": f"{start_dt.strftime('%Y-%m')} to {end_dt.strftime('%Y-%m')}",
                "comparison_table": table,
                "totals": totals,
                "summary": {
                    "months_with_data": len(comparison_data),
                    "subscriptions_with_costs": len([t for t in totals.values() if t > 0]),
                    "highest_spender": max(totals.items(), key=lambda x: x[1])[0] if totals else None
                }
            }, indent=2)
        
        @tool
        def get_historical_subscription_costs(
            subscription_names: List[str],
            num_months: int = 6
        ) -> str:
            """
            Get TOTAL monthly costs without breakdown (max 12 months).
            
            IMPROVED: Distinguishes between no data and zero costs.
            """
            
            if not 1 <= num_months <= 12:
                return json.dumps({
                    "data_status": "error",
                    "error": "num_months must be 1-12"
                })
            
            end_dt = datetime.now().replace(day=1)
            last_day = calendar.monthrange(end_dt.year, end_dt.month)[1]
            end_dt = end_dt.replace(day=last_day)
            
            year, month = end_dt.year, end_dt.month - num_months + 1
            while month <= 0:
                month += 12
                year -= 1
            start_dt = datetime(year, month, 1)
            
            auth_service = AzureAuthService(
                user_config.tenant_id, user_config.client_id, user_config.client_secret
            )
            
            try:
                access_token = auth_service.get_access_token()
            except Exception as e:
                return json.dumps({
                    "data_status": "error",
                    "error": f"Authentication failed: {str(e)}"
                })
            
            cost_data_service = CostDataService(access_token)
            results = {}
            has_any_data = False
            
            for sub in user_config.subscriptions:
                if sub.name in subscription_names:
                    try:
                        response_data = cost_data_service.get_monthly_costs(sub.id, start_dt, end_dt)
                        
                        if not response_data or not response_data.get('rows'):
                            results[sub.name] = {
                                "data_status": "no_data",
                                "message": "No cost data available for this period"
                            }
                            continue
                        
                        monthly_data = cost_data_service.parse_monthly_response(response_data)
                        monthly_totals = []
                        grand_total = 0
                        
                        for month_key in sorted(monthly_data.keys()):
                            year_val, month_val = int(month_key[:4]), int(month_key[4:6])
                            month_str = datetime(year_val, month_val, 1).strftime('%Y-%m')
                            total = sum(monthly_data[month_key].values())
                            grand_total += total
                            monthly_totals.append({
                                "month": month_str, 
                                "total_cost": round(total, 2),
                                "has_costs": total > 0.01
                            })
                        
                        results[sub.name] = {
                            "data_status": "success" if grand_total > 0 else "no_data",
                            "monthly_totals": monthly_totals,
                            "grand_total": round(grand_total, 2),
                            "average": round(grand_total / len(monthly_totals), 2) if monthly_totals else 0
                        }
                        
                        if grand_total > 0:
                            has_any_data = True
                            
                    except Exception as e:
                        results[sub.name] = {
                            "data_status": "error",
                            "error": str(e)
                        }
            
            overall_status = "success" if has_any_data else "no_data"
            
            return json.dumps({
                "data_status": overall_status,
                "subscriptions": results,
                "period": f"{start_dt.strftime('%Y-%m')} to {end_dt.strftime('%Y-%m')}"
            }, indent=2)
        
        @tool
        def get_service_costs_with_breakdown(
            subscription_name: str,
            service_name: str,
            month: Optional[str] = None
        ) -> str:
            """
            Get service costs BY RESOURCE GROUP for a month.
            
            IMPROVED: Clear messaging when service has no costs.
            """
            
            month_dt = datetime.strptime(month, '%Y-%m') if month else datetime.now().replace(day=1)
            start_dt = month_dt.replace(day=1)
            last_day = calendar.monthrange(start_dt.year, start_dt.month)[1]
            end_dt = start_dt.replace(day=last_day)
            
            sub = next((s for s in user_config.subscriptions if s.name == subscription_name), None)
            if not sub:
                available_subs = [s.name for s in user_config.subscriptions]
                return json.dumps({
                    "data_status": "error",
                    "error": f"Subscription '{subscription_name}' not found",
                    "available_subscriptions": available_subs
                })
            
            auth_service = AzureAuthService(
                user_config.tenant_id, user_config.client_id, user_config.client_secret
            )
            
            try:
                access_token = auth_service.get_access_token()
            except Exception as e:
                return json.dumps({
                    "data_status": "error",
                    "error": f"Authentication failed: {str(e)}"
                })
            
            cost_data_service = CostDataService(access_token)
            
            try:
                response_data = cost_data_service.get_costs_by_resource_group(
                    sub.id, start_dt, end_dt, Granularity.MONTHLY
                )
                
                if not response_data or not response_data.get('rows'):
                    return json.dumps({
                        "data_status": "no_data",
                        "message": f"No cost data available for {subscription_name} in {month_dt.strftime('%Y-%m')}"
                    })
                
                grouped = cost_data_service.parse_grouped_response(
                    response_data,
                    [GroupingDimension.SERVICE_NAME.value, GroupingDimension.RESOURCE_GROUP.value]
                )
                
                rg_costs = {}
                total = 0
                
                for item in grouped:
                    if item.get('ServiceName') == service_name:
                        rg = item.get('ResourceGroupName', 'Unassigned')
                        cost = item['cost']
                        rg_costs[rg] = rg_costs.get(rg, 0) + cost
                        total += cost
                
                if not rg_costs or total < 0.01:
                    return json.dumps({
                        "data_status": "no_data",
                        "message": f"No costs found for service '{service_name}' in {subscription_name} for {month_dt.strftime('%Y-%m')}",
                        "subscription": subscription_name,
                        "service": service_name,
                        "month": month_dt.strftime('%Y-%m'),
                        "suggestion": "Verify the service name is correct. Common services: 'Virtual Machines', 'Storage', 'Azure Databricks'"
                    })
                
                breakdown = [
                    {
                        "resource_group": rg, 
                        "cost": round(cost, 2), 
                        "percentage": round(cost/total*100, 2)
                    }
                    for rg, cost in sorted(rg_costs.items(), key=lambda x: x[1], reverse=True)
                ]
                
                return json.dumps({
                    "data_status": "success",
                    "subscription": subscription_name,
                    "service": service_name,
                    "month": month_dt.strftime('%Y-%m'),
                    "total_cost": round(total, 2),
                    "breakdown": breakdown,
                    "resource_group_count": len(breakdown)
                }, indent=2)
                
            except Exception as e:
                return json.dumps({
                    "data_status": "error",
                    "error": str(e)
                })
        
        return [
            get_subscription_list,
            get_cost_summary,
            detect_anomalies,
            get_monthly_cost_summary,
            get_historical_subscription_costs,
            compare_subscription_costs,
            get_service_costs_with_breakdown
        ]
    
    async def process_message(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Process user message and return response."""
        
        chat_history = []
        if conversation_history:
            for msg in conversation_history:
                if msg["role"] == "user":
                    chat_history.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    chat_history.append(AIMessage(content=msg["content"]))
        
        try:
            result = await self.agent.ainvoke({
                "input": user_message,
                "chat_history": chat_history
            })
            
            tool_calls = []
            for step in result.get("intermediate_steps", []):
                if len(step) >= 2:
                    tool_calls.append({"tool": step[0].tool, "input": step[0].tool_input})
            
            return {
                "response": result.get("output", ""),
                "tool_calls": tool_calls if tool_calls else None,
                "success": True
            }
        except Exception as e:
            print(f"ERROR: {str(e)}")
            return {
                "response": f"I encountered an error processing your request: {str(e)}",
                "tool_calls": None,
                "success": False,
                "error": str(e)
            }


def create_agent_service(user_config: UserConfiguration) -> AgentService:
    return AgentService(user_config)