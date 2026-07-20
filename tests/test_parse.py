from token_budget.parse import records_from_lines

ASSISTANT = (
    '{"type":"assistant","timestamp":"2026-07-20T10:00:00Z","sessionId":"s1",'
    '"isSidechain":false,"cwd":"C:/x/BIAP","message":{"model":"claude-opus-4-8",'
    '"role":"assistant","usage":{"input_tokens":1000,"cache_read_input_tokens":10000,'
    '"cache_creation_input_tokens":2000,"output_tokens":500,'
    '"cache_creation":{"ephemeral_5m_input_tokens":2000,"ephemeral_1h_input_tokens":0}}}}'
)
USER = '{"type":"user","message":{"role":"user","content":"hi"}}'
BAD = "{not json"


def test_extracts_assistant_usage():
    records = list(records_from_lines([ASSISTANT, USER, BAD, ""]))
    assert len(records) == 1
    record = records[0]
    assert record.model == "claude-opus-4-8"
    assert record.input == 1000
    assert record.cache_read == 10000
    assert record.cache_write_5m == 2000
    assert record.cache_write_1h == 0
    assert record.output == 500
    assert record.total == 13500
    assert record.is_sidechain is False


def test_cache_creation_fallback_to_5m():
    line = (
        '{"type":"assistant","timestamp":"t","sessionId":"s","message":'
        '{"model":"m","usage":{"cache_creation_input_tokens":777}}}'
    )
    record = list(records_from_lines([line]))[0]
    assert record.cache_write_5m == 777
    assert record.cache_write_1h == 0


def test_skips_non_assistant_and_malformed():
    assert list(records_from_lines([USER, BAD, "", "  "])) == []
