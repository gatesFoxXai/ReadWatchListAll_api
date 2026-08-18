import os
import pandas as pd
from datetime import datetime, timedelta


def add_columns_to_csv(csv_path: str):
    """Add '日期時間' and 'stock_id' columns to a CSV file if they are missing.
    The '日期時間' column is filled with sequential timestamps starting from now,
    incremented by one second per row. The 'stock_id' column is derived from the
    filename (without extension)."""
    # Determine stock_id from filename
    stock_id = os.path.splitext(os.path.basename(csv_path))[0]
    # Read existing CSV
    try:
        df = pd.read_csv(csv_path, encoding="utf-8")
    except Exception as e:
        print(f"Failed to read {csv_path}: {e}")
        return
    # Add missing columns
    if "日期時間" not in df.columns:
        start = datetime.now()
        df.insert(0, "日期時間", [(start + timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S") for i in range(len(df))])
    if "stock_id" not in df.columns:
        df.insert(1 if "日期時間" in df.columns else 0, "stock_id", stock_id)
    # Save back, preserving order
    df.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"Updated {csv_path}")


if __name__ == "__main__":
    # Process all CSV files in the workspace root (excluding .bak files)
    cwd = os.path.abspath(os.path.dirname(__file__))
    for fname in os.listdir(cwd):
        if fname.lower().endswith(".csv") and not fname.lower().endswith(".bak"):
            path = os.path.join(cwd, fname)
            add_columns_to_csv(path)
