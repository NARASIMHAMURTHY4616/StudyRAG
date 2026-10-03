"""Ollama Client for local LLM inference with low-latency streaming and performance metrics."""

import json
import logging
import re
import time
import threading
from typing import Generator, Optional, Dict, Any
import requests
from config import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for communicating with local Ollama instance with streaming capability and latency metrics."""

    # Concurrency guard to prevent multi-request CPU contention on low-resource machines
    _generation_lock = threading.Lock()

    def __init__(
        self,
        base_url: str = settings.OLLAMA_BASE_URL,
        model: str = settings.OLLAMA_MODEL,
        timeout: int = settings.OLLAMA_TIMEOUT,
        keep_alive: str = settings.OLLAMA_KEEP_ALIVE,
        think: bool = settings.OLLAMA_THINK,
        max_tokens: int = settings.MAX_OUTPUT_TOKENS,
        temperature: float = settings.TEMPERATURE,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.keep_alive = keep_alive
        self.think = think
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.generate_url = f"{self.base_url}/api/generate"

    def is_available(self) -> bool:
        """Check if Ollama server is reachable and running."""
        try:
            res = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return res.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False

    def list_models(self) -> list:
        """List available models in local Ollama."""
        try:
            res = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if res.status_code == 200:
                data = res.json()
                return [m.get("name") for m in data.get("models", [])]
        except Exception as e:
            logger.warning(f"Could not list Ollama models: {e}")
        return [self.model]

    def _build_payload(
        self,
        prompt: str,
        model: Optional[str] = None,
        stream: bool = False,
        think: Optional[bool] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Build optimized payload for local CPU inference."""
        active_model = model or self.model
        active_think = self.think if think is None else think
        active_max_tokens = max_tokens or self.max_tokens
        active_temperature = self.temperature if temperature is None else temperature

        payload: Dict[str, Any] = {
            "model": active_model,
            "prompt": prompt,
            "stream": stream,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": active_temperature,
                "num_predict": active_max_tokens,
            },
        }

        # Explicitly control reasoning/thinking if supported by model/Ollama
        if active_think is not None:
            payload["think"] = active_think

        return payload

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        think: Optional[bool] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        Send a prompt to Ollama and return the generated text synchronously.
        """
        payload = self._build_payload(
            prompt,
            model=model,
            stream=False,
            think=think,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        active_model = payload["model"]
        active_tokens = payload["options"]["num_predict"]

        logger.info(f"Sending prompt to Ollama model '{active_model}' (think={payload.get('think')}, max_tokens={active_tokens})")
        t_start = time.perf_counter()

        with OllamaClient._generation_lock:
            try:
                response = requests.post(
                    self.generate_url,
                    json=payload,
                    timeout=self.timeout,
                )
            except requests.exceptions.ConnectionError as e:
                msg = "Ollama is not running. Please start Ollama (`ollama serve`) and try again."
                logger.error(f"Connection error to Ollama: {e}")
                raise ConnectionError(msg) from e
            except requests.exceptions.Timeout as e:
                msg = f"Ollama request timed out after {self.timeout} seconds."
                logger.error(msg)
                raise TimeoutError(msg) from e
            except Exception as e:
                logger.error(f"Unexpected error calling Ollama: {e}")
                raise RuntimeError(f"Failed to communicate with Ollama: {e}") from e

        t_end = time.perf_counter()
        elapsed = t_end - t_start

        if response.status_code != 200:
            err_msg = f"Ollama returned HTTP {response.status_code}: {response.text}"
            logger.error(err_msg)
            raise RuntimeError(err_msg)

        try:
            result = response.json()
            raw_response = result.get("response", "")
            eval_count = result.get("eval_count", 0)
            tok_sec = round(eval_count / elapsed, 2) if elapsed > 0 and eval_count > 0 else 0
            logger.info(f"[PERF] Ollama generation finished in {elapsed:.2f}s ({eval_count} tokens, ~{tok_sec} tok/s)")
            return self._clean_llm_output(raw_response)
        except Exception as e:
            logger.error(f"Failed to parse Ollama JSON response: {e}")
            raise RuntimeError(f"Invalid response from Ollama: {e}") from e

    def generate_stream(
        self,
        prompt: str,
        model: Optional[str] = None,
        think: Optional[bool] = None,
    ) -> Generator[str, None, None]:
        """
        Stream tokens progressively from Ollama with precise TTFT tracking.
        Yields tokens one by one as they arrive without unneeded buffering.
        """
        payload = self._build_payload(prompt, model=model, stream=True, think=think)
        active_model = payload["model"]

        logger.info(f"Initiating streaming request to Ollama model '{active_model}' (think={payload.get('think')})")

        t_start = time.perf_counter()
        first_token_time: Optional[float] = None
        token_count = 0

        # Concurrency protection
        if not OllamaClient._generation_lock.acquire(blocking=True, timeout=120):
            raise RuntimeError("Local LLM engine is currently busy processing another request. Please try again in a moment.")

        try:
            try:
                response = requests.post(
                    self.generate_url,
                    json=payload,
                    stream=True,
                    timeout=self.timeout,
                )
            except requests.exceptions.ConnectionError as e:
                msg = "Ollama is not running. Please start Ollama (`ollama serve`) and try again."
                logger.error(f"Connection error to Ollama streaming: {e}")
                raise ConnectionError(msg) from e
            except requests.exceptions.Timeout as e:
                msg = f"Ollama streaming request timed out after {self.timeout}s."
                logger.error(msg)
                raise TimeoutError(msg) from e
            except Exception as e:
                logger.error(f"Unexpected streaming error calling Ollama: {e}")
                raise RuntimeError(f"Failed to communicate with Ollama: {e}") from e

            if response.status_code != 200:
                raise RuntimeError(f"Ollama returned HTTP {response.status_code}: {response.text}")

            in_think_block = False
            think_buffer = ""

            for line in response.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    token = data.get("response", "")

                    if not token:
                        if data.get("done", False):
                            eval_count = data.get("eval_count", token_count)
                            eval_dur_ns = data.get("eval_duration", 0)
                            total_dur_ns = data.get("total_duration", 0)
                            if eval_dur_ns > 0:
                                tok_sec = round(eval_count / (eval_dur_ns / 1e9), 2)
                                logger.info(f"[PERF] Ollama streaming complete: {eval_count} tokens in {total_dur_ns / 1e9:.2f}s (~{tok_sec} tok/s)")
                            break
                        continue

                    token_count += 1
                    if first_token_time is None:
                        first_token_time = time.perf_counter() - t_start
                        logger.info(f"[PERF] Ollama Time-To-First-Token (TTFT): {first_token_time:.2f}s")

                    # If think mode is disabled (default), yield token directly for maximum streaming speed
                    if not self.think:
                        yield token
                        continue

                    # Fallback thinking filter if think=True
                    think_buffer += token
                    if "<think>" in think_buffer:
                        in_think_block = True
                        if "</think>" in think_buffer:
                            parts = think_buffer.split("</think>", 1)
                            token_to_emit = parts[1]
                            think_buffer = ""
                            in_think_block = False
                            if token_to_emit:
                                yield token_to_emit
                        continue

                    if in_think_block:
                        if "</think>" in think_buffer:
                            parts = think_buffer.split("</think>", 1)
                            token_to_emit = parts[1]
                            think_buffer = ""
                            in_think_block = False
                            if token_to_emit:
                                yield token_to_emit
                        continue

                    yield token

                except Exception as e:
                    logger.debug(f"Error parsing streaming chunk: {e}")
                    continue

        finally:
            OllamaClient._generation_lock.release()
            total_time = time.perf_counter() - t_start
            ttft_str = f"{first_token_time:.2f}s" if first_token_time is not None else "N/A"
            logger.info(f"[PERF] Ollama stream finished: TTFT={ttft_str} | total={total_time:.2f}s | tokens={token_count}")

    def _clean_llm_output(self, text: str) -> str:
        """Strip internal reasoning tags (like <think>...</think>) if present."""
        if not text:
            return ""
        cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        return cleaned.strip()
