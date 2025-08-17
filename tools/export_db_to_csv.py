import pandas as pd
import sqlite3
from os.path import join

db_dir = '/Users/nuriseok/Downloads/project/data/db'

conn = sqlite3.connect(join(db_dir, 'collections.db'), isolation_level=None, detect_types=sqlite3.PARSE_COLNAMES)
db_df = pd.read_sql_query("SELECT * FROM collections", conn)
db_df.to_csv(join(db_dir,'export.csv'), index=False)
print('Completed!')