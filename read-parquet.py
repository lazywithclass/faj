import sys
import pandas as pd

if len(sys.argv) != 2:
  print(f"Usage: {sys.argv[0]} <path_to_parquet>")
  sys.exit(1)

columns = ["id"]
df = pd.read_parquet(sys.argv[1], columns=columns)
print(df.to_string(index=False))
