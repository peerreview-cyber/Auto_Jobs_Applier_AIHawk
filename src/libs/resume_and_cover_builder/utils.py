import json
import time
from datetime import datetime
from typing import Any, Dict, List
from langchain_core.messages.ai import AIMessage
from langchain_core.prompt_values import StringPromptValue
from .config import global_config
from loguru import logger

class LLMLogger:
    def __init__(self, llm: Any):
        self.llm = llm

    @staticmethod
    def log_request(prompts, parsed_reply: Dict[str, Dict]):
        try:
            if not global_config.LOG_OUTPUT_FILE_PATH:
                return
            calls_log = global_config.LOG_OUTPUT_FILE_PATH / "open_ai_calls.json"
            
            if isinstance(prompts, StringPromptValue):
                prompts_text = prompts.text
            elif hasattr(prompts, 'messages'):
                prompts_text = {f"prompt_{i+1}": m.content for i, m in enumerate(prompts.messages)}
            else:
                prompts_text = str(prompts)

            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            token_usage = parsed_reply.get("usage_metadata", {})
            
            log_entry = {
                "model": parsed_reply.get("response_metadata", {}).get("model_name", "unknown"),
                "time": current_time,
                "prompts": prompts_text,
                "replies": parsed_reply.get("content", ""),
                "total_tokens": token_usage.get("total_tokens", 0),
                "input_tokens": token_usage.get("input_tokens", 0),
                "output_tokens": token_usage.get("output_tokens", 0),
                "total_cost": 0 # Placeholder
            }

            with open(calls_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False, indent=4) + "\n")
        except Exception as e:
            logger.error(f"Error logging request: {e}")

class LoggerChatModel:
    def __init__(self, llm: Any):
        self.llm = llm
        self.logger = logger # Added for compatibility

    def __call__(self, messages: List[Any]) -> str:
        max_retries = 10
        retry_delay = 10
        for attempt in range(max_retries):
            try:
                reply = self.llm.invoke(messages)
                parsed_reply = self.parse_llmresult(reply)
                LLMLogger.log_request(prompts=messages, parsed_reply=parsed_reply)
                return reply
            except Exception as e:
                error_msg = str(e)
                # Specific check for Gemini/API overload
                if "503" in error_msg or "overloaded" in error_msg.lower():
                    logger.warning(f"Gemini API Overloaded (503). Retrying in {retry_delay}s... (Attempt {attempt+1}/{max_retries})")
                else:
                    logger.error(f"LLM Error (Attempt {attempt+1}): {error_msg}")
                
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 1.5 # Exponential backoff
                else:
                    raise

    def parse_llmresult(self, llmresult: AIMessage) -> Dict[str, Dict]:
        content = llmresult.content
        response_metadata = getattr(llmresult, 'response_metadata', {})
        usage_metadata = getattr(llmresult, 'usage_metadata', {})
        
        if not usage_metadata and 'token_usage' in response_metadata:
            tu = response_metadata['token_usage']
            usage_metadata = {
                "input_tokens": tu.get('prompt_tokens', 0),
                "output_tokens": tu.get('completion_tokens', 0),
                "total_tokens": tu.get('total_tokens', 0),
            }

        return {
            "content": content,
            "response_metadata": {
                "model_name": response_metadata.get("model_name", response_metadata.get("model", "unknown")),
            },
            "usage_metadata": {
                "input_tokens": usage_metadata.get("input_tokens", 0),
                "output_tokens": usage_metadata.get("output_tokens", 0),
                "total_tokens": usage_metadata.get("total_tokens", 0),
            },
        }
