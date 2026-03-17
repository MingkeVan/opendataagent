from __future__ import annotations

from app.db.session import session_scope
from app.services.conversation_service import create_conversation
from app.services.run_service import (
    build_message_projection,
    create_run,
    parse_protocol_answer_text,
    process_agent_event,
)


def test_parse_protocol_answer_text_requires_clean_xml_envelope() -> None:
    analysis_summary, final_answer = parse_protocol_answer_text(
        "<analysis_summary>业务对象：客户</analysis_summary>\n"
        "<final_answer>本月销售额最高的客户是木棉生活。</final_answer>"
    )
    assert analysis_summary == "业务对象：客户"
    assert final_answer == "本月销售额最高的客户是木棉生活。"

    invalid_analysis, invalid_final = parse_protocol_answer_text(
        "先说明一下分析过程\n<final_answer>这里有结论</final_answer>"
    )
    assert invalid_analysis is None
    assert invalid_final is None


def test_projection_splits_analysis_summary_and_final_answer() -> None:
    with session_scope() as session:
        conversation = create_conversation(session, "projection", "demo-analyst")
        _, _, run = create_run(session, conversation, "这个月哪个用户产生的销售额最多？")

        process_agent_event(
            session,
            run,
            0,
            {
                "type": "assistant-message",
                "stepId": "step_1",
                "stepIndex": 1,
                "model": "claude-opus-4-6",
                "blocks": [
                    {
                        "type": "text",
                        "text": (
                            "<analysis_summary>\n"
                            "- 业务对象：客户\n"
                            "- 指标：SUM(orders.total_amount)\n"
                            "- 时间范围：本月\n"
                            "</analysis_summary>\n"
                            "<final_answer>\n"
                            "本月销售额最高的客户是木棉生活，累计销售额 ¥13,472。\n\n"
                            "口径：按当前自然月汇总 orders.total_amount。\n"
                            "</final_answer>"
                        ),
                    }
                ],
            },
        )
        session.commit()

        ui_parts, content_blocks, final_text, trace_summary = build_message_projection(session, run)

    reasoning = next(part for part in ui_parts if part["type"] == "reasoning")
    text_part = next(part for part in ui_parts if part["type"] == "text")
    assert "SUM(orders.total_amount)" in reasoning["summary"]
    assert text_part["text"].startswith("本月销售额最高的客户是木棉生活")
    assert "业务对象" not in text_part["text"]
    assert any(block["type"] == "thinking" for block in content_blocks)
    assert any(block["type"] == "text" for block in content_blocks)
    assert final_text.startswith("本月销售额最高的客户是木棉生活")
    assert trace_summary["hasReasoning"] is True


def test_projection_keeps_plain_text_when_protocol_is_missing() -> None:
    with session_scope() as session:
        conversation = create_conversation(session, "projection", "demo-analyst")
        _, _, run = create_run(session, conversation, "你是谁？")

        process_agent_event(
            session,
            run,
            0,
            {
                "type": "assistant-message",
                "stepId": "step_1",
                "stepIndex": 1,
                "model": "claude-opus-4-6",
                "blocks": [
                    {
                        "type": "text",
                        "text": "我是 OpenDataAgent，可以把业务问题转成 SQL 并返回结论。",
                    }
                ],
            },
        )
        session.commit()

        ui_parts, _, final_text, trace_summary = build_message_projection(session, run)

    assert [part["type"] for part in ui_parts] == ["step", "text"]
    assert final_text == "我是 OpenDataAgent，可以把业务问题转成 SQL 并返回结论。"
    assert trace_summary["hasReasoning"] is False


def test_projection_parses_protocol_across_contiguous_text_blocks() -> None:
    with session_scope() as session:
        conversation = create_conversation(session, "projection", "demo-analyst")
        _, _, run = create_run(session, conversation, "这个月哪个用户产生的销售额最多？")

        process_agent_event(
            session,
            run,
            0,
            {
                "type": "assistant-message",
                "stepId": "step_1",
                "stepIndex": 1,
                "model": "claude-opus-4-6",
                "blocks": [
                    {
                        "type": "text",
                        "text": "<analysis_summary>业务对象：客户；指标：SUM(orders.total_amount)。</analysis_summary>",
                    },
                    {
                        "type": "text",
                        "text": "<final_answer>本月销售额最高的客户是木棉生活。</final_answer>",
                    },
                ],
            },
        )
        session.commit()

        ui_parts, _, final_text, trace_summary = build_message_projection(session, run)

    assert [part["type"] for part in ui_parts] == ["step", "reasoning", "text"]
    assert final_text == "本月销售额最高的客户是木棉生活。"
    assert trace_summary["hasReasoning"] is True
