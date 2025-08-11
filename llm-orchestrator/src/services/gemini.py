"""Gemini LLM service"""
import os
import sys
import time
import json
from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

# Import OpenTelemetry instrumentation
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'shared'))
try:
    from opentelemetry import trace
    from telemetry import trace_function, add_ai_attributes, TraceContext
    tracer = trace.get_tracer(__name__)
except ImportError:
    # Fallback if telemetry is not available
    def trace_function(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    class TraceContext:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def set_attribute(self, *args):
            pass
    
    tracer = None

from config import get_settings
from models.chat import Message, MessageRole, ChatRequest, ChatResponse, TokenUsage


class GeminiService:
    """Service for interacting with Google Gemini"""
    
    def __init__(self):
        self.settings = get_settings()
        genai.configure(api_key=self.settings.gemini_api_key)
        
        # Safety settings
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }
        
        # Model configuration
        self.generation_config = {
            "temperature": self.settings.temperature,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": self.settings.max_tokens,
        }
    
    def _get_model(self, model_name: Optional[str] = None) -> genai.GenerativeModel:
        """Get Gemini model instance"""
        model_name = model_name or self.settings.gemini_model
        
        # Add thinking configuration for flash models
        if "flash" in model_name and self.settings.thinking_budget > 0:
            self.generation_config["thinking_budget"] = self.settings.thinking_budget
        
        return genai.GenerativeModel(
            model_name=model_name,
            generation_config=self.generation_config,
            safety_settings=self.safety_settings
        )
    
    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Convert messages to Gemini format"""
        gemini_messages = []
        
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                # Gemini doesn't have system role, prepend to first user message
                if gemini_messages and gemini_messages[0]["role"] == "user":
                    gemini_messages[0]["parts"][0] = f"{msg.content}\n\n{gemini_messages[0]['parts'][0]}"
                else:
                    gemini_messages.insert(0, {
                        "role": "user",
                        "parts": [msg.content]
                    })
            elif msg.role == MessageRole.USER:
                gemini_messages.append({
                    "role": "user",
                    "parts": [msg.content]
                })
            elif msg.role == MessageRole.ASSISTANT:
                gemini_messages.append({
                    "role": "model",
                    "parts": [msg.content]
                })
        
        return gemini_messages
    
    def _calculate_cost(self, usage: Dict[str, int], model: str) -> float:
        """Calculate cost based on token usage"""
        # Gemini pricing (example rates, update with actual)
        pricing = {
            "gemini-2.0-flash-exp": {
                "input": 0.00025 / 1000,  # per token
                "output": 0.001 / 1000,   # per token
            },
            "gemini-1.5-pro": {
                "input": 0.0035 / 1000,
                "output": 0.014 / 1000,
            }
        }
        
        model_pricing = pricing.get(model, pricing["gemini-2.0-flash-exp"])
        
        input_cost = usage.get("prompt_tokens", 0) * model_pricing["input"]
        output_cost = usage.get("completion_tokens", 0) * model_pricing["output"]
        
        return round(input_cost + output_cost, 6)
    
    async def complete(self, request: ChatRequest) -> ChatResponse:
        """Generate chat completion with OpenTelemetry instrumentation"""
        with TraceContext(
            name="gemini.chat_completion",
            attributes={
                "ai.operation": "chat_completion",
                "ai.provider": "google",
                "ai.model": request.model or self.settings.gemini_model,
                "ai.temperature": request.temperature or self.settings.temperature,
                "ai.max_tokens": request.max_tokens or self.settings.max_tokens,
                "session.id": request.session_id,
                "message.count": len(request.messages)
            }
        ) as span:
            try:
                model = self._get_model(request.model)
                
                # Update generation config with request parameters
                if request.temperature is not None:
                    model._generation_config.temperature = request.temperature
                if request.max_tokens is not None:
                    model._generation_config.max_output_tokens = request.max_tokens
                if request.thinking_budget is not None and "flash" in model.model_name:
                    model._generation_config.thinking_budget = request.thinking_budget
                
                # Convert messages
                gemini_messages = self._convert_messages(request.messages)
                
                # Record start time for cost tracking
                start_time = time.time()
                
                # Generate response
                chat = model.start_chat(history=gemini_messages[:-1] if len(gemini_messages) > 1 else [])
                response = chat.send_message(gemini_messages[-1]["parts"][0])
                
                # Calculate completion time
                completion_time = time.time() - start_time
                
                # Extract token usage
                usage_metadata = response.usage_metadata
                usage = {
                    "prompt_tokens": usage_metadata.prompt_token_count,
                    "completion_tokens": usage_metadata.candidates_token_count,
                    "total_tokens": usage_metadata.total_token_count,
                }
                
                # Calculate cost
                cost = self._calculate_cost(usage, model.model_name)
                
                # Add AI attributes to span for cost tracking
                if tracer:
                    add_ai_attributes(
                        span,
                        provider="google",
                        model=model.model_name,
                        input_tokens=usage["prompt_tokens"],
                        output_tokens=usage["completion_tokens"],
                        cost_usd=cost
                    )
                    span.set_attribute("ai.completion_time_s", completion_time)
                    span.set_attribute("ai.characters_generated", len(response.text))
                
                # Format response
                return ChatResponse(
                    id=f"chat-{int(time.time())}",
                    model=model.model_name,
                    choices=[{
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": response.text
                        },
                        "finish_reason": "stop"
                    }],
                    usage={**usage, "cost": cost},
                    created=int(time.time()),
                    session_id=request.session_id
                )
                
            except Exception as e:
                if tracer:
                    span.record_exception(e)
                    span.set_attribute("error.type", type(e).__name__)
                raise
    
    async def stream_complete(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """Stream chat completion"""
        model = self._get_model(request.model)
        
        # Update generation config
        if request.temperature is not None:
            model._generation_config.temperature = request.temperature
        if request.max_tokens is not None:
            model._generation_config.max_output_tokens = request.max_tokens
        
        # Convert messages
        gemini_messages = self._convert_messages(request.messages)
        
        # Generate streaming response
        chat = model.start_chat(history=gemini_messages[:-1] if len(gemini_messages) > 1 else [])
        response_stream = chat.send_message(
            gemini_messages[-1]["parts"][0],
            stream=True
        )
        
        # Stream chunks
        for chunk in response_stream:
            if chunk.text:
                data = {
                    "id": f"chat-{int(time.time())}",
                    "model": model.model_name,
                    "choices": [{
                        "index": 0,
                        "delta": {"content": chunk.text},
                        "finish_reason": None
                    }]
                }
                yield f"data: {json.dumps(data)}\n\n"
        
        # Send final chunk
        yield "data: [DONE]\n\n"
    
    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """Count tokens in text"""
        model = self._get_model(model)
        return model.count_tokens(text).total_tokens
    
    async def create_embeddings(self, texts: List[str], model: str = "models/text-embedding-004") -> List[List[float]]:
        """Create embeddings for texts"""
        embed_model = genai.GenerativeModel(model)
        embeddings = []
        
        for text in texts:
            result = embed_model.embed_content(text)
            embeddings.append(result.embedding)
        
        return embeddings