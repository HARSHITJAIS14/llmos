"""Gemini Teacher Client for contextual screen perception annotation."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = REPO_ROOT / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)


class GeminiTeacher:
    """Wrapper around Gemini 3.8 Flash with high thinking, caching, retry, and usage logging."""

    def __init__(
        self,
        model_name: str = "gemini-3.8-flash",
        thinking_level: types.ThinkingLevel = types.ThinkingLevel.HIGH,
        api_key: Optional[str] = None,
    ):
        self.model_name = model_name
        self.thinking_level = thinking_level
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY not found in environment or .env file.")

        self.client = genai.Client(api_key=self.api_key)

    def _pil_to_part(self, image: Image.Image) -> types.Part:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        raw_bytes = buf.getvalue()
        return types.Part.from_bytes(data=raw_bytes, mime_type="image/png")

    def call_annotator(
        self,
        prompt: str,
        images: List[Image.Image],
        output_dir: Path,
        call_name: str,
        response_schema: Optional[Any] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        Execute an annotation call with Gemini 3.8 Flash.
        Saves:
          - requests/<call_name>_request.json (prompt text, image sizes/hashes, NO secrets)
          - responses/<call_name>_response.json (raw text, finish reason, tokens, timing)
        Returns parsed JSON dict.
        """
        requests_dir = output_dir / "requests"
        responses_dir = output_dir / "responses"
        requests_dir.mkdir(parents=True, exist_ok=True)
        responses_dir.mkdir(parents=True, exist_ok=True)

        req_file = requests_dir / f"{call_name}_request.json"
        resp_file = responses_dir / f"{call_name}_response.json"

        # Check cache if already completed
        if resp_file.exists():
            cached = json.loads(resp_file.read_text())
            if cached.get("finish_reason") == "STOP" and "parsed" in cached:
                return cached["parsed"]

        # Record sanitized request metadata
        image_meta = []
        for im in images:
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            h = hashlib.sha256(buf.getvalue()).hexdigest()
            image_meta.append({"size": list(im.size), "sha256": h})

        request_record = {
            "model_requested": self.model_name,
            "thinking_level": str(self.thinking_level),
            "prompt": prompt,
            "images": image_meta,
            "timestamp": time.time(),
        }
        req_file.write_text(json.dumps(request_record, indent=2))

        # Build contents list
        contents: List[Any] = [prompt]
        for im in images:
            contents.append(self._pil_to_part(im))

        # Thinking config: high thinking, omit thoughts transcripts
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            thinking_config=types.ThinkingConfig(
                thinking_level=self.thinking_level,
                include_thoughts=False,
            ),
        )

        attempt = 0
        last_error = None
        while attempt < max_retries:
            attempt += 1
            start_t = time.perf_counter()
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=config,
                )
                elapsed = time.perf_counter() - start_t

                raw_text = response.text or ""
                finish_reason = "UNKNOWN"
                if response.candidates:
                    finish_reason = str(response.candidates[0].finish_reason).replace("FinishReason.", "")

                if finish_reason == "LENGTH":
                    raise ValueError("Model response was truncated due to output length limit.")

                # Parse JSON
                try:
                    cleaned_text = raw_text.strip()
                    if cleaned_text.startswith("```"):
                        lines = cleaned_text.splitlines()
                        if lines[-1].strip() == "```":
                            cleaned_text = "\n".join(lines[1:-1])
                    parsed_json = json.loads(cleaned_text)
                except Exception as json_err:
                    if attempt < max_retries:
                        # Single repair retry
                        repair_prompt = (
                            prompt
                            + f"\n\nCRITICAL: Your previous output was invalid JSON ({json_err}). "
                            "Output strictly valid JSON only. Escape apostrophes and quotes properly."
                        )
                        contents[0] = repair_prompt
                        continue
                    raise

                # Extract token usage metadata safely
                usage_dict = {}
                if response.usage_metadata:
                    u = response.usage_metadata
                    usage_dict = {
                        "prompt_tokens": getattr(u, "prompt_token_count", None),
                        "candidates_tokens": getattr(u, "candidates_token_count", None),
                        "thoughts_tokens": getattr(u, "thoughts_token_count", None),
                        "total_tokens": getattr(u, "total_token_count", None),
                    }

                response_record = {
                    "model_requested": self.model_name,
                    "model_returned": getattr(response, "model_version", None) or self.model_name,
                    "finish_reason": finish_reason,
                    "elapsed_seconds": round(elapsed, 4),
                    "usage": usage_dict,
                    "raw_text": raw_text,
                    "parsed": parsed_json,
                }
                resp_file.write_text(json.dumps(response_record, indent=2))
                return parsed_json

            except Exception as e:
                last_error = e
                wait_time = min(2 ** attempt, 8)
                print(f"[GeminiTeacher] Attempt {attempt} failed ({e}). Retrying in {wait_time}s...")
                time.sleep(wait_time)

        raise RuntimeError(f"GeminiTeacher failed after {max_retries} attempts: {last_error}")
