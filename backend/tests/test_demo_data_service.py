from __future__ import annotations

from app.core.config import reset_settings_cache
from app.services.demo_data_service import execute_readonly_query, load_schema_metadata, normalize_readonly_sql, seed_demo_schema


def test_seed_demo_schema_and_query_flow(monkeypatch) -> None:
    monkeypatch.setenv("AGENT_DATA_MYSQL_DATABASE", "opendata_agent_demo_test")
    reset_settings_cache()

    payload = seed_demo_schema(reset=True)
    assert payload["tables"] == 4
    assert payload["orders"] > 0

    metadata = load_schema_metadata()
    assert metadata["database"] == "opendata_agent_demo_test"
    assert [table["name"] for table in metadata["tables"]] == ["customers", "order_items", "orders", "products"]

    order_count = execute_readonly_query("SELECT COUNT(*) AS order_count FROM orders")
    assert order_count.columns == ["order_count"]
    assert order_count.rows[0][0] == payload["orders"]

    trend = execute_readonly_query(
        """
        SELECT DATE(order_date) AS order_day, COUNT(*) AS order_count
        FROM orders
        GROUP BY DATE(order_date)
        ORDER BY order_day ASC
        LIMIT 5
        """
    )
    assert trend.columns == ["order_day", "order_count"]
    assert len(trend.rows) == 5


def test_normalize_readonly_sql_rejects_mutation() -> None:
    assert normalize_readonly_sql("SELECT 1;") == "SELECT 1"
    try:
        normalize_readonly_sql("UPDATE orders SET total_amount = 0")
    except ValueError as exc:
        assert "Dangerous SQL keyword" in str(exc) or "Only read-only" in str(exc)
    else:
        raise AssertionError("Expected mutation SQL to be rejected")
