from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from typing import Any

import anyio

from app.core.config import get_settings
from app.services.demo_data_service import execute_readonly_query, load_schema_metadata, render_schema_context, seed_demo_schema


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def build_system_prompt(schema_context: str, skill_prompt: str) -> str:
    instructions = [
        "你是 OpenDataAgent 的数据分析智能体。",
        "你可以先解释、再调用工具，也可以先调用工具再给结论；不要为了输出 JSON 而牺牲正常 agent 行为。",
        "你只能通过 mcp__analytics__mysql_query 访问数据库，不能臆测查询结果。",
        "凡是涉及数据库事实、数量、趋势、排行、明细的问题，都必须至少调用一次 mysql_query。",
        "只能编写单条只读 MySQL SQL，禁止写操作。",
        "最终回答必须使用中文，简洁、结构化，并在有图表或表格时先给业务结论。",
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
                build_assistant_message([{"type": "thinking", "thinking": reasoning}], model),
                build_assistant_message([{"type": "text", "text": answer}], model),
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
                build_assistant_message([{"type": "thinking", "thinking": reasoning}], model),
                build_assistant_message(
                    [{"type": "tool_use", "id": "tool_1", "name": "mysql_query", "input": {"sql": sql}}],
                    model,
                ),
                build_assistant_message(
                    [{"type": "tool_result", "tool_use_id": "tool_1", "content": {"rowCount": len(record["rows"])}}],
                    model,
                ),
                build_assistant_message([{"type": "text", "text": answer}], model),
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
            build_assistant_message([{"type": "thinking", "thinking": reasoning}], model),
            build_assistant_message(
                [{"type": "tool_use", "id": "tool_1", "name": "mysql_query", "input": {"sql": sql.strip()}}],
                model,
            ),
            build_assistant_message(
                [{"type": "tool_result", "tool_use_id": "tool_1", "content": {"rowCount": len(record["rows"])}}],
                model,
            ),
            build_assistant_message([{"type": "text", "text": answer}], model),
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
        ThinkingBlock,
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
            "If querying information_schema.tables, you must filter table_schema to the configured database."
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

        options = ClaudeAgentOptions(
            tools=[],
            allowed_tools=["mcp__analytics__mysql_query"],
            mcp_servers={"analytics": server},
            system_prompt=build_system_prompt(render_schema_context(schema_metadata), skill_prompt),
            model=settings.anthropic_model,
            max_turns=8,
            cwd=str(settings.repo_root),
            cli_path=settings.claude_cli_path,
            env={
                "ANTHROPIC_API_KEY": settings.anthropic_api_key or "",
                "ANTHROPIC_BASE_URL": settings.anthropic_base_url or "",
                "HOME": home_dir,
                "XDG_CONFIG_HOME": config_dir,
                "XDG_CACHE_HOME": cache_dir,
                "CI": "1",
            },
            permission_mode="bypassPermissions",
            setting_sources=[],
            effort="high",
        )

        assistant_messages: list[dict[str, Any]] = []
        result_payload: dict[str, Any] | None = None
        with anyio.fail_after(settings.claude_sdk_timeout_seconds):
            async for message in query(prompt=build_user_prompt(prompt, conversation_context), options=options):
                if isinstance(message, AssistantMessage):
                    payload = build_assistant_message([], settings.anthropic_model)
                    for block in message.content:
                        if isinstance(block, ThinkingBlock):
                            payload["blocks"].append({"type": "thinking", "thinking": block.thinking})
                        elif isinstance(block, ToolUseBlock):
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
    emit({"type": "run-context", "context": payload["context"]})
    delay = settings.claude_agent_fixture_delay_ms / 1000 if settings.claude_agent_use_fixture_data else 0

    emit(
        {
            "type": "step-start",
            "stepId": "step_1",
            "stepIndex": 1,
            "title": "通过 Claude Agent SDK 分析并查询数据库",
            "model": payload["context"]["model"],
        }
    )
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
    payload = anyio.run(run_agent, args.prompt, skill_prompt, conversation_context)
    emit_payload(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
