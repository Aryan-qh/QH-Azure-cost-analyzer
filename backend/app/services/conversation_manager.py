"""
Conversation Manager Service - Compatible with LangChain

PURPOSE: Manage multi-turn conversations with history and context
- Store conversation history in memory (extensible to Redis/DB)
- Track tool calls and results for context
- Handle conversation lifecycle (create, update, delete)
- Prepare conversation context for LangChain agents

CURRENT APPROACH:
- Use this manager for storage and retrieval
- Convert to LangChain message format when invoking agent
- Best of both worlds: persistence + LangChain's powerful memory features
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
import secrets


class Message(BaseModel):
    """Single message in a conversation"""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = datetime.now()
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_results: Optional[List[Dict[str, Any]]] = None


class Conversation(BaseModel):
    """Conversation thread with history"""
    conversation_id: str
    session_id: str  # Links to user's Azure config
    messages: List[Message] = []
    created_at: datetime = datetime.now()
    last_updated: datetime = datetime.now()
    metadata: Dict[str, Any] = {}  # For RAG: embeddings, summaries, etc.


class ConversationManagerService:
    """
    Manage conversation state and history.
    
    DESIGN NOTES:
    - In-memory storage for simplicity (like configuration_manager)
    - Conversations expire after 30 minutes of inactivity
    - metadata field prepared for RAG extension (store embeddings, summaries)
    - Easy to migrate to Redis or PostgreSQL later
    
    LANGCHAIN COMPATIBILITY:
    - get_message_history() returns format compatible with LangChain
    - Can be easily converted to HumanMessage/AIMessage objects
    - Works alongside LangChain's memory classes
    """
    
    # Conversation timeout (30 minutes)
    CONVERSATION_TIMEOUT = timedelta(minutes=30)
    
    # Max messages to keep in context (prevent token overflow)
    MAX_CONTEXT_MESSAGES = 20
    
    def __init__(self):
        # In-memory storage: {conversation_id: Conversation}
        self._conversations: Dict[str, Conversation] = {}
    
    def create_conversation(self, session_id: str) -> str:
        """
        Create a new conversation thread.
        
        Args:
            session_id: User's session ID (links to their Azure config)
        
        Returns:
            conversation_id: Unique identifier for this conversation
        """
        conversation_id = secrets.token_urlsafe(16)
        
        conversation = Conversation(
            conversation_id=conversation_id,
            session_id=session_id,
            metadata={}  # RAG: Future use for embeddings, summaries
        )
        
        self._conversations[conversation_id] = conversation
        
        # Cleanup expired conversations
        self._cleanup_expired_conversations()
        
        return conversation_id
    
    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        tool_results: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Add a message to conversation history.
        
        Args:
            conversation_id: Conversation identifier
            role: "user" or "assistant"
            content: Message content
            tool_calls: Optional list of tool calls made by assistant (LangChain format)
            tool_results: Optional list of tool execution results
        
        Returns:
            True if added successfully, False if conversation not found
        """
        if conversation_id not in self._conversations:
            return False
        
        conversation = self._conversations[conversation_id]
        
        message = Message(
            role=role,
            content=content,
            tool_calls=tool_calls,
            tool_results=tool_results
        )
        
        conversation.messages.append(message)
        conversation.last_updated = datetime.now()
        
        # Limit context window size
        if len(conversation.messages) > self.MAX_CONTEXT_MESSAGES:
            # Keep system context + recent messages
            # RAG: In future, summarize old messages and store in metadata
            conversation.messages = conversation.messages[-self.MAX_CONTEXT_MESSAGES:]
        
        return True
    
    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """
        Retrieve a conversation by ID.
        
        Returns None if conversation doesn't exist or has expired.
        """
        if conversation_id not in self._conversations:
            return None
        
        conversation = self._conversations[conversation_id]
        
        # Check if expired
        if datetime.now() - conversation.last_updated > self.CONVERSATION_TIMEOUT:
            del self._conversations[conversation_id]
            return None
        
        return conversation
    
    def get_message_history(self, conversation_id: str) -> Optional[List[Dict[str, str]]]:
        """
        Get message history formatted for LangChain.
        
        Returns:
            List of messages in format: [{"role": "user", "content": "..."}]
            This format is compatible with LangChain's message history
            None if conversation not found
        
        LANGCHAIN CONVERSION:
        In agent_service.py, we convert this to LangChain message objects:
        ```python
        from langchain_core.messages import HumanMessage, AIMessage
        
        for msg in history:
            if msg["role"] == "user":
                langchain_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                langchain_messages.append(AIMessage(content=msg["content"]))
        ```
        """
        conversation = self.get_conversation(conversation_id)
        
        if not conversation:
            return None
        
        # Format for LangChain compatibility
        history = []
        for msg in conversation.messages:
            history.append({
                "role": msg.role,
                "content": msg.content
            })
        
        return history
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """
        Delete a conversation.
        
        Returns:
            True if deleted, False if not found
        """
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            return True
        return False
    
    def validate_session(self, session_id: str) -> bool:
        """
        Check if a session exists and is valid.
        
        Args:
            session_id: Session identifier
        
        Returns:
            True if session is valid, False otherwise
        """
        return self.get_config(session_id) is not None
    
    def list_conversations(self, session_id: str) -> List[Dict[str, Any]]:
        """
        List all active conversations for a session.
        
        Returns:
            List of conversation summaries (non-sensitive info)
        """
        self._cleanup_expired_conversations()
        
        conversations = []
        for conv_id, conv in self._conversations.items():
            if conv.session_id == session_id:
                conversations.append({
                    "conversation_id": conv_id,
                    "created_at": conv.created_at.isoformat(),
                    "last_updated": conv.last_updated.isoformat(),
                    "message_count": len(conv.messages)
                })
        
        return conversations
    
    def _cleanup_expired_conversations(self):
        """Remove expired conversations from memory"""
        now = datetime.now()
        expired = [
            conv_id for conv_id, conv in self._conversations.items()
            if now - conv.last_updated > self.CONVERSATION_TIMEOUT
        ]
        
        for conv_id in expired:
            del self._conversations[conv_id]
    
    def get_active_conversation_count(self) -> int:
        """Get count of active conversations"""
        self._cleanup_expired_conversations()
        return len(self._conversations)
    
    # RAG PREPARATION METHODS
    # These work the same with LangChain
    
    def update_metadata(self, conversation_id: str, key: str, value: Any) -> bool:
        """
        Update conversation metadata.
        
        RAG USE CASE: Store embeddings, summaries, or other derived data
        
        Examples:
        - update_metadata(conv_id, "summary", "User asked about costs...")
        - update_metadata(conv_id, "embedding", [0.1, 0.2, ...])
        - update_metadata(conv_id, "topics", ["azure", "costs", "anomalies"])
        
        LANGCHAIN INTEGRATION:
        Can be used alongside LangChain's memory for additional context:
        ```python
        # Store conversation summary for RAG
        summary = await llm.ainvoke("Summarize this conversation...")
        conversation_manager.update_metadata(conv_id, "summary", summary)
        ```
        """
        if conversation_id not in self._conversations:
            return False
        
        self._conversations[conversation_id].metadata[key] = value
        return True
    
    def get_metadata(self, conversation_id: str, key: str) -> Optional[Any]:
        """
        Retrieve specific metadata value.
        
        Returns:
            Metadata value if found, None otherwise
        """
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return None
        
        return conversation.metadata.get(key)


# Global instance
_conversation_manager = ConversationManagerService()


def get_conversation_manager() -> ConversationManagerService:
    """Get the global conversation manager instance"""
    return _conversation_manager


