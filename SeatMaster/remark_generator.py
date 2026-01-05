import pandas as pd
import openpyxl
from openpyxl.styles import Alignment, Font
import os
import glob


def build_student_mapping(students_dir="data/students"):
    """
    Scans Excel files in students_dir to create a {Class_No: Batch_Name} map.
    Looks for 'Batch Name' and 'Class No' inside the files.
    """
    mapping = {}

    if not os.path.exists(students_dir):
        print(f"Warning: Directory '{students_dir}' not found.")
        return mapping

    files = glob.glob(os.path.join(students_dir, "*.xlsx"))

    for file_path in files:
        try:
            # Scan first rows to detect header
            df_scan = pd.read_excel(file_path, header=None, nrows=15)

            header_row_idx = None
            for idx, row in df_scan.iterrows():
                row_str = [str(v).strip() for v in row.values]
                if "Class No" in row_str and "Batch Name" in row_str:
                    header_row_idx = idx
                    break

            if header_row_idx is not None:
                df = pd.read_excel(file_path, header=header_row_idx)
                df.columns = [str(c).strip() for c in df.columns]

                if "Class No" in df.columns and "Batch Name" in df.columns:
                    df = df.dropna(subset=["Class No"])
                    for _, r in df.iterrows():
                        key = str(r["Class No"]).strip()
                        val = str(r["Batch Name"]).strip()
                        mapping[key] = val

        except Exception as e:
            print(f"Error processing {os.path.basename(file_path)}: {e}")

    return mapping


def generate_remark_sheets(
    seating_df,
    exam_title,
    exam_date,
    exam_session,      # FN / AN
    template_path,
    output_path,
    students_dir="data/students"
):
    """
    Generates remark sheets with:
    - FN / AN in cell C3
    - Clean room name
    - Integer Class No (no .0)
    """

    # -------------------------
    # Build student → batch mapping
    # -------------------------
    class_map = build_student_mapping(students_dir)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    wb = openpyxl.load_workbook(template_path)
    master_sheet = wb.active
    master_sheet.title = "Master_Template"

    grouped = seating_df.groupby("Room")

    for room_name, room_data in grouped:
        ws = wb.copy_worksheet(master_sheet)
        ws.title = str(room_name)[:30]

        # -------------------------
        # HEADER (CRITICAL FIX)
        # -------------------------
        ws["B3"] = exam_date
        ws["C3"] = exam_session        # ✅ FN / AN goes here
        ws["F3"] = str(room_name)      # ✅ Room only

        if ws["A2"].value and "Examination" in str(ws["A2"].value):
            ws["A2"] = exam_title
        else:
            ws["A1"] = exam_title

        # -------------------------
        # ROW EXPANSION LOGIC
        # -------------------------
        START_ROW = 7

        footer_header_row = 25
        for r in range(START_ROW, ws.max_row + 1):
            if str(ws.cell(row=r, column=1).value).strip() == "Class":
                footer_header_row = r
                break

        room_data["Bench"] = (
            pd.to_numeric(room_data["Bench"], errors="coerce")
            .fillna(0)
            .astype(int)
        )

        min_bench = room_data["Bench"].min()
        max_bench = room_data["Bench"].max()

        needed_rows = (max_bench - min_bench) + 1
        available_rows = footer_header_row - START_ROW

        if needed_rows > available_rows:
            ws.insert_rows(footer_header_row, needed_rows - available_rows + 2)
            footer_header_row += needed_rows - available_rows + 2

        # -------------------------
        # FILL SEATING DATA (FIXED CLASS NO)
        # -------------------------
        for bench in range(min_bench, max_bench + 1):
            row_idx = START_ROW + (bench - min_bench)

            seat_cell = ws.cell(row=row_idx, column=1, value=bench)
            seat_cell.font = Font(bold=True)
            seat_cell.alignment = Alignment(horizontal="center")

            bench_students = room_data[room_data["Bench"] == bench]

            for _, stu in bench_students.iterrows():
                seat = stu["Seat"]
                raw_class = stu["Class No"]

                if pd.isna(raw_class) or raw_class == "-":
                    continue

                # ✅ REMOVE .0 PROPERLY
                if isinstance(raw_class, float):
                    class_no = str(int(raw_class))
                else:
                    class_no = str(raw_class).strip()

                col = {"Left": 2, "Center": 4, "Right": 6}.get(seat)
                if col:
                    c = ws.cell(row=row_idx, column=col, value=class_no)
                    c.alignment = Alignment(horizontal="center")

        # -------------------------
        # FOOTER HEADER STYLE
        # -------------------------
        for col in range(1, 5):
            ws.cell(row=footer_header_row, column=col).font = Font(
                bold=True, color="FFFFFF"
            )

        # -------------------------
        # SUMMARY SECTION (FIXED)
        # -------------------------
        valid_students = room_data[room_data["Class No"] != "-"].copy()

        valid_students["Class No"] = valid_students["Class No"].apply(
            lambda x: str(int(x)) if isinstance(x, float) else str(x)
        )

        valid_students["Real_Class_Name"] = (
            valid_students["Class No"]
            .map(class_map)
            .fillna("Unknown Class")
        )

        # Total Students
        total_count = len(valid_students)
        for r in range(footer_header_row, footer_header_row + 15):
            for c in range(1, 10):
                if ws.cell(row=r, column=c).value == "Total Students":
                    ws.cell(row=r, column=c + 1, value=total_count)
                    break

        summary = (
            valid_students
            .groupby("Real_Class_Name")["Class No"]
            .agg(["count", "min", "max"])
            .reset_index()
        )

        write_row = footer_header_row + 1
        for _, s in summary.iterrows():
            ws.cell(write_row, 1, s["Real_Class_Name"])
            ws.cell(write_row, 2, s["min"])
            ws.cell(write_row, 3, s["max"])
            ws.cell(write_row, 4, s["count"])
            write_row += 1

    del wb["Master_Template"]
    wb.save(output_path)
    return output_path
