from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from typing import Any

import anyio

from app.core.config import get_settings
from app.services.demo_data_service import execute_readonly_query, load_schema_metadata, render_schema_context, seed_demo_schema

PROTOCOL_TAG_PATTERN = re.compile(
    r"<(?P<tag>analysis_summary|final_answer)>\s*(?P<body>.*?)\s*</(?P=tag)>",
    re.IGNORECASE | re.DOTALL,
)


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def build_protocol_answer(final_answer: str, analysis_summary: str | None = None) -> str:
    parts: list[str] = []
    if analysis_summary and analysis_summary.strip():
        parts.append(f"<analysis_summary>\n{analysis_summary.strip()}\n</analysis_summary>")
    parts.append(f"<final_answer>\n{final_answer.strip()}\n</final_answer>")
    return "\n".join(parts)


def has_valid_protocol_answer(text: str) -> bool:
    normalized = (text or "").strip()
    if not normalized:
        return False

    final_count = 0
    position = 0
    matched = False
    for match in PROTOCOL_TAG_PATTERN.finditer(normalized):
        if normalized[position : match.start()].strip():
            return False
        matched = True
        position = match.end()
        if str(match.group("tag") or "").lower() == "final_answer" and str(match.group("body") or "").strip():
            final_count += 1

    return matched and not normalized[position:].strip() and final_count > 0


def replace_text_blocks(blocks: list[dict[str, Any]], replacement_text: str) -> list[dict[str, Any]]:
    replaced_blocks: list[dict[str, Any]] = []
    inserted = False
    for block in blocks:
        if block.get("type") == "text":
            if not inserted:
                replaced_blocks.append({"type": "text", "text": replacement_text})
                inserted = True
            continue
        replaced_blocks.append(block)
    if not inserted:
        replaced_blocks.append({"type": "text", "text": replacement_text})
    return replaced_blocks


def build_system_prompt(schema_context: str, skill_prompt: str) -> str:
    instructions = [
        "你是 OpenDataAgent 的数据分析智能体。",
        "你可以先解释、再调用工具，也可以先调用工具再给结论；不要为了输出 JSON 而牺牲正常 agent 行为。",
        "你要先把自然语言问题拆成：业务对象、指标、维度、时间范围、排序条件，再映射到 schema。",
        "当用户没有直接给表名时，要优先依据 schema context 的 business term mapping、table meaning 和 analysis recipes 做语义找表。",
        "涉及数据库事实、数量、趋势、排行、明细、Top N、时间范围的问题，都必须至少调用一次 mysql_query，不能臆测查询结果。",
        "你只能通过 mcp__analytics__mysql_query 访问数据库。",
        "只能编写单条只读 MySQL SQL，禁止写操作。",
        "如果问题是“谁最多/最高/Top 1”，需要在 SQL 中明确排序方向和 LIMIT。",
        "如果问题涉及“这个月/本月”，默认按当前自然月过滤，优先使用 orders.order_date。",
        "客户销售额通常使用 orders.total_amount 聚合，并通过 orders.customer_id 关联 customers.id。",
        "商品或品类销售额通常使用 order_items.line_amount 聚合，并通过 order_items.product_id 关联 products.id。",
        "在最终回答前，先确认所选表、关联键和指标口径是自洽的；如有歧义，先用更小的验证查询澄清。",
        "最终回答必须使用中文，简洁、结构化，并在有图表或表格时先给业务结论。",
        "最终回答至少要包含：核心结论、使用的口径/时间范围、关键数据。",
        "所有最终可见回答必须使用以下 XML 标签格式输出，且标签外不要输出额外正文：",
        "<analysis_summary>用于简短总结业务对象、指标、维度、时间范围、排序依据、选表依据、口径判断；如果本轮不需要 reasoning，可省略这个标签。</analysis_summary>",
        "<final_answer>用于输出最终业务结论、关键数字和必要口径说明；这个标签必须始终存在。</final_answer>",
        "不要在 final_answer 里复述“分析思路”“业务拆解”“口径判断”“步骤说明”这类过程性小标题。",
        "选表依据、关联键、排序逻辑、业务对象拆解这类过程信息只能放在 analysis_summary，不能放进 final_answer。",
        "final_answer 必须直接从业务结论起笔，再补关键数字和必要口径说明。",
        "final_answer 不得出现“尚需查询后确定”“需要先查询”“需进一步确认”这类过程性或不确定性表述。",
        "输出最终答案前先自检：必须只保留 analysis_summary 和 final_answer 这两个标签，不能缺 final_answer，不能在标签外输出 Markdown 标题、表格说明或额外句子。",
        "以下是可用 schema 上下文：",
        schema_context,
    ]
    if skill_prompt:
        instructions.extend(["", "业务风格补充：", skill_prompt])
    return "\n".join(instructions)


def build_user_prompt(prompt: str, conversation_context: str) -> str:
    if not conversation_context.strip():
        return prompt
    return "\n".join(
        [
            "以下是本轮之前的对话上下文，请优先沿用其中已经明确过的业务对象、口径和维度：",
            conversation_context,
            "",
            "以下是本轮新问题，请基于上述上下文继续分析：",
            prompt,
        ]
    )


def normalize_tool_name(name: str) -> str:
    if name.startswith("mcp__"):
        return name.split("__")[-1]
    return name


def build_assistant_message(blocks: list[dict[str, Any]], model: str) -> dict[str, Any]:
    return {
        "type": "assistant-message",
        "stepId": "step_1",
        "stepIndex": 1,
        "model": model,
        "blocks": blocks,
    }


def query_record(sql: str, database: str) -> dict[str, Any]:
    result = execute_readonly_query(sql)
    return {
        "sql": sql,
        "error": None,
        "database": database,
        "columns": result.columns,
        "rows": result.rows,
        "truncated": result.truncated,
    }


def is_numeric(value: object) -> bool:
    return isinstance(value, (int, float))


def summarize_series(rows: list[list[object | None]], columns: list[str]) -> str:
    if not rows or len(columns) < 2:
        return "查询已完成。"
    metric_name = columns[1]
    first = rows[0][1]
    last = rows[-1][1]
    if not (is_numeric(first) and is_numeric(last)):
        return "查询已完成，可结合表格进一步分析。"
    if last > first:
        direction = "整体上升"
    elif last < first:
        direction = "整体回落"
    else:
        direction = "整体持平"
    delta = last - first
    return f"{metric_name}从 {first} 变化到 {last}，{direction}，绝对变化 {delta}。"


def summarize_tables(record: dict[str, Any]) -> str:
    rows = record["rows"]
    names = [str(row[0]) for row in rows]
    return f"当前数据库里共有 {len(names)} 张表：{', '.join(names)}。"


def build_fixture_plan(prompt: str, conversation_context: str, schema_metadata: dict[str, Any], model: str) -> dict[str, Any]:
    database = schema_metadata["database"]
    lowered = prompt.lower()
    has_context = bool(conversation_context.strip())

    reasoning = (
        "我会先判断问题是否需要查询数据库；若涉及事实、数量、趋势或表结构，就调用 mysql_query，"
        "最后基于查询结果输出中文结论。"
    )
    if has_context:
        reasoning += " 这次会优先继承上一轮已经确认的业务对象和分析口径。"

    if not any(keyword in prompt for keyword in ["表", "趋势", "走势", "订单", "销量", "销售额", "sql", "明细", "排行", "月份", "天"]):
        answer = "我是 OpenDataAgent 的数据分析智能体，擅长把业务问题转成数据库查询，并给出带解释的图表、表格和结论。"
        return {
            "context": {
                "provider": "claude-agent-sdk-fixture",
                "model": model,
                "database": database,
                "toolWhitelist": ["mcp__analytics__mysql_query"],
                "schemaTables": [table["name"] for table in schema_metadata["tables"]],
                "hasConversationContext": has_context,
                "dataMode": "fixture",
            },
            "assistantMessages": [
                build_assistant_message([{"type": "text", "text": build_protocol_answer(answer)}], model),
            ],
            "toolRecords": [],
            "result": {
                "type": "result",
                "isError": False,
                "result": answer,
                "sessionId": "fixture-session",
                "model": model,
            },
        }

    if "几个表" in prompt or "哪些表" in prompt or ("数据库" in prompt and "表" in prompt):
        sql = (
            "SELECT table_name AS TABLE_NAME "
            "FROM information_schema.tables "
            f"WHERE table_schema = '{database}' "
            "ORDER BY table_name ASC"
        )
        record = query_record(sql, database)
        answer = summarize_tables(record)
        return {
            "context": {
                "provider": "claude-agent-sdk-fixture",
                "model": model,
                "database": database,
                "toolWhitelist": ["mcp__analytics__mysql_query"],
                "schemaTables": [table["name"] for table in schema_metadata["tables"]],
                "hasConversationContext": has_context,
                "dataMode": "fixture",
            },
            "assistantMessages": [
                build_assistant_message(
                    [{"type": "tool_use", "id": "tool_1", "name": "mysql_query", "input": {"sql": sql}}],
                    model,
                ),
                build_assistant_message(
                    [{"type": "tool_result", "tool_use_id": "tool_1", "content": {"rowCount": len(record["rows"])}}],
                    model,
                ),
                build_assistant_message(
                    [{"type": "text", "text": build_protocol_answer(answer, reasoning)}],
                    model,
                ),
            ],
            "toolRecords": [record],
            "result": {
                "type": "result",
                "isError": False,
                "result": answer,
                "sessionId": "fixture-session",
                "model": model,
            },
        }

    if "按月" in prompt or "月份" in prompt or "月度" in prompt:
        sql = """
        SELECT DATE_FORMAT(order_date, '%Y-%m') AS month, COUNT(*) AS order_count, ROUND(SUM(total_amount), 2) AS revenue
        FROM orders
        GROUP BY DATE_FORMAT(order_date, '%Y-%m')
        ORDER BY month ASC
        """
        record = query_record(sql, database)
        answer = f"{summarize_series(record['rows'], record['columns'])} 这次结果按月份聚合。"
        if has_context:
            answer = f"这次延续上一轮上下文，{answer}"
    elif "最近30天" in prompt or "30天" in prompt:
        sql = """
        SELECT DATE(order_date) AS order_day, COUNT(*) AS order_count, ROUND(SUM(total_amount), 2) AS revenue
        FROM orders
        WHERE order_date >= CURDATE() - INTERVAL 29 DAY
        GROUP BY DATE(order_date)
        ORDER BY order_day ASC
        """
        record = query_record(sql, database)
        answer = f"{summarize_series(record['rows'], record['columns'])} 这是最近 30 天的订单趋势。"
    else:
        sql = """
        SELECT DATE(order_date) AS order_day, COUNT(*) AS order_count, ROUND(SUM(total_amount), 2) AS revenue
        FROM orders
        WHERE order_date >= CURDATE() - INTERVAL 6 DAY
        GROUP BY DATE(order_date)
        ORDER BY order_day ASC
        """
        record = query_record(sql, database)
        answer = f"{summarize_series(record['rows'], record['columns'])} 这是最近 7 天的订单趋势。"

    if has_context:
        answer = f"这次延续上一轮上下文，{answer}"

    return {
        "context": {
            "provider": "claude-agent-sdk-fixture",
            "model": model,
            "database": database,
            "toolWhitelist": ["mcp__analytics__mysql_query"],
            "schemaTables": [table["name"] for table in schema_metadata["tables"]],
            "hasConversationContext": has_context,
            "dataMode": "fixture",
        },
        "assistantMessages": [
            build_assistant_message(
                [{"type": "tool_use", "id": "tool_1", "name": "mysql_query", "input": {"sql": sql.strip()}}],
                model,
            ),
            build_assistant_message(
                [{"type": "tool_result", "tool_use_id": "tool_1", "content": {"rowCount": len(record["rows"])}}],
                model,
            ),
            build_assistant_message(
                [{"type": "text", "text": build_protocol_answer(answer, reasoning)}],
                model,
            ),
        ],
        "toolRecords": [record],
        "result": {
            "type": "result",
            "isError": False,
            "result": answer,
            "sessionId": "fixture-session",
            "model": model,
        },
    }


async def run_fixture_agent(prompt: str, skill_prompt: str, conversation_context: str) -> dict[str, Any]:
    del skill_prompt
    settings = get_settings()
    seed_demo_schema(reset=False)
    schema_metadata = load_schema_metadata()
    return build_fixture_plan(prompt, conversation_context, schema_metadata, settings.anthropic_model)


async def run_live_agent(prompt: str, skill_prompt: str, conversation_context: str) -> dict[str, Any]:
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ResultMessage,
        TextBlock,
        ToolResultBlock,
        ToolUseBlock,
        create_sdk_mcp_server,
        query,
        tool,
    )

    settings = get_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required when using live claude-agent-sdk runtime")
    if not settings.anthropic_base_url:
        raise RuntimeError("ANTHROPIC_BASE_URL is required when using live claude-agent-sdk runtime")

    schema_metadata = load_schema_metadata()
    tool_records: list[dict[str, Any]] = []

    @tool(
        "mysql_query",
        (
            "Execute exactly one read-only MySQL query against the configured analytics database. "
            "If querying information_schema.tables, you must filter table_schema to the configured database. "
            "Use this after you have mapped the user's business terms to the correct tables and columns."
        ),
        {"sql": str},
    )
    async def mysql_query_tool(args: dict[str, Any]) -> dict[str, Any]:
        sql = str(args.get("sql") or "").strip()
        try:
            record = query_record(sql, schema_metadata["database"])
            tool_records.append(record)
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "database": record["database"],
                                "columns": record["columns"],
                                "rows": record["rows"],
                                "rowCount": len(record["rows"]),
                                "truncated": record["truncated"],
                            },
                            ensure_ascii=False,
                        ),
                    }
                ]
            }
        except Exception as exc:
            record = {
                "sql": sql,
                "error": str(exc),
                "database": schema_metadata["database"],
                "columns": [],
                "rows": [],
                "truncated": False,
            }
            tool_records.append(record)
            return {"content": [{"type": "text", "text": str(exc)}], "is_error": True}

    server = create_sdk_mcp_server(name="analytics", tools=[mysql_query_tool])

    with tempfile.TemporaryDirectory(prefix="claude-agent-sdk-") as home_dir:
        config_dir = os.path.join(home_dir, ".config")
        cache_dir = os.path.join(home_dir, ".cache")
        os.makedirs(config_dir, exist_ok=True)
        os.makedirs(cache_dir, exist_ok=True)
        runtime_env = {
            "ANTHROPIC_API_KEY": settings.anthropic_api_key or "",
            "ANTHROPIC_BASE_URL": settings.anthropic_base_url or "",
            "HOME": home_dir,
            "XDG_CONFIG_HOME": config_dir,
            "XDG_CACHE_HOME": cache_dir,
            "CI": "1",
        }

        async def repair_protocol_answer(text: str) -> str | None:
            if not text.strip():
                return None
            repair_options = ClaudeAgentOptions(
                tools=[],
                allowed_tools=[],
                mcp_servers={},
                system_prompt=(
                    "你是一个严格的输出格式整理器。"
                    "请把用户提供的中文业务回答改写成严格的 XML 协议。"
                    "只能输出可选的 <analysis_summary>...</analysis_summary> 和必需的 "
                    "<final_answer>...</final_answer>；标签外不能有任何额外文本。"
                    "不要新增事实，不要删掉核心结论、关键数字和必要口径。"
                    "业务对象、指标、维度、时间范围、排序依据、选表依据、关联键只能放进 analysis_summary。"
                    "final_answer 必须直接从最终业务结论起笔，不要先解释用哪些表、字段或关联关系。"
                    "final_answer 不得出现“尚需查询后确定”“需要先查询”“需进一步确认”这类过程性或不确定性表述。"
                ),
                model=settings.anthropic_model,
                max_turns=1,
                cwd=str(settings.repo_root),
                cli_path=settings.claude_cli_path,
                env=runtime_env,
                permission_mode="bypassPermissions",
                setting_sources=[],
            )
            repaired_chunks: list[str] = []
            with anyio.fail_after(min(settings.claude_sdk_timeout_seconds, 45)):
                async for repair_message in query(
                    prompt=(
                        "请把下面这段回答重写为严格 XML 协议格式：\n"
                        "<raw_answer>\n"
                        f"{text.strip()}\n"
                        "</raw_answer>"
                    ),
                    options=repair_options,
                ):
                    if isinstance(repair_message, AssistantMessage):
                        for repair_block in repair_message.content:
                            if isinstance(repair_block, TextBlock):
                                repaired_chunks.append(repair_block.text)
            repaired_text = "\n".join(chunk.strip() for chunk in repaired_chunks if chunk.strip()).strip()
            return repaired_text if has_valid_protocol_answer(repaired_text) else None

        options = ClaudeAgentOptions(
            tools=[],
            allowed_tools=["mcp__analytics__mysql_query"],
            mcp_servers={"analytics": server},
            system_prompt=build_system_prompt(render_schema_context(schema_metadata), skill_prompt),
            model=settings.anthropic_model,
            max_turns=8,
            cwd=str(settings.repo_root),
            cli_path=settings.claude_cli_path,
            env=runtime_env,
            permission_mode="bypassPermissions",
            setting_sources=[],
        )

        assistant_messages: list[dict[str, Any]] = []
        result_payload: dict[str, Any] | None = None
        with anyio.fail_after(settings.claude_sdk_timeout_seconds):
            async for message in query(prompt=build_user_prompt(prompt, conversation_context), options=options):
                if isinstance(message, AssistantMessage):
                    payload = build_assistant_message([], settings.anthropic_model)
                    for block in message.content:
                        if isinstance(block, ToolUseBlock):
                            payload["blocks"].append(
                                {
                                    "type": "tool_use",
                                    "id": block.id,
                                    "name": normalize_tool_name(block.name),
                                    "input": block.input,
                                }
                            )
                        elif isinstance(block, ToolResultBlock):
                            payload["blocks"].append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.tool_use_id,
                                    "content": getattr(block, "content", None),
                                }
                            )
                        elif isinstance(block, TextBlock):
                            payload["blocks"].append({"type": "text", "text": block.text})
                    if payload["blocks"]:
                        assistant_messages.append(payload)
                elif isinstance(message, ResultMessage):
                    result_payload = {
                        "type": "result",
                        "isError": message.is_error,
                        "result": message.result,
                        "sessionId": message.session_id,
                        "model": settings.anthropic_model,
                    }

        for assistant_message in assistant_messages:
            text_blocks = [block for block in assistant_message["blocks"] if block.get("type") == "text"]
            if not text_blocks:
                continue
            combined_text = "\n".join(str(block.get("text") or "") for block in text_blocks).strip()
            if has_valid_protocol_answer(combined_text):
                continue
            repaired_text = await repair_protocol_answer(combined_text)
            if repaired_text:
                assistant_message["blocks"] = replace_text_blocks(assistant_message["blocks"], repaired_text)

    return {
        "context": {
            "provider": "claude-agent-sdk",
            "model": settings.anthropic_model,
            "database": schema_metadata["database"],
            "toolWhitelist": ["mcp__analytics__mysql_query"],
            "schemaTables": [table["name"] for table in schema_metadata["tables"]],
            "hasConversationContext": bool(conversation_context.strip()),
            "dataMode": "live",
        },
        "assistantMessages": assistant_messages,
        "toolRecords": tool_records,
        "result": result_payload,
    }


async def run_agent(prompt: str, skill_prompt: str, conversation_context: str) -> dict[str, Any]:
    settings = get_settings()
    if settings.claude_agent_use_fixture_data:
        return await run_fixture_agent(prompt, skill_prompt, conversation_context)
    return await run_live_agent(prompt, skill_prompt, conversation_context)


def emit_payload(payload: dict[str, Any]) -> None:
    settings = get_settings()
    delay = settings.claude_agent_fixture_delay_ms / 1000 if settings.claude_agent_use_fixture_data else 0
    if delay:
        time.sleep(delay)

    tool_result_index = 0
    pending_tool_call_ids: list[str] = []
    for assistant_message in payload["assistantMessages"]:
        emit(assistant_message)
        if delay:
            time.sleep(delay)
        for block in assistant_message["blocks"]:
            if block["type"] == "tool_use" and block.get("id"):
                pending_tool_call_ids.append(str(block["id"]))
            elif block["type"] == "tool_result" and tool_result_index < len(payload["toolRecords"]):
                tool_call_id = str(
                    block.get("tool_use_id")
                    or (pending_tool_call_ids.pop(0) if pending_tool_call_ids else f"tool_{tool_result_index + 1}")
                )
                emit(
                    {
                        "type": "tool-result",
                        "stepId": "step_1",
                        "stepIndex": 1,
                        "toolCallId": tool_call_id,
                        "toolName": "mysql_query",
                        "record": payload["toolRecords"][tool_result_index],
                    }
                )
                if tool_call_id in pending_tool_call_ids:
                    pending_tool_call_ids.remove(tool_call_id)
                tool_result_index += 1
                if delay:
                    time.sleep(delay)

    while tool_result_index < len(payload["toolRecords"]) and pending_tool_call_ids:
        tool_call_id = pending_tool_call_ids.pop(0)
        emit(
            {
                "type": "tool-result",
                "stepId": "step_1",
                "stepIndex": 1,
                "toolCallId": tool_call_id,
                "toolName": "mysql_query",
                "record": payload["toolRecords"][tool_result_index],
            }
        )
        tool_result_index += 1
        if delay:
            time.sleep(delay)

    emit(
        {
            "type": "step-end",
            "stepId": "step_1",
            "stepIndex": 1,
            "title": "通过 Claude Agent SDK 分析并查询数据库",
            "stopReason": "completed",
            "model": payload["context"]["model"],
        }
    )
    if delay:
        time.sleep(delay)
    if payload["result"] is not None:
        emit(payload["result"])
        if payload["result"].get("isError"):
            raise RuntimeError(str(payload["result"].get("result") or "claude agent runtime returned an error"))
    emit({"type": "finish"})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--skill-id", required=True)
    parser.add_argument("--conversation-title", required=True)
    parser.add_argument("--prompt", required=True)
    args = parser.parse_args()

    del args.run_id, args.skill_id, args.conversation_title
    skill_prompt = os.getenv("AGENT_SKILL_PROMPT", "").strip()
    conversation_context = os.getenv("AGENT_CONVERSATION_CONTEXT", "").strip()
    settings = get_settings()
    emit(
        {
            "type": "run-context",
            "context": {
                "provider": "claude-agent-sdk",
                "model": settings.anthropic_model,
                "dataMode": "fixture" if settings.claude_agent_use_fixture_data else "live",
            },
        }
    )
    emit(
        {
            "type": "step-start",
            "stepId": "step_1",
            "stepIndex": 1,
            "title": "通过 Claude Agent SDK 分析并查询数据库",
            "model": settings.anthropic_model,
        }
    )
    payload = anyio.run(run_agent, args.prompt, skill_prompt, conversation_context)
    emit_payload(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
