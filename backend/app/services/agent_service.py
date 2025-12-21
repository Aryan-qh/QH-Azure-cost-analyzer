"""
AI Agent Service - LangChain Implementation

PURPOSE: Conversational AI agent for Azure cost analysis using LangChain
- Uses LangChain's tool calling and agent framework
- Integrates with Claude via ChatAnthropic
- Defines tools as decorated functions
- Handles conversation flow with LangChain memory

BENEFITS OF LANGCHAIN:
1. Better abstractions (tools, agents, chains)
2. Built-in memory management
3. Easier to swap LLM providers
4. Better error handling and retries
5. RAG integration is much simpler

ARCHITECTURE:
User Question → LangChain Agent → Claude (ChatAnthropic)
                     ↓
              Tool Execution (decorated @tool)
              ├─ get_cost_summary_tool
              ├─ detect_anomalies_tool
              └─ get_subscription_list_tool
                     ↓
              Natural Language Response
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json

# LangChain imports
from langchain_openai import ChatOpenAI  # CHANGED: OpenAI instead of Anthropic
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

# Our existing services
from app.services.azure_auth import AzureAuthService
from app.services.cost_data import CostDataService
from app.services.cost_processor import CostProcessorService
from app.services.anomaly_detector import AnomalyDetectorService
from app.services.configuration_manager import UserConfiguration


class AgentService:
    """
    LangChain-based AI Agent for Azure cost analysis.
    
    DESIGN NOTES:
    - Uses ChatAnthropic (Claude Sonnet 4)
    - Tools defined with @tool decorator
    - AgentExecutor handles tool calling loop
    - Each instance is tied to a user configuration
    - Stateless: conversation history passed in
    """
    
    def __init__(self, user_config: UserConfiguration):
        """
        Initialize agent for a specific user.
        
        Args:
            user_config: User's Azure configuration (credentials + subscriptions)
        """
        self.user_config = user_config
        
        # Initialize OpenAI LLM
        # API key from environment: OPENAI_API_KEY
        self.llm = ChatOpenAI(
            model="gpt-4-turbo-preview",  # or "gpt-4", "gpt-3.5-turbo"
            temperature=0,  # Deterministic for cost analysis
            max_tokens=4096
        )
        
        # Create tools with user context
        self.tools = self._create_tools()
        
        # Create agent
        self.agent = self._create_agent()
    
    def _create_agent(self) -> AgentExecutor:
        """
        Create LangChain agent with tools.
        
        Returns:
            Configured AgentExecutor
        """
        
        # System prompt
        system_prompt = """You are an AI assistant for Azure cost analysis and monitoring.

Your capabilities:
1. Fetch cost data for Azure subscriptions over time periods
2. Detect cost anomalies by comparing against historical averages
3. Analyze cost trends and patterns
4. Answer questions about subscription configurations

Guidelines:
- Always ask for clarification if the user's request is ambiguous
- When dates aren't specified, use reasonable defaults (e.g., "yesterday" for anomalies)
- Present cost data clearly with proper formatting
- Highlight important findings (anomalies, large changes, trends)
- Be concise but comprehensive
- If multiple subscriptions exist, ask which ones to analyze unless specified

Current date: {current_date}

Available subscriptions: {subscriptions}
""".format(
            current_date=datetime.now().strftime('%Y-%m-%d'),
            subscriptions=", ".join([sub.name for sub in self.user_config.subscriptions])
        )
        
        # Create prompt template with memory placeholder
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        # Create tool-calling agent
        agent = create_tool_calling_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )
        
        # Create executor
        agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,  # Set to False in production
            handle_parsing_errors=True,
            max_iterations=5  # Prevent infinite loops
        )
        
        return agent_executor
    
    def _create_tools(self) -> List:
        """
        Create tools with user configuration context.
        
        Returns:
            List of LangChain tools
        """
        
        # Store user config in closure for tools to access
        user_config = self.user_config
        
        @tool
        def get_subscription_list() -> str:
            """Get list of configured Azure subscriptions with their display names.
            
            Use this to see available subscriptions before calling other tools.
            
            Returns:
                JSON string with subscription list
            """
            subscriptions = [
                {
                    "name": sub.name,
                    "id": sub.id[:8] + "..."  # Truncate for privacy
                }
                for sub in user_config.subscriptions
            ]
            
            return json.dumps({
                "subscriptions": subscriptions,
                "count": len(subscriptions)
            }, indent=2)
        
        @tool
        def get_cost_summary(subscription_names: List[str], num_days: int = 7) -> str:
            """Get cost data for specified subscriptions over a time period.
            
            Returns daily costs broken down by service category (Virtual Machines, 
            Storage, Databricks, etc.) with percentage changes.
            
            Args:
                subscription_names: List of subscription names to query (use exact names)
                num_days: Number of days to look back (1-90, default 7)
            
            Returns:
                JSON string with cost summary data
            """
            
            # Validate num_days
            if num_days < 1 or num_days > 90:
                return json.dumps({"error": "num_days must be between 1 and 90"})
            
            # Initialize Azure services
            auth_service = AzureAuthService(
                user_config.tenant_id,
                user_config.client_id,
                user_config.client_secret
            )
            
            try:
                access_token = auth_service.get_access_token()
            except Exception as e:
                return json.dumps({"error": f"Authentication failed: {str(e)}"})
            
            cost_data_service = CostDataService(access_token)
            cost_processor = CostProcessorService()
            
            # Calculate date range
            end_date = datetime.now() - timedelta(days=1)
            start_date = end_date - timedelta(days=num_days - 1)
            
            results = {}
            
            # Get data for each requested subscription
            for sub in user_config.subscriptions:
                if sub.name in subscription_names:
                    try:
                        # Fetch cost data
                        response_data = cost_data_service.get_cost_data_range(
                            sub.id, start_date, end_date
                        )
                        
                        if not response_data:
                            results[sub.name] = {"error": "No data available"}
                            continue
                        
                        daily_data = cost_data_service.parse_range_response(response_data)
                        
                        # Process each day
                        daily_costs = []
                        for i in range(num_days):
                            date = start_date + timedelta(days=i)
                            date_key = int(date.strftime('%Y%m%d'))
                            day_rows = daily_data.get(date_key, [])
                            
                            costs = cost_processor.process_cost_data(day_rows)
                            daily_costs.append({
                                "date": date.strftime('%Y-%m-%d'),
                                "costs": costs
                            })
                        
                        results[sub.name] = {
                            "daily_costs": daily_costs,
                            "period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
                        }
                    
                    except Exception as e:
                        results[sub.name] = {"error": str(e)}
            
            return json.dumps(results, indent=2)
        
        @tool
        def detect_anomalies(
            subscription_names: List[str],
            target_date: Optional[str] = None,
            threshold_percent: float = 25.0
        ) -> str:
            """Detect cost anomalies for a specific date.
            
            Compares against rolling calendar average from previous month to identify 
            services with unusual cost spikes or drops.
            
            Args:
                subscription_names: List of subscription names to check
                target_date: Date to check in YYYY-MM-DD format (default: yesterday)
                threshold_percent: Percentage threshold for flagging anomalies (default: 25.0)
            
            Returns:
                JSON string with anomaly detection results
            """
            
            # Validate threshold
            if threshold_percent < 0 or threshold_percent > 100:
                return json.dumps({"error": "threshold_percent must be between 0 and 100"})
            
            # Parse target date
            if target_date:
                try:
                    target_dt = datetime.strptime(target_date, '%Y-%m-%d')
                except ValueError:
                    return json.dumps({"error": "Invalid date format. Use YYYY-MM-DD"})
            else:
                target_dt = datetime.now() - timedelta(days=1)
            
            # Initialize services
            auth_service = AzureAuthService(
                user_config.tenant_id,
                user_config.client_id,
                user_config.client_secret
            )
            
            try:
                access_token = auth_service.get_access_token()
            except Exception as e:
                return json.dumps({"error": f"Authentication failed: {str(e)}"})
            
            cost_data_service = CostDataService(access_token)
            cost_processor = CostProcessorService()
            anomaly_detector = AnomalyDetectorService(cost_data_service, cost_processor)
            
            # Build subscription dictionary
            subscriptions_to_check = {
                sub.name: sub.id
                for sub in user_config.subscriptions
                if sub.name in subscription_names
            }
            
            if not subscriptions_to_check:
                return json.dumps({
                    "error": f"No matching subscriptions found. Available: {[s.name for s in user_config.subscriptions]}"
                })
            
            try:
                # Check all requested subscriptions
                results = anomaly_detector.check_all_subscriptions(
                    subscriptions_to_check,
                    target_dt,
                    threshold_percent
                )
                
                return json.dumps(results, indent=2)
            
            except Exception as e:
                return json.dumps({"error": str(e)})
        
        # Return list of tools
        return [get_subscription_list, get_cost_summary, detect_anomalies]
    
    async def process_message(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Process a user message and return agent response.
        
        Args:
            user_message: The user's question/request
            conversation_history: Previous messages (optional)
        
        Returns:
            Dictionary with response and metadata
        """
        
        # Convert conversation history to LangChain format
        chat_history = []
        if conversation_history:
            for msg in conversation_history:
                if msg["role"] == "user":
                    chat_history.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    chat_history.append(AIMessage(content=msg["content"]))
        
        try:
            # Invoke agent
            result = await self.agent.ainvoke({
                "input": user_message,
                "chat_history": chat_history
            })
            
            # Extract response
            response_text = result.get("output", "")
            
            # Extract intermediate steps (tool calls)
            intermediate_steps = result.get("intermediate_steps", [])
            tool_calls = []
            
            for step in intermediate_steps:
                if len(step) >= 2:
                    action = step[0]
                    tool_calls.append({
                        "tool": action.tool,
                        "input": action.tool_input
                    })
            
            return {
                "response": response_text,
                "tool_calls": tool_calls if tool_calls else None,
                "success": True
            }
        
        except Exception as e:
            print(f"ERROR in agent processing: {str(e)}")
            return {
                "response": f"I encountered an error processing your request: {str(e)}",
                "tool_calls": None,
                "success": False,
                "error": str(e)
            }


# Factory function for dependency injection
def create_agent_service(user_config: UserConfiguration) -> AgentService:
    """
    Create an agent service instance for a user.
    
    Args:
        user_config: User's Azure configuration
    
    Returns:
        Configured AgentService
    """
    return AgentService(user_config)