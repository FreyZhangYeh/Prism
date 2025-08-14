import json
import re
import logging
from typing import Dict, Any, Union, List, Optional
from openai import OpenAI
import os

logger = logging.getLogger(__name__)


class LLMClient:
    """LLM client for deep research demo using Qwen API."""
    
    def __init__(self, 
                 api_key: Optional[str] = None,
                 base_url: Optional[str] = None,
                 model_name: str = "qwen-flash"):
        """
        Initialize LLM client.
        
        Args:
            api_key: API key for Qwen service
            base_url: Base URL for Qwen service
            model_name: Model to use (default: qwen-plus)
        """
        # Try to import config
        try:
            from config import config as global_config
            self.api_key = api_key or global_config.llm.api_key
            self.base_url = base_url or global_config.llm.base_url
            self.model_name = model_name or global_config.llm.model
        except ImportError:
            # Use provided values or defaults
            self.api_key = api_key or ""
            self.base_url = base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
            self.model_name = model_name or "qwen-flash"
        
        if not self.api_key:
            raise ValueError("API key is required. Please set 'api_key' in config.json.")
        
        self._client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
        )
        self.call_count = 0
        logger.info(f"LLMClient initialized with model: {self.model_name}")
    
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7) -> str:
        """
        Synchronous chat completion.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0-1)
            
        Returns:
            Generated text response
        """
        self.call_count += 1
        
        try:
            # Check if we need JSON response format
            need_json = False
            for msg in messages:
                if "仅输出JSON" in msg.get("content", "") or "Only output JSON" in msg.get("content", ""):
                    need_json = True
                    break
            
            # Prepare request parameters
            params = {
                "model": self.model_name,
                "messages": messages,
                "temperature": temperature,
            }
            
            # Add JSON response format if needed
            if need_json:
                params["response_format"] = {"type": "json_object"}
            
            # Make API call
            completion = self._client.chat.completions.create(**params)
            
            response_content = completion.choices[0].message.content
            if not response_content:
                raise ValueError("LLM returned an empty response")
            
            logger.debug(f"LLM response: {response_content[:200]}...")
            return response_content
            
        except Exception as e:
            logger.error(f"Failed to generate response from LLM: {e}")
            raise
    
    def generate_json(self, 
                      system_prompt: str, 
                      user_prompt: str,
                      temperature: float = 0.7) -> Dict[str, Any]:
        """
        Generate structured JSON output.
        
        Args:
            system_prompt: System message
            user_prompt: User message
            temperature: Sampling temperature
            
        Returns:
            Parsed JSON dictionary
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            completion = self._client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"}
            )
            
            response_content = completion.choices[0].message.content
            if not response_content:
                raise ValueError("LLM returned an empty response")
            
            return self._parse_json_from_response(response_content)
            
        except Exception as e:
            logger.error(f"Failed to generate JSON from LLM: {e}")
            raise
    
    def _parse_json_from_response(self, text: str) -> Dict[str, Any]:
        """
        Parse JSON from response text, handling various formats.
        """
        json_obj: Union[Dict, List]
        
        # Try to find JSON code block
        match = re.search(r"```json\s*([\s\S]+?)\s*```", text)
        if match:
            json_str = match.group(1)
            try:
                json_obj = json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"Found JSON block but it was malformed: {json_str}")
                raise e
        else:
            # Try to parse the entire text as JSON
            try:
                json_obj = json.loads(text)
            except json.JSONDecodeError as e:
                logger.error(f"Response is not valid JSON: {text[:200]}...")
                raise Exception("LLM response was not valid JSON") from e
        
        # Handle list responses
        if isinstance(json_obj, list):
            if json_obj:
                return json_obj[0]
            else:
                logger.warning("LLM returned empty JSON list")
                raise Exception("LLM returned empty JSON list")
        
        # Return dictionary directly
        if isinstance(json_obj, dict):
            return json_obj
        
        # Other types are not expected
        raise Exception(f"Expected JSON object or list, got type '{type(json_obj)}'")
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        return {
            "total_calls": self.call_count,
            "model": self.model_name,
            "base_url": self.base_url
        }