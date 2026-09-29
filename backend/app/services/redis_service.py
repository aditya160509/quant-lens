import os
import requests
import json
import logging
from typing import Any, Optional, Union
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class RedisService:
    """
    Upstash Redis Service Wrapper
    Provides a shared brain for the Quant360 engine using REST API.
    """
    
    def __init__(self):
        # Always try to load .env from project root
        env_path = Path(__file__).parent.parent.parent.parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            
        self.url = os.getenv("UPSTASH_REDIS_REST_URL")
        self.token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
        self.is_active = bool(self.url and self.token)
        
        if not self.is_active:
            logger.warning("[REDIS] Redis credentials missing. Shared brain is DISABLED.")
        else:
            # Clean up URL (ensure no trailing slash)
            self.url = self.url.rstrip('/')
            logger.info(f"[REDIS] Shared brain ACTIVE: {self.url}")

    def get(self, key: str) -> Optional[Any]:
        """Get a value from Redis. Automatically parses JSON."""
        if not self.is_active:
            return None
            
        try:
            response = requests.get(
                f"{self.url}/get/{key}",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=2.0
            )
            
            if response.status_code == 200:
                result = response.json().get("result")
                if result:
                    try:
                        return json.loads(result)
                    except (ValueError, TypeError):
                        return result
            return None
        except Exception as e:
            logger.error(f"[REDIS] Get error for {key}: {e}")
            return None

    def mget(self, keys: list) -> list:
        """Get multiple values from Redis in ONE call. Crucial for reducing Upstash usage."""
        if not self.is_active or not keys:
            return [None] * len(keys)
            
        try:
            # Command format for Upstash REST: ["MGET", key1, key2, ...]
            cmd = ["MGET"] + keys
            response = requests.post(
                self.url,
                headers={"Authorization": f"Bearer {self.token}"},
                json=cmd,
                timeout=3.0
            )
            
            if response.status_code == 200:
                results = response.json().get("result", [])
                parsed_results = []
                for res in results:
                    if res:
                        try:
                            parsed_results.append(json.loads(res))
                        except (ValueError, TypeError):
                            parsed_results.append(res)
                    else:
                        parsed_results.append(None)
                return parsed_results
            return [None] * len(keys)
        except Exception as e:
            logger.error(f"[REDIS] MGet error: {e}")
            return [None] * len(keys)

    def set(self, key: str, value: Any, ex: int = None) -> bool:
        """Set a value in Redis with optional expiry (seconds)."""
        if not self.is_active:
            return False
            
        try:
            # Prepare value (JSON stringify if it's a dict or list)
            def custom_serializer(obj):
                if hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                if hasattr(obj, 'to_dict'):
                    return obj.to_dict()
                return str(obj)

            if isinstance(value, (dict, list)):
                val_str = json.dumps(value, default=custom_serializer)
            else:
                val_str = str(value)
            
            # Prepare command
            cmd = ["set", key, val_str]
            if ex:
                cmd.extend(["EX", str(ex)])
            
            response = requests.post(
                self.url,
                headers={"Authorization": f"Bearer {self.token}"},
                json=cmd,
                timeout=2.0
            )
            
            return response.status_code == 200
        except Exception as e:
            logger.error(f"[REDIS] Set error for {key}: {e}")
            return False

    def mset(self, mapping: dict, ex: int = None) -> bool:
        """Set multiple values in Redis in ONE call. MASSIVELY reduces Upstash costs."""
        if not self.is_active or not mapping:
            return False
            
        try:
            # Prepare value (JSON stringify if it's a dict or list)
            def custom_serializer(obj):
                if hasattr(obj, 'isoformat'):
                    return obj.isoformat()
                if hasattr(obj, 'to_dict'):
                    return obj.to_dict()
                return str(obj)

            # Command format for Upstash REST: ["MSET", key1, val1, key2, val2, ...]
            cmd = ["MSET"]
            for key, value in mapping.items():
                if isinstance(value, (dict, list)):
                    val_str = json.dumps(value, default=custom_serializer)
                else:
                    val_str = str(value)
                cmd.extend([key, val_str])
            
            response = requests.post(
                self.url,
                headers={"Authorization": f"Bearer {self.token}"},
                json=cmd,
                timeout=10.0
            )
            
            return response.status_code == 200
        except Exception as e:
            logger.error(f"[REDIS] MSet error: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete a key from Redis."""
        if not self.is_active:
            return False
        try:
            response = requests.get(
                f"{self.url}/del/{key}",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=2.0
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"[REDIS] Delete error for {key}: {e}")
            return False

# Global instance
redis_brain = RedisService()
