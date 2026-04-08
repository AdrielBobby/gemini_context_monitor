import pytest
from core.session_reader import SessionData, Message, UsageMetadata, Tokens
from core.calculator import calc_session_context, calc_avg_tokens_per_turn, CONTEXT_LIMIT

def test_session_data_validation():
    # Valid data
    data = {
        "sessionId": "test1",
        "messages": [
            {
                "model": "gemini-1.5-pro",
                "usageMetadata": {
                    "promptTokenCount": 1000,
                    "candidatesTokenCount": 50,
                    "cachedContentTokenCount": 0
                }
            }
        ]
    }
    session = SessionData.model_validate(data)
    assert len(session.messages) == 1
    assert session.messages[0].model == "gemini-1.5-pro"
    assert session.messages[0].usageMetadata.promptTokenCount == 1000

def test_calc_session_context():
    session = SessionData(
        sessionId="test2",
        messages=[
            Message(
                model="gemini-1.5-pro",
                usageMetadata=UsageMetadata(promptTokenCount=5000, candidatesTokenCount=100)
            )
        ]
    )
    stats = calc_session_context(session)
    assert stats is not None
    assert stats["input"] == 5000
    assert stats["output"] == 100
    assert stats["used"] == 5000
    assert stats["remaining"] == CONTEXT_LIMIT - 5000

def test_calc_avg_tokens_per_turn():
    session = SessionData(
        sessionId="test3",
        messages=[
            Message(usageMetadata=UsageMetadata(promptTokenCount=1000)),
            Message(usageMetadata=UsageMetadata(promptTokenCount=2000)),
        ]
    )
    avg = calc_avg_tokens_per_turn(session)
    assert avg == 1500
