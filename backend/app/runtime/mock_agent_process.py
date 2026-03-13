from __future__ import annotations

import argparse
import json
import os
import sys
import time


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def chunk_text(text: str, size: int = 14) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] or [text]


def build_outputs(prompt: str) -> tuple[dict | None, dict | None, str]:
    lowered = prompt.lower()
    wants_chart = any(keyword in prompt for keyword in ["图", "趋势", "chart", "走势"])
    wants_table = wants_chart or any(keyword in prompt for keyword in ["表", "table", "明细"])

    table = None
    chart = None
    if wants_table:
        table = {
            "type": "data-table",
            "id": "table_1",
            "title": "最近七天指标明细",
            "columns": ["日期", "订单量", "销售额", "环比"],
            "rows": [
                ["03-07", 120, 9800, "+3%"],
                ["03-08", 132, 10320, "+7%"],
                ["03-09", 118, 9750, "-11%"],
                ["03-10", 141, 11020, "+19%"],
                ["03-11", 149, 11880, "+6%"],
                ["03-12", 153, 12040, "+2%"],
                ["03-13", 161, 12980, "+8%"],
            ],
            "summary": "订单量和销售额整体上行，3 月 9 日出现短暂回落。",
            "stepId": "step_1",
        }
    if wants_chart:
        chart = {
            "type": "data-chart",
            "id": "chart_1",
            "title": "订单量趋势",
            "chartType": "line",
            "spec": {
                "xAxis": {"type": "category", "data": ["03-07", "03-08", "03-09", "03-10", "03-11", "03-12", "03-13"]},
                "yAxis": {"type": "value"},
                "series": [{"type": "line", "smooth": True, "data": [120, 132, 118, 141, 149, 153, 161]}],
                "tooltip": {"trigger": "axis"},
            },
            "summary": "近七天订单量呈上升趋势，末端加速明显。",
            "stepId": "step_1",
        }

    conclusion = "我已结合最近七天的模拟业务数据给出结论：整体趋势向上，短期波动后恢复增长。"
    if "sql" in lowered:
        conclusion += " 同时保留了 SQL 查询轨迹以便审计。"
    if wants_chart:
        conclusion += " 已生成趋势图帮助快速判断拐点。"
    if wants_table:
        conclusion += " 明细表可用于进一步下钻。"
    return table, chart, conclusion


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--skill-id", required=True)
    parser.add_argument("--conversation-title", required=True)
    parser.add_argument("--prompt", required=True)
    args = parser.parse_args()

    delay = int(os.getenv("MOCK_AGENT_DELAY_MS", "60")) / 1000
    reasoning = f"根据 skill {args.skill_id} 和当前问题，我会先组织分析步骤，再调用数据工具，并最后生成摘要。"
    table, chart, conclusion = build_outputs(args.prompt)

    emit({"type": "start-step", "stepId": "step_1", "title": "分析并组织结果"})
    time.sleep(delay)
    emit({"type": "reasoning-start", "id": "reasoning_1", "stepId": "step_1"})
    time.sleep(delay)
    for chunk in chunk_text(reasoning):
        emit({"type": "reasoning-delta", "id": "reasoning_1", "delta": chunk, "stepId": "step_1"})
        time.sleep(delay)
    emit({"type": "reasoning-end", "id": "reasoning_1", "stepId": "step_1"})
    time.sleep(delay)

    tool_input = {
        "sql": "SELECT day, orders, revenue FROM metrics_last_7_days ORDER BY day ASC",
        "purpose": "获取最近七天业务指标",
    }
    emit({"type": "tool-input-start", "toolCallId": "tool_1", "toolName": "mysql_query", "stepId": "step_1"})
    time.sleep(delay)
    emit(
        {
            "type": "tool-input-delta",
            "toolCallId": "tool_1",
            "toolName": "mysql_query",
            "delta": json.dumps(tool_input, ensure_ascii=False),
            "stepId": "step_1",
        }
    )
    time.sleep(delay)
    emit(
        {
            "type": "tool-input-available",
            "toolCallId": "tool_1",
            "toolName": "mysql_query",
            "input": tool_input,
            "stepId": "step_1",
        }
    )
    time.sleep(delay)
    emit(
        {
            "type": "tool-output-available",
            "toolCallId": "tool_1",
            "toolName": "mysql_query",
            "output": {"rowCount": 7, "summary": "返回 7 条日级业务记录"},
            "stepId": "step_1",
        }
    )
    time.sleep(delay)

    if table is not None:
        emit(table)
        time.sleep(delay)
    if chart is not None:
        emit(chart)
        time.sleep(delay)

    emit({"type": "text-start", "id": "text_1", "stepId": "step_1"})
    time.sleep(delay)
    for chunk in chunk_text(conclusion, size=18):
        emit({"type": "text-delta", "id": "text_1", "delta": chunk, "stepId": "step_1"})
        time.sleep(delay)
    emit({"type": "text-end", "id": "text_1", "stepId": "step_1"})
    time.sleep(delay)
    emit({"type": "finish-step", "stepId": "step_1", "title": "分析并组织结果"})
    time.sleep(delay)
    emit({"type": "finish"})
    return 0


if __name__ == "__main__":
    sys.exit(main())

