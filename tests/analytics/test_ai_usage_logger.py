from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.analytics.ai_usage_logger import (
    _estimate_cost,
    invoke_structured_with_usage,
)


class _Structured:
    def invoke(self, _prompt):
        return {
            "parsed": {"ok": True},
            "raw": SimpleNamespace(
                usage_metadata={
                    "input_tokens": 100,
                    "output_tokens": 50,
                },
                response_metadata={},
            ),
            "parsing_error": None,
        }


class ChatOpenAIStub:
    model_name = "gpt-4o"

    def with_structured_output(self, _schema, include_raw=False):
        assert include_raw is True
        return _Structured()


@patch("app.analytics.ai_usage_logger.log_ai_usage")
def test_structured_invocation_records_real_usage_metadata(mock_log):
    workspace_id = uuid4()
    result = invoke_structured_with_usage(
        model=ChatOpenAIStub(),
        schema=dict,
        prompt="hello",
        workspace_id=workspace_id,
        generated_post_id=None,
        agent_purpose="writer",
    )

    assert result == {"ok": True}
    kwargs = mock_log.call_args.kwargs
    assert kwargs["workspace_id"] == workspace_id
    assert kwargs["provider"] == "openai"
    assert kwargs["model"] == "gpt-4o"
    assert kwargs["prompt_tokens"] == 100
    assert kwargs["completion_tokens"] == 50


def test_known_model_cost_and_unknown_model_behavior():
    assert _estimate_cost("openai", "gpt-4o", 1000, 1000) == Decimal("0.012500")
    assert _estimate_cost("gemini", "unknown-future-model", 1000, 1000) is None
    assert _estimate_cost("ollama", "llama3", 1000, 1000) == Decimal("0")
