import os
from pathlib import Path
import sys
import pandas as pd

import pyarrow as pa
import pickle
import gzip
import pyarrow.parquet as pq

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))


EXCEL_FILE=os.path.join(ROOT_DIR,"..","tests","Lien_table_options_v0.xlsx")
OWNER="ORAGPDC01"


from data_access.db import get_column_comments, get_foreign_keys, get_indexes, get_primary_key, \
get_table_columns, get_table_comment



selected_owner=OWNER
env="VEILLE"
df =pd.read_excel(EXCEL_FILE)
df=df.fillna("")


liste_table= df["LISTE DES TABLES"].tolist()

print(type(liste_table))

def load_metadata(env, selected_owner, selected_table):

        columns_df = get_table_columns(env,
            owner=selected_owner,
            table_name=selected_table,
        )

        pk_df = get_primary_key(env,
            owner=selected_owner,
            table_name=selected_table,
        )

        fk_df = get_foreign_keys(env,
            owner=selected_owner,
            table_name=selected_table,
        )

        indexes_df = get_indexes(env,
            owner=selected_owner,
            table_name=selected_table,
        )

        table_comment_df = get_table_comment(env,
            owner=selected_owner,
            table_name=selected_table,
        )

        column_comments_df = get_column_comments(env,
            owner=selected_owner,
            table_name=selected_table,
        )

        return columns_df, pk_df, fk_df, indexes_df, table_comment_df, column_comments_df


# #          templates = build_templates(selected_owner, selected_table, columns_df, pk_df, indexes_df)

dict_metadata = {}
for table in liste_table:
    table=table.strip().upper()
    print(f"Loading metadata for table: {table}")
    columns_df, pk_df, fk_df, indexes_df, table_comment_df, column_comments_df = load_metadata(env, selected_owner, table)
    print(f"Metadata loaded for table: {table}")
    dict_metadata[table] = {
        "columns": columns_df,
        "primary_key": pk_df,
        "foreign_keys": fk_df,
        "indexes": indexes_df,
        "table_comment": table_comment_df,
        "column_comments": column_comments_df
    }


with gzip.open('metadata_cache.pkl.gz', 'wb') as f:
    pickle.dump(dict_metadata, f)

# pq.write_table(table,'ma_table.parquet')

# table = pq.read_table('ma_table.parquet')
# df = table.to_pandas()
# print("Lecture parquet")
# print(df.head())


# # Write partitioned Parquet files
# pq.write_to_dataset(table, root_path='dataset/', partition_cols=['Age'])

# # Read a partitioned dataset
# table = pq.ParquetDataset('dataset/').read()
# df = table.to_pandas()

# print(df)
