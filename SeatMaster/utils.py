import io
import pandas as pd

def df_to_bytes(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sheet1")
    return output.getvalue()

def normalize_subject(s):
    """Return an uppercase, trimmed string for consistent matching."""
    if pd.isna(s):
        return ""
    return str(s).strip().upper()
