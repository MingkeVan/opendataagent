from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pymysql

from app.core.config import get_settings

FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|call|rename|replace|load|outfile|dumpfile|set)\b",
    re.IGNORECASE,
)
COMMENT_PATTERN = re.compile(r"(--[^\n]*$)|(/\*.*?\*/)", re.MULTILINE | re.DOTALL)


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[list[object | None]]
    truncated: bool


def _connect(*, database: str | None) -> pymysql.connections.Connection:
    settings = get_settings()
    return pymysql.connect(
        host=settings.agent_data_mysql_host,
        port=settings.agent_data_mysql_port,
        user=settings.agent_data_mysql_user,
        password=settings.agent_data_mysql_password,
        database=database,
        charset="utf8mb4",
        autocommit=True,
    )


def _serialize_cell(value: object | None) -> object | None:
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return value


def ensure_data_database() -> None:
    settings = get_settings()
    conn = _connect(database=None)
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{settings.agent_data_mysql_database}` "
                "DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_0900_ai_ci"
            )
    finally:
        conn.close()


def seed_demo_schema(*, reset: bool = True) -> dict:
    settings = get_settings()
    ensure_data_database()
    conn = _connect(database=settings.agent_data_mysql_database)
    try:
        with conn.cursor() as cursor:
            if reset:
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
                cursor.execute("DROP TABLE IF EXISTS order_items")
                cursor.execute("DROP TABLE IF EXISTS orders")
                cursor.execute("DROP TABLE IF EXISTS products")
                cursor.execute("DROP TABLE IF EXISTS customers")
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS customers (
                    id BIGINT PRIMARY KEY,
                    customer_name VARCHAR(128) NOT NULL,
                    city VARCHAR(64) NOT NULL,
                    signup_date DATE NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id BIGINT PRIMARY KEY,
                    product_name VARCHAR(128) NOT NULL,
                    category VARCHAR(64) NOT NULL,
                    unit_price DECIMAL(10, 2) NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id BIGINT PRIMARY KEY,
                    customer_id BIGINT NOT NULL,
                    order_date DATETIME NOT NULL,
                    order_status VARCHAR(32) NOT NULL,
                    total_amount DECIMAL(12, 2) NOT NULL,
                    KEY idx_orders_date (order_date),
                    CONSTRAINT fk_orders_customer
                        FOREIGN KEY (customer_id) REFERENCES customers (id)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS order_items (
                    id BIGINT PRIMARY KEY,
                    order_id BIGINT NOT NULL,
                    product_id BIGINT NOT NULL,
                    quantity INT NOT NULL,
                    unit_price DECIMAL(10, 2) NOT NULL,
                    line_amount DECIMAL(12, 2) NOT NULL,
                    KEY idx_items_order (order_id),
                    KEY idx_items_product (product_id),
                    CONSTRAINT fk_items_order
                        FOREIGN KEY (order_id) REFERENCES orders (id),
                    CONSTRAINT fk_items_product
                        FOREIGN KEY (product_id) REFERENCES products (id)
                )
                """
            )

            cursor.execute("DELETE FROM order_items")
            cursor.execute("DELETE FROM orders")
            cursor.execute("DELETE FROM products")
            cursor.execute("DELETE FROM customers")

            customers = [
                (1, "星海贸易", "上海", "2025-10-02"),
                (2, "晨光零售", "杭州", "2025-10-12"),
                (3, "远山咖啡", "北京", "2025-11-03"),
                (4, "北辰商超", "南京", "2025-11-14"),
                (5, "木棉生活", "深圳", "2025-12-01"),
                (6, "云图文创", "苏州", "2025-12-18"),
                (7, "长风百货", "成都", "2026-01-05"),
                (8, "海岸精选", "宁波", "2026-01-18"),
            ]
            products = [
                (1, "经典手冲壶", "咖啡器具", "168.00"),
                (2, "滤纸套装", "耗材", "36.00"),
                (3, "冷萃咖啡液", "饮品", "58.00"),
                (4, "便携保温杯", "周边", "88.00"),
                (5, "精品拼配豆", "咖啡豆", "128.00"),
                (6, "燕麦奶组合", "饮品", "42.00"),
            ]
            cursor.executemany(
                "INSERT INTO customers (id, customer_name, city, signup_date) VALUES (%s, %s, %s, %s)",
                customers,
            )
            cursor.executemany(
                "INSERT INTO products (id, product_name, category, unit_price) VALUES (%s, %s, %s, %s)",
                products,
            )

            base_day = date.today() - timedelta(days=60)
            orders: list[tuple[object, ...]] = []
            order_items: list[tuple[object, ...]] = []
            order_id = 1
            item_id = 1
            product_price_map = {int(item[0]): Decimal(str(item[3])) for item in products}
            for day_index in range(60):
                day = base_day + timedelta(days=day_index)
                order_count = 6 + day_index // 5 + (day_index % 4)
                for slot in range(order_count):
                    customer_id = (day_index + slot) % len(customers) + 1
                    placed_at = datetime.combine(
                        day,
                        time(hour=(slot * 2 + day_index) % 20 + 1, minute=(day_index * 7 + slot * 11) % 60),
                    )
                    status = "paid" if slot % 5 else "shipped"
                    item_count = 1 + ((order_id + day_index) % 3)
                    total_amount = Decimal("0.00")
                    for item_offset in range(item_count):
                        product_id = (day_index + slot + item_offset) % len(products) + 1
                        quantity = 1 + ((day_index + item_offset) % 3)
                        unit_price = product_price_map[product_id]
                        line_amount = unit_price * quantity
                        total_amount += line_amount
                        order_items.append(
                            (
                                item_id,
                                order_id,
                                product_id,
                                quantity,
                                f"{unit_price:.2f}",
                                f"{line_amount:.2f}",
                            )
                        )
                        item_id += 1
                    orders.append(
                        (
                            order_id,
                            customer_id,
                            placed_at.strftime("%Y-%m-%d %H:%M:%S"),
                            status,
                            f"{total_amount:.2f}",
                        )
                    )
                    order_id += 1

            cursor.executemany(
                """
                INSERT INTO orders (id, customer_id, order_date, order_status, total_amount)
                VALUES (%s, %s, %s, %s, %s)
                """,
                orders,
            )
            cursor.executemany(
                """
                INSERT INTO order_items (id, order_id, product_id, quantity, unit_price, line_amount)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                order_items,
            )

        return {
            "database": settings.agent_data_mysql_database,
            "tables": 4,
            "customers": len(customers),
            "products": len(products),
            "orders": len(orders),
            "order_items": len(order_items),
        }
    finally:
        conn.close()


def load_schema_metadata() -> dict:
    settings = get_settings()
    ensure_data_database()
    conn = _connect(database=settings.agent_data_mysql_database)
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = %s
                ORDER BY table_name
                """,
                (settings.agent_data_mysql_database,),
            )
            table_names = [row[0] for row in cursor.fetchall()]
            cursor.execute(
                """
                SELECT table_name, column_name, data_type, column_key, is_nullable
                FROM information_schema.columns
                WHERE table_schema = %s
                ORDER BY table_name, ordinal_position
                """,
                (settings.agent_data_mysql_database,),
            )
            column_rows = cursor.fetchall()
            cursor.execute(
                """
                SELECT table_name, column_name, referenced_table_name, referenced_column_name
                FROM information_schema.key_column_usage
                WHERE table_schema = %s AND referenced_table_name IS NOT NULL
                ORDER BY table_name, ordinal_position
                """,
                (settings.agent_data_mysql_database,),
            )
            relationships = [
                {
                    "table": row[0],
                    "column": row[1],
                    "referenced_table": row[2],
                    "referenced_column": row[3],
                }
                for row in cursor.fetchall()
            ]
    finally:
        conn.close()

    tables: dict[str, dict] = {name: {"name": name, "columns": []} for name in table_names}
    for table_name, column_name, data_type, column_key, is_nullable in column_rows:
        tables[table_name]["columns"].append(
            {
                "name": column_name,
                "data_type": data_type,
                "column_key": column_key,
                "nullable": is_nullable == "YES",
            }
        )
    return {
        "database": settings.agent_data_mysql_database,
        "tables": [tables[name] for name in table_names],
        "relationships": relationships,
        "semantic_guidance": build_semantic_guidance(),
    }


def build_semantic_guidance() -> dict:
    return {
        "business_terms": {
            "用户": ["customers", "customer_name", "customer_id"],
            "客户": ["customers", "customer_name", "customer_id"],
            "订单": ["orders", "order_date", "order_status", "total_amount"],
            "销售额": ["orders.total_amount", "order_items.line_amount"],
            "收入": ["orders.total_amount", "order_items.line_amount"],
            "商品": ["products", "product_name", "category", "product_id"],
            "品类": ["products.category"],
            "销量": ["order_items.quantity"],
        },
        "table_descriptions": {
            "customers": "客户主数据表，包含客户名称、城市、注册时间。涉及用户、客户、买家时优先考虑。",
            "orders": (
                "订单头表，每行代表一笔订单，包含 customer_id、order_date、order_status、total_amount。"
                "涉及订单量、订单金额、客户销售额、按天/月趋势时通常以这张表为主。"
            ),
            "order_items": (
                "订单明细表，每行代表订单中的一个商品行，包含 product_id、quantity、line_amount。"
                "涉及商品销量、商品销售额、品类分析时通常以这张表为主。"
            ),
            "products": "商品维度表，包含商品名称、品类、标价。涉及商品、SKU、品类时需要与 order_items 联表。",
        },
        "analysis_recipes": [
            {
                "question": "按客户统计销售额 / 哪个用户销售额最高",
                "tables": ["orders", "customers"],
                "join": "orders.customer_id = customers.id",
                "metric": "SUM(orders.total_amount)",
                "grain": "客户",
            },
            {
                "question": "按商品或品类统计销售额",
                "tables": ["order_items", "products"],
                "join": "order_items.product_id = products.id",
                "metric": "SUM(order_items.line_amount)",
                "grain": "商品 / 品类",
            },
            {
                "question": "按时间看订单量或销售额趋势",
                "tables": ["orders"],
                "join": "不需要",
                "metric": "COUNT(*) / SUM(orders.total_amount)",
                "grain": "天 / 月",
            },
        ],
        "time_guidance": [
            "“这个月”默认指当前自然月，从本月第一天 00:00:00 到下月第一天 00:00:00 之前。",
            "时间过滤优先使用 orders.order_date。",
        ],
    }


def render_schema_context(metadata: dict) -> str:
    lines = [f"Database: {metadata['database']}", "Tables:"]
    for table in metadata["tables"]:
        column_parts = []
        for column in table["columns"]:
            suffix = []
            if column["column_key"] == "PRI":
                suffix.append("PK")
            if not column["nullable"]:
                suffix.append("NOT NULL")
            label = f"{column['name']} {column['data_type']}"
            if suffix:
                label += f" ({', '.join(suffix)})"
            column_parts.append(label)
        description = metadata.get("semantic_guidance", {}).get("table_descriptions", {}).get(table["name"])
        if description:
            lines.append(f"- {table['name']}: " + ", ".join(column_parts))
            lines.append(f"  meaning: {description}")
        else:
            lines.append(f"- {table['name']}: " + ", ".join(column_parts))
    if metadata["relationships"]:
        lines.append("Relationships:")
        for relation in metadata["relationships"]:
            lines.append(
                f"- {relation['table']}.{relation['column']} -> "
                f"{relation['referenced_table']}.{relation['referenced_column']}"
            )
    semantic_guidance = metadata.get("semantic_guidance") or {}
    business_terms = semantic_guidance.get("business_terms") or {}
    if business_terms:
        lines.append("Business term mapping:")
        for term, mappings in business_terms.items():
            lines.append(f"- {term}: {', '.join(mappings)}")
    recipes = semantic_guidance.get("analysis_recipes") or []
    if recipes:
        lines.append("Common analysis recipes:")
        for recipe in recipes:
            lines.append(
                "- "
                f"{recipe['question']} -> tables: {', '.join(recipe['tables'])}; "
                f"join: {recipe['join']}; metric: {recipe['metric']}; grain: {recipe['grain']}"
            )
    time_guidance = semantic_guidance.get("time_guidance") or []
    if time_guidance:
        lines.append("Time guidance:")
        for item in time_guidance:
            lines.append(f"- {item}")
    return "\n".join(lines)


def normalize_readonly_sql(sql: str) -> str:
    candidate = sql.strip()
    if candidate.endswith(";"):
        candidate = candidate[:-1].strip()
    if not candidate:
        raise ValueError("SQL is empty")
    if ";" in candidate:
        raise ValueError("Only a single SQL statement is allowed")
    candidate_no_comments = COMMENT_PATTERN.sub("", candidate).strip()
    if not candidate_no_comments.lower().startswith(("select", "with")):
        raise ValueError("Only read-only SELECT/WITH queries are allowed")
    if FORBIDDEN_SQL_PATTERN.search(candidate_no_comments):
        raise ValueError("Dangerous SQL keyword detected")
    return candidate


def execute_readonly_query(sql: str, *, max_rows: int | None = None) -> QueryResult:
    settings = get_settings()
    normalized = normalize_readonly_sql(sql)
    row_limit = max_rows or settings.agent_sql_max_rows
    conn = _connect(database=settings.agent_data_mysql_database)
    try:
        with conn.cursor() as cursor:
            cursor.execute(normalized)
            columns = [item[0] for item in cursor.description or []]
            fetched = list(cursor.fetchmany(row_limit + 1))
    finally:
        conn.close()

    truncated = len(fetched) > row_limit
    rows = [[_serialize_cell(value) for value in row] for row in fetched[:row_limit]]
    return QueryResult(columns=columns, rows=rows, truncated=truncated)
