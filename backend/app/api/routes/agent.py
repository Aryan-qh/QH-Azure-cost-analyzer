# api/routes/agent.py
"""
AI Agent API Routes - LangChain Version

CHANGES FROM PREVIOUS VERSION:
1. Agent service now instantiated per request (with user config)
2. Simplified tool call handling (LangChain manages this)
3. Response format slightly different (LangChain standard)

ENDPOINTS:
1. POST /api/agent/chat - Send a message to the agent
2. POST /api/agent/conversation/new - Create new conversation
3. GET /api/agent/conversations - List active conversations
4. DELETE /api/agent/conversation/{id} - Delete a conversation
5. GET /api/agent/conversation/{id}/history - Get conversation history

LOGIC:
- All endpoints require valid session_id (links to Azure config)
- Conversations are isolated per session
- Multi-turn conversations maintain context
- LangChain handles tool execution transparently
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from app.services.agent_service import create_agent_service
from app.services.conversation_manager import get_conversation_manager, ConversationManagerService
from app.services.configuration_manager import get_config_manager, ConfigurationManagerService

router_agent = APIRouter()


# Request/Response Models

class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    session_id: str = Field(..., description="Session ID from configuration")
    message: str = Field(..., min_length=1, description="User's message/question")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for multi-turn chat. Omit to start new conversation.")


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    response: str
    conversation_id: str
    tool_calls_made: Optional[List[Dict[str, Any]]] = None
    success: bool = True


class NewConversationRequest(BaseModel):
    """Request to create new conversation"""
    session_id: str


class NewConversationResponse(BaseModel):
    """Response with new conversation ID"""
    conversation_id: str
    message: str


class ConversationListResponse(BaseModel):
    """Response with list of conversations"""
    conversations: List[Dict[str, Any]]
    count: int


# Endpoints

@router_agent.post("/chat", response_model=ChatResponse)
async def chat_with_agent(
    request: ChatRequest,
    conversation_manager: ConversationManagerService = Depends(get_conversation_manager),
    config_manager: ConfigurationManagerService = Depends(get_config_manager)
):
    """
    Send a message to the AI agent (LangChain-powered).
    
    FLOW:
    1. Validate session and get user configuration
    2. Get or create conversation
    3. Create agent service with user config
    4. Process message with LangChain agent
    5. Store message and response in conversation history
    6. Return natural language response
    
    EXAMPLE REQUESTS:
    - "What were the costs for prod yesterday?"
    - "Check for anomalies in all subscriptions"
    - "Show me the cost trend for the last 7 days"
    - "Are there any unusual spikes in Virtual Machine costs?"
    """
    
    try:
        # 1. Validate session and get configuration
        user_config = config_manager.get_config(request.session_id)
        
        if not user_config:
            raise HTTPException(
                status_code=401,
                detail="Session not found or expired. Please reconfigure."
            )
        
        # Update session activity
        config_manager.update_session_activity(request.session_id)
        
        # 2. Get or create conversation
        if request.conversation_id:
            conversation = conversation_manager.get_conversation(request.conversation_id)
            
            if not conversation:
                raise HTTPException(
                    status_code=404,
                    detail="Conversation not found or expired."
                )
            
            # Verify conversation belongs to this session
            if conversation.session_id != request.session_id:
                raise HTTPException(
                    status_code=403,
                    detail="Conversation does not belong to this session."
                )
            
            conversation_id = request.conversation_id
        else:
            # Create new conversation
            conversation_id = conversation_manager.create_conversation(request.session_id)
        
        # 3. Get conversation history
        history = conversation_manager.get_message_history(conversation_id) or []
        
        # 4. Create agent service with user configuration
        agent_service = create_agent_service(user_config)
        
        # 5. Process message with LangChain agent
        agent_result = await agent_service.process_message(
            user_message=request.message,
            conversation_history=history
        )
        
        # Check if agent encountered an error
        if not agent_result.get("success", False):
            return ChatResponse(
                response=agent_result["response"],
                conversation_id=conversation_id,
                tool_calls_made=None,
                success=False
            )
        
        # 6. Store messages in conversation
        # Store user message
        conversation_manager.add_message(
            conversation_id=conversation_id,
            role="user",
            content=request.message
        )
        
        # Store assistant response
        conversation_manager.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=agent_result["response"],
            tool_calls=agent_result.get("tool_calls")
        )
        
        # 7. Return response
        return ChatResponse(
            response=agent_result["response"],
            conversation_id=conversation_id,
            tool_calls_made=agent_result.get("tool_calls"),
            success=True
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in agent chat: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Agent processing failed: {str(e)}"
        )


@router_agent.post("/conversation/new", response_model=NewConversationResponse)
async def create_new_conversation(
    request: NewConversationRequest,
    conversation_manager: ConversationManagerService = Depends(get_conversation_manager),
    config_manager: ConfigurationManagerService = Depends(get_config_manager)
):
    """
    Create a new conversation thread.
    
    USE CASE: Start a fresh conversation when context reset is desired
    """
    
    # Validate session
    user_config = config_manager.get_config(request.session_id)
    
    if not user_config:
        raise HTTPException(
            status_code=401,
            detail="Session not found or expired."
        )
    
    # Create conversation
    conversation_id = conversation_manager.create_conversation(request.session_id)
    
    return NewConversationResponse(
        conversation_id=conversation_id,
        message="New conversation created successfully."
    )


@router_agent.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(
    session_id: str,
    conversation_manager: ConversationManagerService = Depends(get_conversation_manager),
    config_manager: ConfigurationManagerService = Depends(get_config_manager)
):
    """
    List all active conversations for a session.
    
    Returns:
    - List of conversations with metadata (created_at, message_count)
    - Useful for showing conversation history in UI
    """
    
    # Validate session
    user_config = config_manager.get_config(session_id)
    
    if not user_config:
        raise HTTPException(
            status_code=401,
            detail="Session not found or expired."
        )
    
    # Get conversations
    conversations = conversation_manager.list_conversations(session_id)
    
    return ConversationListResponse(
        conversations=conversations,
        count=len(conversations)
    )


@router_agent.delete("/conversation/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    session_id: str,
    conversation_manager: ConversationManagerService = Depends(get_conversation_manager),
    config_manager: ConfigurationManagerService = Depends(get_config_manager)
):
    """
    Delete a conversation.
    
    Returns:
    - Success message if deleted
    - 404 if conversation not found
    """
    
    # Validate session
    user_config = config_manager.get_config(session_id)
    
    if not user_config:
        raise HTTPException(
            status_code=401,
            detail="Session not found or expired."
        )
    
    # Verify conversation belongs to session
    conversation = conversation_manager.get_conversation(conversation_id)
    
    if conversation and conversation.session_id != session_id:
        raise HTTPException(
            status_code=403,
            detail="Conversation does not belong to this session."
        )
    
    # Delete conversation
    deleted = conversation_manager.delete_conversation(conversation_id)
    
    if deleted:
        return {
            "status": "success",
            "message": "Conversation deleted successfully."
        }
    else:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found."
        )


@router_agent.get("/conversation/{conversation_id}/history")
async def get_conversation_history(
    conversation_id: str,
    session_id: str,
    conversation_manager: ConversationManagerService = Depends(get_conversation_manager),
    config_manager: ConfigurationManagerService = Depends(get_config_manager)
):
    """
    Get full conversation history.
    
    Returns:
    - List of all messages in conversation
    - Useful for displaying chat history in UI
    """
    
    # Validate session
    user_config = config_manager.get_config(session_id)
    
    if not user_config:
        raise HTTPException(
            status_code=401,
            detail="Session not found or expired."
        )
    
    # Get conversation
    conversation = conversation_manager.get_conversation(conversation_id)
    
    if not conversation:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found or expired."
        )
    
    # Verify ownership
    if conversation.session_id != session_id:
        raise HTTPException(
            status_code=403,
            detail="Conversation does not belong to this session."
        )
    
    # Return history
    return {
        "conversation_id": conversation_id,
        "messages": [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
                "tool_calls": msg.tool_calls
            }
            for msg in conversation.messages
        ]
    }


@router_agent.get("/stats")
async def get_agent_stats(
    conversation_manager: ConversationManagerService = Depends(get_conversation_manager)
):
    """
    Get statistics about agent usage (for monitoring).
    """
    return {
        "active_conversations": conversation_manager.get_active_conversation_count(),
        "agent_framework": "LangChain with OpenAI GPT-4"
    }