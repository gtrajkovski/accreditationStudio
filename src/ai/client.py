"""Conversational AI client with history management.

Wraps Anthropic SDK for interactive workflows with streaming support.
"""

from typing import Dict, List, Generator, Optional, Any
import anthropic

from src.config import Config
from src.services.cost_tracking_service import log_api_call


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
        model: Optional[str] = None,
        track_cost: bool = True,
        institution_id: Optional[str] = None,
        operation: Optional[str] = None
    ) -> str:
        """Send a message and get response, maintaining conversation history.

        Args:
            user_message: The user's message to send.
            system_prompt: Optional system prompt (defaults to accreditation assistant).
            model: Optional model override (defaults to self.model).
            track_cost: Whether to log cost (default True).
            institution_id: Institution ID for cost tracking.
            operation: Operation type for cost tracking (e.g., 'chat').

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

            # Log cost (Phase 29)
            if track_cost:
                log_api_call(
                    model=model or self.model,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    institution_id=institution_id,
                    operation=operation or "chat"
                )

            return assistant_message

        except Exception:
            self.conversation_history.pop()
            raise

    def chat_stream(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        track_cost: bool = True,
        institution_id: Optional[str] = None,
        operation: Optional[str] = None
    ) -> Generator[str, None, None]:
        """Send a message and stream response chunks, maintaining history.

        Args:
            user_message: The user's message to send.
            system_prompt: Optional system prompt.
            model: Optional model override (defaults to self.model).
            track_cost: Whether to log cost (default True).
            institution_id: Institution ID for cost tracking.
            operation: Operation type for cost tracking (e.g., 'chat').

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

                # Get usage from stream after completion
                final_message = stream.get_final_message()

            self.conversation_history.append({
                "role": "assistant",
                "content": "".join(full_response)
            })

            # Log cost (Phase 29)
            if track_cost:
                log_api_call(
                    model=model or self.model,
                    input_tokens=final_message.usage.input_tokens,
                    output_tokens=final_message.usage.output_tokens,
                    institution_id=institution_id,
                    operation=operation or "chat"
                )

        except Exception:
            self.conversation_history.pop()
            raise

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        track_cost: bool = True,
        institution_id: Optional[str] = None,
        agent_type: Optional[str] = None,
        operation: Optional[str] = None
    ) -> str:
        """Generate a one-shot response without polluting conversation history.

        Useful for batch operations or standalone generations.

        Args:
            system_prompt: System instructions for the AI.
            user_prompt: The user's prompt.
            max_tokens: Optional token limit.
            model: Optional model override (defaults to self.model).
            track_cost: Whether to log cost (default True).
            institution_id: Institution ID for cost tracking.
            agent_type: Agent type for cost tracking.
            operation: Operation type for cost tracking.

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

        # Log cost (Phase 29)
        if track_cost:
            log_api_call(
                model=model or self.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                institution_id=institution_id,
                agent_type=agent_type,
                operation=operation
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

    def submit_batch(
        self,
        requests: List[Dict[str, Any]],
        track_cost: bool = True
    ) -> Dict[str, Any]:
        """Submit a batch of requests to Anthropic Batch API.

        Args:
            requests: List of dicts with 'custom_id' and 'params' keys.
                      params contains model, max_tokens, messages, system.
            track_cost: Whether to log estimated cost (actual logged on completion)

        Returns:
            Dict with batch_id, processing_status, request_counts, expires_at
        """
        from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
        from anthropic.types.messages.batch_create_params import Request

        # Convert to Anthropic format
        batch_requests = []
        for req in requests:
            batch_requests.append(
                Request(
                    custom_id=req["custom_id"],
                    params=MessageCreateParamsNonStreaming(**req["params"])
                )
            )

        batch = self.client.messages.batches.create(requests=batch_requests)

        return {
            "batch_id": batch.id,
            "processing_status": batch.processing_status,
            "request_counts": {
                "processing": batch.request_counts.processing,
                "succeeded": batch.request_counts.succeeded,
                "errored": batch.request_counts.errored,
                "canceled": batch.request_counts.canceled,
                "expired": batch.request_counts.expired,
            },
            "created_at": batch.created_at,
            "expires_at": batch.expires_at,
            "results_url": batch.results_url,
        }

    def get_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """Get status of an Anthropic batch job."""
        batch = self.client.messages.batches.retrieve(batch_id)
        return {
            "batch_id": batch.id,
            "processing_status": batch.processing_status,
            "request_counts": {
                "processing": batch.request_counts.processing,
                "succeeded": batch.request_counts.succeeded,
                "errored": batch.request_counts.errored,
                "canceled": batch.request_counts.canceled,
                "expired": batch.request_counts.expired,
            },
            "ended_at": batch.ended_at,
            "results_url": batch.results_url,
        }

    def get_batch_results(self, batch_id: str) -> Generator[Dict[str, Any], None, None]:
        """Stream results from a completed Anthropic batch.

        Yields:
            Dict with custom_id, result_type, message (if succeeded), error (if errored)
        """
        for result in self.client.messages.batches.results(batch_id):
            yield {
                "custom_id": result.custom_id,
                "result_type": result.result.type,
                "message": result.result.message if result.result.type == "succeeded" else None,
                "error": result.result.error if result.result.type == "errored" else None,
            }
