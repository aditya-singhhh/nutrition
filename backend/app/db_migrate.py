"""Tiny additive migration: add new nullable columns to tables that already exist (create_all never alters tables).

Stop-gap until Alembic is introduced. Only ever ADDs nullable columns, so it cannot lose data.
"""
from __future__ import annotations

import logging

from sqlalchemy import Engine, inspect, text

logger = logging.getLogger(__name__)

# (table, column, SQL type)
ADDED_COLUMNS = [
    ("user_profiles", "display_name", "VARCHAR(60)"),
    ("user_profiles", "target_weight_kg", "FLOAT"),
    ("user_profiles", "life_stage", "VARCHAR(20)"),
    ("user_profiles", "training_opt_in", "BOOLEAN"),
]


def ensure_columns(engine: Engine) -> list[str]:
    insp = inspect(engine)
    added = []
    for table, col, ddl in ADDED_COLUMNS:
        if not insp.has_table(table):
            continue
        if col in {c["name"] for c in insp.get_columns(table)}:
            continue
        with engine.begin() as conn:
            conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {col} {ddl}'))
        added.append(f"{table}.{col}")
    if added:
        logger.info("added columns: %s", ", ".join(added))
    return added
