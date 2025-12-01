"""Claude API client for AI analysis.

Handles API calls to Anthropic's Claude with retries, rate limiting,
and response parsing.
"""

import json
import time
from typing import Optional

import anthropic

from common.config import config
from common.logger import setup_logger

logger = setup_logger(__name__)

# Model configurations
MODELS = {
    "opus": "claude-opus-4-20250514",
    "sonnet": "claude-sonnet-4-20250514",
    "haiku": "claude-3-5-haiku-20241022",
}

# Pricing per million tokens (as of 2025)
PRICING = {
    "opus": {"input": 15.00, "output": 75.00},
    "sonnet": {"input": 3.00, "output": 15.00},
    "haiku": {"input": 0.25, "output": 1.25},
}


class APIClient:
    """Client for Claude API calls."""

    def __init__(self, model: str = "opus"):
        """
        Initialize API client.

        Args:
            model: Model to use ("opus", "sonnet", or "haiku")
        """
        api_key = config.ANTHROPIC_API_KEY
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set in environment")

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = MODELS.get(model, MODELS["opus"])
        self.model_name = model
        self.pricing = PRICING.get(model, PRICING["opus"])

    def call(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 8192,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> tuple:
        """
        Call Claude API with retry logic.

        Args:
            system_prompt: System prompt text
            user_prompt: User prompt text
            max_tokens: Maximum response tokens
            max_retries: Number of retries on failure
            retry_delay: Delay between retries (multiplied each retry)

        Returns:
            tuple: (response_dict, input_tokens, output_tokens, cost_estimate)
        """
        for attempt in range(max_retries):
            try:
                logger.info(f"Calling Claude API ({self.model_name})...")

                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ],
                )

                # Extract response text
                response_text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        response_text += block.text

                # Parse JSON from response
                parsed = self._parse_json_response(response_text)

                # Calculate usage
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                cost = self._calculate_cost(input_tokens, output_tokens)

                logger.info(
                    f"API call successful: {input_tokens} in, {output_tokens} out, ${cost:.4f}"
                )

                return parsed, input_tokens, output_tokens, cost

            except anthropic.RateLimitError as e:
                logger.warning(f"Rate limited, waiting {retry_delay}s...")
                time.sleep(retry_delay)
                retry_delay *= 2

            except anthropic.APIError as e:
                logger.error(f"API error (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.debug(f"Raw response: {response_text[:500]}...")
                raise ValueError(f"Invalid JSON in API response: {e}")

        raise RuntimeError(f"Failed after {max_retries} attempts")

    def _parse_json_response(self, text: str) -> dict:
        """
        Parse JSON from response text.

        Handles cases where JSON is wrapped in markdown code blocks.
        """
        text = text.strip()

        # Try direct parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                return json.loads(text[start:end].strip())

        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                return json.loads(text[start:end].strip())

        # Try finding JSON object boundaries
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])

        raise json.JSONDecodeError("Could not find JSON in response", text, 0)

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost estimate based on token usage."""
        input_cost = (input_tokens / 1_000_000) * self.pricing["input"]
        output_cost = (output_tokens / 1_000_000) * self.pricing["output"]
        return input_cost + output_cost


def call_claude(
    system_prompt: str,
    user_prompt: str,
    model: str = "opus",
    max_tokens: int = 8192,
) -> tuple:
    """
    Convenience function to call Claude API.

    Args:
        system_prompt: System prompt text
        user_prompt: User prompt text
        model: Model to use ("opus", "sonnet", "haiku")
        max_tokens: Maximum response tokens

    Returns:
        tuple: (response_dict, input_tokens, output_tokens, cost_estimate)
    """
    client = APIClient(model=model)
    return client.call(system_prompt, user_prompt, max_tokens=max_tokens)


def estimate_cost(input_chars: int, model: str = "opus") -> float:
    """
    Estimate API cost for a given input size.

    Args:
        input_chars: Number of input characters
        model: Model to use

    Returns:
        Estimated cost in dollars
    """
    # Rough estimate: 4 chars per token
    input_tokens = input_chars // 4
    # Assume output is ~2K tokens for analysis
    output_tokens = 2000

    pricing = PRICING.get(model, PRICING["opus"])
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]

    return input_cost + output_cost
