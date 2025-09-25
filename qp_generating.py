# seating_arrangement_app.py
import streamlit as st
import pandas as pd
import io
from PyPDF2 import PdfReader, PdfWriter

st.set_page_config(page_title="SeatMaster", layout="wide")
st.title("🎓 SeatMaster – Seating Arrangement & QP Generator")

# --- Upload Files ---
room_file = st.file_uploader("Upload Room Details (Excel with Room, Start, End)", type=["xlsx", "csv"])
student_file = st.file_uploader("Upload Student List (Excel/CSV with Class No, Student Name, DAY1...)", type=["xlsx", "csv"])
mapping_file = st.file_uploader("Upload QP Mapping (Excel/CSV with QP Code and Subject Name)", type=["xlsx", "csv"])
qp_files = st.file_uploader("Upload QP PDFs (filename = QP Code)", type=["pdf"], accept_multiple_files=True)

# --- Helpers ---
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

# --- Initialize session_state (persist outputs) ---
if "generated" not in st.session_state:
    st.session_state["generated"] = False
for key in ["final_df_bytes","detailed_seating_bytes","room_summary_bytes",
            "qp_summary_bytes","qp_count_bytes","hall_qp_summary_bytes","room_pdfs"]:
    if key not in st.session_state:
        st.session_state[key] = None if "bytes" in key or key=="room_pdfs" else False

# --- Load files ---
if room_file and student_file:
    room_df = pd.read_csv(room_file) if room_file.name.endswith(".csv") else pd.read_excel(room_file)
    students = pd.read_csv(student_file) if student_file.name.endswith(".csv") else pd.read_excel(student_file)

    st.subheader(f"📊 Total Students: {len(students)}")

    rooms = room_df["Room"].unique().tolist()
    selected_rooms = st.multiselect("Select Rooms (order is preserved)", rooms)

    subject_columns = [c for c in students.columns if c.upper().startswith("DAY")]
    selected_day = st.selectbox("Select Day to Conduct Subjects", subject_columns) if subject_columns else None

    if selected_rooms:
        total_capacity = sum(
            (int(room_df[room_df["Room"] == room].iloc[0]["End"]) -
             int(room_df[room_df["Room"] == room].iloc[0]["Start"]) + 1) * 3
            for room in selected_rooms
        )
        st.info(f"🪑 Total Capacity of Selected Rooms: {total_capacity} seats")

    # Prepare normalized mapping if provided (normalize Subject Name)
    mapping_df = None
    if mapping_file:
        mapping_df = pd.read_csv(mapping_file) if mapping_file.name.endswith(".csv") else pd.read_excel(mapping_file)
        # Normalize both columns for robust matching
        if "QP Code" in mapping_df.columns:
            mapping_df['QP Code'] = mapping_df['QP Code'].astype(str).str.upper().str.strip()
        if "Subject Name" in mapping_df.columns:
            mapping_df['Subject Name'] = mapping_df['Subject Name'].apply(normalize_subject)

    # Build uploaded_qps dict keyed by QP code (upper, no extension)
    uploaded_qps = {}
    if qp_files:
        uploaded_qps = {qp.name.rsplit(".pdf",1)[0].upper().strip(): qp.getvalue() for qp in qp_files}

    if st.button("Generate Seating Plan"):
        # validation
        if not selected_rooms:
            st.error("Please select at least one room.")
        elif "Class No" not in students.columns or "Student Name" not in students.columns:
            st.error("Student list must contain 'Class No' and 'Student Name'.")
        else:
            ordered_rooms = selected_rooms
            seats = ["Left", "Right", "Center"]
            seating_data = []

            # Prepare benches per room
            room_benches = {}
            for room in ordered_rooms:
                row = room_df[room_df["Room"] == room].iloc[0]
                start, end = int(row["Start"]), int(row["End"])
                room_benches[room] = list(range(start, end + 1))

            # Interleaved seating assignment: Left,Right,Center across rooms and benches
            for seat in seats:
                for room in ordered_rooms:
                    for bench in room_benches[room]:
                        seating_data.append({"Room": room, "Bench": bench, "Seat": seat})

            # Assign students into seating slots
            student_list = students.values.tolist()
            student_columns = students.columns.tolist()
            for i, slot in enumerate(seating_data):
                if i < len(student_list):
                    row = student_list[i]
                    info = dict(zip(student_columns, row))
                    slot["Class No"] = info["Class No"]
                    slot["Student Name"] = info["Student Name"]
                    if selected_day and pd.notna(info[selected_day]):
                        # Normalize each subject in the comma-separated list
                        raw = str(info[selected_day])
                        subjects = [normalize_subject(s) for s in raw.split(",") if str(s).strip() != ""]
                        slot["Subjects"] = ", ".join(subjects) if subjects else "-"
                    else:
                        slot["Subjects"] = "-"
                else:
                    slot["Class No"] = "-"
                    slot["Student Name"] = "-"
                    slot["Subjects"] = "-"

            seating_df = pd.DataFrame(seating_data)

            # Pivot view for display
            final_df = seating_df.pivot_table(index=["Room","Bench"], columns="Seat", values="Class No", aggfunc="first").reset_index()
            # Ensure columns order Left, Center, Right if present
            display_cols = ["Room","Bench"]
            for c in ["Left","Center","Right"]:
                if c in final_df.columns:
                    display_cols.append(c)
            final_df = final_df[display_cols]
            final_df["Room"] = pd.Categorical(final_df["Room"], categories=ordered_rooms, ordered=True)
            final_df = final_df.sort_values(["Room","Bench"]).reset_index(drop=True)

            # Room summary & building qp_summary (normalized subjects)
            summary_records = []
            qp_summary_records = []
            all_subjects = []
            for room in ordered_rooms:
                rs = seating_df[seating_df["Room"] == room]
                valid_subs = rs[rs["Subjects"] != "-"]["Subjects"]
                room_subjects = []
                for subj_list in valid_subs:
                    for s in str(subj_list).split(","):
                        s_norm = normalize_subject(s)
                        if s_norm:
                            room_subjects.append(s_norm)
                            qp_summary_records.append({"Room": room, "Bench": rs.loc[valid_subs.index[valid_subs==subj_list][0],"Bench"] if False else None, "Seat": None, "Subject": s_norm})
                            # we don't need Bench/Seat mapping inside this loop for counts; bench/seat locations handled separately below
                            # (we will build bench-seat locations when creating qp_count_df)
                all_subjects.extend(room_subjects)
                summary_records.append({
                    "Room": room,
                    "Total Students": len(rs[rs["Class No"] != "-"]),
                    "Subjects in Room": ", ".join(sorted(set(room_subjects)))
                })

            # Instead of the above hacky qp_summary_records (we need bench/seat), rebuild properly:
            qp_summary_records = []
            for _, row in seating_df[seating_df["Subjects"] != "-"].iterrows():
                bench = row["Bench"]
                seat = row["Seat"]
                room = row["Room"]
                for s in str(row["Subjects"]).split(","):
                    s_norm = normalize_subject(s)
                    if s_norm:
                        qp_summary_records.append({"Room": room, "Bench": bench, "Seat": seat, "Subject": s_norm})
                        all_subjects.append(s_norm)

            summary_df = pd.DataFrame(summary_records)

            # QP detailed & counts
            qp_summary_df = pd.DataFrame(qp_summary_records)
            if not qp_summary_df.empty:
                qp_count_df = (
                    qp_summary_df.groupby(["Room","Subject"])
                    .agg(
                        QP_Needed=("Subject","count"),
                        Bench_Seat_Locations=("Bench", lambda x: ", ".join([f"{b}-{s}" for b,s in zip(x, qp_summary_df.loc[x.index,"Seat"])]))
                    )
                    .reset_index()
                    .sort_values(["Room","Subject"])
                )
            else:
                qp_count_df = pd.DataFrame(columns=["Room","Subject","QP_Needed","Bench_Seat_Locations"])

            # Hall-wise QP summary (simple room-subject-count)
            if not qp_summary_df.empty:
                hall_qp_summary_df = qp_summary_df.groupby(["Room","Subject"]).size().reset_index(name="Total QPs Needed").sort_values(["Room","Subject"])
            else:
                hall_qp_summary_df = pd.DataFrame(columns=["Room","Subject","Total QPs Needed"])

            # --- QP PDF generation: generate per (room,subject) using exact counts ---
            room_pdfs = {}
            if mapping_df is not None and qp_files:
                # Ensure mapping_df normalized 'Subject Name' (done earlier)
                for room in ordered_rooms:
                    room_rows = qp_summary_df[qp_summary_df["Room"] == room]
                    if room_rows.empty:
                        continue

                    # Count how many students in this room need each subject
                    subject_counts = room_rows["Subject"].value_counts().to_dict()

                    writer = PdfWriter()
                    for subj, count in subject_counts.items():
                        # lookup QP code in mapping (mapping_df 'Subject Name' is normalized)
                        if mapping_df is None or "Subject Name" not in mapping_df.columns:
                            continue
                        matched = mapping_df[mapping_df["Subject Name"] == subj]["QP Code"].values
                        if matched.size == 0:
                            # No mapping found -> skip (you can also log warn)
                            st.warning(f"No QP code found for subject '{subj}' (room {room})")
                            continue
                        qp_code = matched[0]
                        if qp_code not in uploaded_qps:
                            st.warning(f"No uploaded PDF found for QP code '{qp_code}' (subject {subj}, room {room})")
                            continue
                        # append the PDF 'count' times (one copy per student)
                        reader = PdfReader(io.BytesIO(uploaded_qps[qp_code]))
                        for _ in range(int(count)):
                            for p in reader.pages:
                                writer.add_page(p)
                    # if any pages were added, write to bytes
                    if len(writer.pages) > 0:
                        out = io.BytesIO()
                        writer.write(out)
                        out.seek(0)
                        room_pdfs[room] = out.getvalue()

            # Persist outputs in session_state (bytes)
            st.session_state["final_df_bytes"] = df_to_bytes(final_df)
            st.session_state["detailed_seating_bytes"] = df_to_bytes(seating_df)
            st.session_state["room_summary_bytes"] = df_to_bytes(summary_df)
            st.session_state["qp_summary_bytes"] = df_to_bytes(qp_summary_df)
            st.session_state["qp_count_bytes"] = df_to_bytes(qp_count_df)
            st.session_state["hall_qp_summary_bytes"] = df_to_bytes(hall_qp_summary_df)
            st.session_state["room_pdfs"] = room_pdfs
            st.session_state["generated"] = True

# --- Display stored tables (persisted) ---
if st.session_state.get("generated"):
    st.subheader("🪑 Seating Arrangement")
    try:
        st.dataframe(pd.read_excel(io.BytesIO(st.session_state["final_df_bytes"])))
    except Exception:
        st.write("Seating plan not available.")

    st.subheader("📋 Room Summary (Subjects)")
    try:
        st.dataframe(pd.read_excel(io.BytesIO(st.session_state["room_summary_bytes"])))
    except Exception:
        st.write("Room summary not available.")

    st.subheader("📊 Hall-wise QP Summary")
    try:
        st.dataframe(pd.read_excel(io.BytesIO(st.session_state["hall_qp_summary_bytes"])))
    except Exception:
        st.write("Hall-wise QP summary not available.")

# --- Download buttons (unique keys) ---
if st.session_state.get("generated"):
    st.markdown("---")
    st.subheader("📥 Downloads")

    if st.session_state["final_df_bytes"]:
        st.download_button("📥 Download Seating Plan", st.session_state["final_df_bytes"],
                           "SeatingPlan.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="dl_seating_plan")

    if st.session_state["detailed_seating_bytes"]:
        st.download_button("📥 Download Detailed Seating", st.session_state["detailed_seating_bytes"],
                           "DetailedSeating.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="dl_detailed_seating")

    if st.session_state["room_summary_bytes"]:
        st.download_button("📥 Download Room Summary", st.session_state["room_summary_bytes"],
                           "RoomSummary.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="dl_room_summary")

    if st.session_state["qp_summary_bytes"]:
        st.download_button("📥 Download QP Summary (Detailed)", st.session_state["qp_summary_bytes"],
                           "QP_Detailed.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="dl_qp_detailed")

    if st.session_state["qp_count_bytes"]:
        st.download_button("📥 Download QP Counts per Room", st.session_state["qp_count_bytes"],
                           "QP_Count.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="dl_qp_counts")

    if st.session_state["hall_qp_summary_bytes"]:
        st.download_button("📥 Download Hall-wise QP Summary", st.session_state["hall_qp_summary_bytes"],
                           "Hall_QP_Summary.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           key="dl_hall_qp_summary")

    # Room PDFs
    if st.session_state["room_pdfs"]:
        st.subheader("📄 Room-wise QP PDFs")
        for i, (room, pdf_bytes) in enumerate(st.session_state["room_pdfs"].items()):
            st.download_button(f"📥 Download {room} QPs", pdf_bytes, f"{room}_QPs.pdf", "application/pdf", key=f"dl_room_pdf_{i}")

