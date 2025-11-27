import os
import pandas as pd

def load_data_by_category(category: str):
    """
    Loads all static data (rooms, student mapping, QP mappings, templates, PDFs)
    from the /data/ folder based on UG/PG selection.
    """
    base_dir = os.path.join(os.getcwd(), "data")
    result = {
        "room_df": None,
        "mapping_df": None,
        "template_path": None,
        "student_map_df": None,
        "uploaded_qps": {}
    }

    # 1️⃣ Load Room DB
    try:
        room_path = os.path.join(base_dir, "rooms", "Room_DB.xlsx")
        if os.path.exists(room_path):
            result["room_df"] = pd.read_excel(room_path)
    except Exception as e:
        print(f"[Warning] Room DB load failed: {e}")

    # 2️⃣ Load Student Mapping (All classes)
    try:
        student_dir = os.path.join(base_dir, "students")
        mapping_frames = []
        for f in os.listdir(student_dir):
            if f.lower().endswith((".xlsx", ".csv")):
                path = os.path.join(student_dir, f)
                df = pd.read_excel(path) if f.endswith(".xlsx") else pd.read_csv(path)
                df["Source File"] = f  # to identify which batch/class
                mapping_frames.append(df)
        if mapping_frames:
            result["student_map_df"] = pd.concat(mapping_frames, ignore_index=True)
    except Exception as e:
        print(f"[Warning] Student mapping load failed: {e}")

    # 3️⃣ Load QP Mapping (UG/PG)
    try:
        map_dir = os.path.join(base_dir, "mapping")
        if category.upper() == "PG":
            map_file = "qp_code_pg.xlsx"
        else:
             map_file = "UG Course Code.xlsx"     # <-- your actual UG mapping filename

        map_path = os.path.join(map_dir, map_file)
        if os.path.exists(map_path):
            result["mapping_df"] = pd.read_excel(map_path)
            result["mapping_df"]['QP Code'] = result["mapping_df"]['QP Code'].astype(str).str.upper().str.strip()
    except Exception as e:
        print(f"[Warning] QP mapping load failed: {e}")

    # 4️⃣ Load Templates
    try:
        template_path = os.path.join(base_dir, "templates", "remarks_sheet.xlsx")
        if os.path.exists(template_path):
            result["template_path"] = template_path
    except Exception as e:
        print(f"[Warning] Template load failed: {e}")

        # 5️⃣ Load Static QP PDFs (UG / PG auto support)
    try:
        pdf_base = os.path.join(base_dir, "qp_pdfs")

        # if category is UG or PG → load only that
        if category.upper() in ["UG", "PG"]:
            pdf_paths = [os.path.join(pdf_base, category.upper())]
        else:
            # fallback → load both UG + PG
            pdf_paths = [
                os.path.join(pdf_base, "UG"),
                os.path.join(pdf_base, "PG")
            ]

        for path in pdf_paths:
            if os.path.exists(path):
                for f in os.listdir(path):
                    if f.lower().endswith(".pdf"):
                        code = f.rsplit(".pdf", 1)[0].upper().strip()
                        with open(os.path.join(path, f), "rb") as fp:
                            result["uploaded_qps"][code] = fp.read()

        print(f"📥 Loaded QPs: {len(result['uploaded_qps'])} files")

    except Exception as e:
        print(f"[Warning] QP PDF load failed: {e}")


    return result
