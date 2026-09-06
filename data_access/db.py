"""Accès Oracle et métadonnées.

Reconstruction progressive à partir des captures du projet MOA Helper.
"""

import time
from typing import Optional

import pandas as pd
import streamlit as st


@st.cache_data(show_spinner=False)
def get_tables_list(env, table_name_like: Optional[str] = None, schema_name=None) -> pd.DataFrame:
    conn = get_connection(env)
    if schema_name:
        query = """
        SELECT owner, table_name
        FROM all_tables
        WHERE owner = :owner
        """
        params = {"owner": schema_name.upper()}
    else:
        query = """
        SELECT owner, table_name
        FROM all_tables
        WHERE 1 = 1
        """
        params = {}
    if table_name_like:
        query += "\nAND UPPER(table_name) LIKE :table_name_like"
        params["table_name_like"] = f"%{table_name_like.upper()}%"
    query += "\nORDER BY owner, table_name"
    return read_sql_df(conn, query, params)


@st.cache_data(show_spinner=False)
def get_table_columns(env, table_name: str, owner: str) -> pd.DataFrame:
    table_columns = get_metadas(table_name, "columns")
    logger.debug(f"get_table_columns-table: {len(table_columns)} columns for table {table_name} in cache")
    if len(table_columns) > 0:
        return table_columns
    conn = get_connection(env)
    query = """
    SELECT owner, table_name, column_id, column_name, data_type,
           data_length, data_precision, data_scale, nullable, data_default
    FROM all_tab_columns
    WHERE owner = :owner
      AND table_name = :table_name
    ORDER BY column_id
    """
    return read_sql_df(conn, query, {"owner": owner.upper(), "table_name": table_name.upper()})


@st.cache_data(show_spinner=False)
def get_primary_key(env, table_name: str, owner: str) -> pd.DataFrame:
    primary_key = get_metadas(table_name, "primary_key")
    logger.debug(f"get_primary_key-table: {len(primary_key)} primary keys for table {table_name} in cache")
    if primary_key is not None:
        return primary_key
    conn = get_connection(env)
    query = """
    SELECT acc.owner, acc.table_name, acc.constraint_name, acc.column_name, acc.position
    FROM all_constraints ac
    JOIN all_cons_columns acc
      ON ac.owner = acc.owner
     AND ac.constraint_name = acc.constraint_name
    WHERE ac.constraint_type = 'P'
      AND ac.owner = :owner
      AND ac.table_name = :table_name
    ORDER BY acc.position
    """
    return read_sql_df(conn, query, {"owner": owner.upper(), "table_name": table_name.upper()})


@st.cache_data(show_spinner=False)
def get_foreign_keys(env, table_name: str, owner: str) -> pd.DataFrame:
    foreign_keys = get_metadas(table_name, "foreign_keys")
    if foreign_keys is not None:
        return foreign_keys
    conn = get_connection(env)
    query = """
    SELECT c.owner, c.table_name, c.constraint_name, col.column_name,
           c_pk.owner AS referenced_owner,
           c_pk.table_name AS referenced_table_name,
           col_pk.column_name AS referenced_column_name
    FROM all_constraints c
    JOIN all_cons_columns col
      ON c.owner = col.owner
     AND c.constraint_name = col.constraint_name
    JOIN all_constraints c_pk
      ON c.r_owner = c_pk.owner
     AND c.r_constraint_name = c_pk.constraint_name
    JOIN all_cons_columns col_pk
      ON c_pk.owner = col_pk.owner
     AND c_pk.constraint_name = col_pk.constraint_name
     AND col.position = col_pk.position
    WHERE c.constraint_type = 'R'
      AND c.owner = :owner
      AND c.table_name = :table_name
    ORDER BY c.constraint_name, col.position
    """
    return read_sql_df(conn, query, {"owner": owner.upper(), "table_name": table_name.upper()})


@st.cache_data(show_spinner=False)
def get_indexes(env, table_name: str, owner: str) -> pd.DataFrame:
    indexes = get_metadas(table_name, "indexes")
    if len(indexes) > 0:
        return indexes
    conn = get_connection(env)
    query = """
    SELECT ai.table_owner, ai.table_name, ai.index_name, ai.uniqueness,
           aic.column_name, aic.column_position
    FROM all_indexes ai
    JOIN all_ind_columns aic
      ON ai.owner = aic.index_owner
     AND ai.index_name = aic.index_name
    WHERE ai.table_owner = :owner
      AND ai.table_name = :table_name
    ORDER BY ai.index_name, aic.column_position
    """
    return read_sql_df(conn, query, {"owner": owner.upper(), "table_name": table_name.upper()})


@st.cache_data(show_spinner=False)
def get_table_comment(env, table_name: str, owner: str) -> pd.DataFrame:
    table_comment = get_metadas(table_name, "table_comment")
    if len(table_comment) > 0:
        return table_comment
    conn = get_connection(env)
    query = """
    SELECT owner, table_name, comments
    FROM all_tab_comments
    WHERE owner = :owner
      AND table_name = :table_name
    """
    return read_sql_df(conn, query, {"owner": owner.upper(), "table_name": table_name.upper()})


@st.cache_data(show_spinner=False)
def get_column_comments(env, table_name: str, owner: str) -> pd.DataFrame:
    column_comments = get_metadas(table_name, "column_comments")
    if len(column_comments) > 0:
        return column_comments
    conn = get_connection(env)
    query = """
    SELECT owner, table_name, column_name, comments
    FROM all_col_comments
    WHERE owner = :owner
      AND table_name = :table_name
    ORDER BY column_name
    """
    return read_sql_df(conn, query, {"owner": owner.upper(), "table_name": table_name.upper()})


_last_db_check = 0
__cached_status_db = False
TTL = 60 * 10


def base_disponible(env):
    global _last_db_check, __cached_status_db
    now = time.time()
    if now - _last_db_check < TTL:
        return __cached_status_db
    try:
        conn = get_connection(env)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM DUAL")
        cur.fetchone()
        cur.close()
        conn.close()
        __cached_status_db = True
    except Exception:
        logger.info("base indisponible mode offline")
        __cached_status_db = False
    _last_db_check = now
    return __cached_status_db
