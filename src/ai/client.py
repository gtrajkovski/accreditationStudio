"""Conversational AI client with history management.

Wraps Anthropic SDK for interactive workflows with streaming support.
"""

from typing import Dict, List, Generator, Optional
import anthropic

from src.config import Config


class AIClient:
    """Conversational AI client that maintains conversation history.

    Supports both streaming and non-streaming responses.
    """

    DEFAULT_SYSTEM_PROMPT = (
        "You are a helpful accreditation compliance assistant specializing in "
        "post-secondary educational institution accreditation."
    )

    def __init__(self):
        """Initialize AI client with Anthropic API credentials.

        Raises:
            ValueError: If ANTHROPIC_API_KEY is not set in environment.
        """
        if not Config.ANTHROPIC_API_KEY:
            raise ValueError(
                "ANTHROPIC_API_KEY not set. Copy .env.example to .env and add your key."
            )

        self.client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
        self.model = Config.MODEL
        self.max_tokens = Config.MAX_TOKENS
        self.conversation_history: List[Dict[str, str]] = []

    def chat(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None
    ) -> str:
        """Send a message and get response, maintaining conversation history.

        Args:
            user_message: The user's message to send.
            system_prompt: Optional system prompt (defaults to accreditation assistant).
            model: Optional model override (defaults to self.model).

        Returns:
            The assistant's response text.

        Raises:
            anthropic.APIError: If API request fails.
        """
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        try:
            response = self.client.messages.create(
                model=model or self.model,
                max_tokens=self.max_tokens,
                system=system_prompt or self.DEFAULT_SYSTEM_PROMPT,
                messages=self.conversation_history
            )

            assistant_message = response.content[0].text

            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_message
            })

            return assistant_message

        except Exception:
            self.conversation_history.pop()
            raise

    def chat_stream(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None
    ) -> Generator[str, None, None]:
        """Send a message and stream response chunks, maintaining history.

        Args:
            user_message: The user's message to send.
            system_prompt: Optional system prompt.
            model: Optional model override (defaults to self.model).

        Yields:
            Text chunks as they arrive from the API.
        """
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        full_response = []

        try:
            with self.client.messages.stream(
                model=model or self.model,
                max_tokens=self.max_tokens,
                system=system_prompt or self.DEFAULT_SYSTEM_PROMPT,
                messages=self.conversation_history
            ) as stream:
                for text in stream.text_stream:
                    full_response.append(text)
                    yield text

            self.conversation_history.append({
                "role": "assistant",
                "content": "".join(full_response)
            })

        except Exception:
            self.conversation_history.pop()
            raise

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None
    ) -> str:
        """Generate a one-shot response without polluting conversation history.

        Useful for batch operations or standalone generations.

        Args:
            system_prompt: System instructions for the AI.
            user_prompt: The user's prompt.
            max_tokens: Optional token limit.
            model: Optional model override (defaults to self.model).

        Returns:
            The assistant's response text.
        """
        response = self.client.messages.create(
            model=model or self.model,
            max_tokens=max_tokens or self.max_tokens,
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": user_prompt
            }]
        )

        return response.content[0].text

    def generate_fast(
        self,
        system_prompt: str,
        user_prompt: str
    ) -> str:
        """Generate using fast model (Haiku) for simple tasks.

        Optimized for simple pattern recognition, classification, and extraction
        tasks with 90% cost savings compared to Sonnet.

        Args:
            system_prompt: System instructions for the AI.
            user_prompt: The user's prompt.

        Returns:
            The assistant's response text.
        """
        return self.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=Config.MODEL_FAST,
            max_tokens=Config.MAX_TOKENS_FAST
        )

    def generate_reasoning(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: Optional[int] = None
    ) -> str:
        """Generate using reasoning model (Sonnet) for complex tasks.

        Use for tasks requiring deep analysis, multi-step reasoning,
        or complex decision making.

        Args:
            system_prompt: System instructions for the AI.
            user_prompt: The user's prompt.
            max_tokens: Optional token limit.

        Returns:
            The assistant's response text.
        """
        return self.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=Config.MODEL_REASONING,
            max_tokens=max_tokens
        )

    def clear_history(self) -> None:
        """Reset conversation history to empty state."""
        self.conversation_history = []
