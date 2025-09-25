# seating_arrangement_app.py
import streamlit as st
import pandas as pd
import io
import re
from PyPDF2 import PdfReader, PdfWriter
from difflib import get_close_matches

st.set_page_config(page_title="Seating Arrangement Generator", layout="wide")
st.title("🎓 Seating Arrangement Generator")

# --- Upload Room Details ---
room_file = st.file_uploader("Upload Room Details (Excel with Room, Start, End)", type=["xlsx", "csv"])

# --- Upload Student List ---
student_file = st.file_uploader("Upload Student List (Excel/CSV with Class No, Student Name, DAY1...)", type=["xlsx", "csv"])

# --- Upload Question Papers ---
qp_files = st.file_uploader("Upload QP PDFs", type=["pdf"], accept_multiple_files=True)

# --- Initialize session state for persistence across reruns ---
if "generated" not in st.session_state:
    st.session_state["generated"] = False
if "final_df_bytes" not in st.session_state:
    st.session_state["final_df_bytes"] = None
if "detailed_seating_bytes" not in st.session_state:
    st.session_state["detailed_seating_bytes"] = None
if "room_summary_bytes" not in st.session_state:
    st.session_state["room_summary_bytes"] = None
if "qp_detailed_bytes" not in st.session_state:
    st.session_state["qp_detailed_bytes"] = None
if "qp_count_bytes" not in st.session_state:
    st.session_state["qp_count_bytes"] = None
if "room_pdfs" not in st.session_state:
    st.session_state["room_pdfs"] = {}  # mapping room -> pdf bytes

# --- Helper functions ---
def clean_subject(subject):
    """Fix single-letter splits (e.g., P ART -> PART)"""
    subject = re.sub(r'\b([A-Z])\s+([A-Z]{2,})\b', r'\1\2', subject)
    subject = re.sub(r'\s+', ' ', subject).strip()
    return subject

def normalize_subject(subject):
    """Normalize for consistent matching"""
    if pd.isna(subject):
        return ""
    subject = str(subject).upper()
    subject = re.sub(r'\s+', ' ', subject).strip()
    return subject

def extract_subject_from_pdf(pdf_file):
    """Extract subject from QP PDF"""
    try:
        reader = PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        for line in text.splitlines():
            if "AEC:" in line:
                parts = line.split("-")
                if len(parts) > 1:
                    subj = parts[1].strip()
                    return normalize_subject(clean_subject(subj))
        return "UNKNOWN SUBJECT"
    except Exception as e:
        return f"ERROR: {e}"

def df_to_bytes(df):
    """Convert DataFrame to excel bytes"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sheet1")
    return output.getvalue()

# --- Build subject -> PDF mapping (normalized keys) ---
qp_mapping = {}
if qp_files:
    for qp in qp_files:
        subject_name = extract_subject_from_pdf(qp)
        subject_name = normalize_subject(subject_name)
        qp_mapping[subject_name] = qp.getvalue()

# --- Main logic ---
if room_file is not None and student_file is not None:
    # Load rooms
    if room_file.name.endswith(".csv"):
        room_df = pd.read_csv(room_file)
    else:
        room_df = pd.read_excel(room_file)

    # Load students
    if student_file.name.endswith(".csv"):
        students = pd.read_csv(student_file)
    else:
        students = pd.read_excel(student_file)

    # Reset generated flag when inputs change (optional safety)
    # If you want to force re-generate when inputs change: uncomment below
    # st.session_state["generated"] = False
    # st.session_state["room_pdfs"] = {}

    total_students = len(students)
    st.subheader(f"📊 Total Students: {total_students}")

    st.subheader("🏫 Available Rooms")
    rooms = room_df["Room"].unique().tolist()
    selected_rooms = st.multiselect("Select Rooms (order is preserved)", rooms)

    # --- Select Day for Subject ---
    subject_columns = [c for c in students.columns if c.upper().startswith("DAY")]
    if subject_columns:
        selected_day = st.selectbox("Select Day to Conduct Subjects", subject_columns)
    else:
        selected_day = None

    if selected_rooms:
        total_capacity = 0
        for room in selected_rooms:
            room_info = room_df[room_df["Room"] == room].iloc[0]
            start, end = int(room_info["Start"]), int(room_info["End"])
            benches = end - start + 1
            total_capacity += benches * 3  # 3 seats per bench
        st.info(f"🪑 Total Capacity of Selected Rooms: {total_capacity} seats")

    if st.button("Generate Seating Plan"):
        if not selected_rooms:
            st.error("Please select at least one room.")
        elif "Class No" not in students.columns or "Student Name" not in students.columns:
            st.error("Student list must contain 'Class No' and 'Student Name' columns.")
        else:
            ordered_rooms = selected_rooms
            seating_data = []
            seats = ["Left", "Right", "Center"]

            # Prepare benches
            room_benches = {}
            for room in ordered_rooms:
                room_info = room_df[room_df["Room"] == room].iloc[0]
                start, end = int(room_info["Start"]), int(room_info["End"])
                room_benches[room] = list(range(start, end + 1))

            # Interleaved seat allocation
            for seat in seats:
                for room in ordered_rooms:
                    for bench in room_benches[room]:
                        seating_data.append({"Room": room, "Bench": bench, "Seat": seat})

            # --- Assign students ---
            student_list = students.values.tolist()
            student_columns = students.columns.tolist()
            for i, seat in enumerate(seating_data):
                if i < len(student_list):
                    row = student_list[i]
                    student_info = dict(zip(student_columns, row))
                    seat["Class No"] = student_info["Class No"]
                    seat["Student Name"] = student_info["Student Name"]
                    if selected_day:
                        subjects = str(student_info[selected_day]) if pd.notna(student_info[selected_day]) else "-"
                        seat["Subjects"] = ", ".join([normalize_subject(s) for s in subjects.split(",") if s.strip()]) if subjects != "-" else "-"
                    else:
                        seat["Subjects"] = "-"
                else:
                    seat["Class No"] = "-"
                    seat["Student Name"] = "-"
                    seat["Subjects"] = "-"

            seating_df = pd.DataFrame(seating_data)

            # --- Pivot for display ---
            final_df = seating_df.pivot_table(
                index=["Room", "Bench"], 
                columns="Seat", values="Class No", 
                aggfunc="first"
            ).reset_index()
            seat_order = ["Left", "Center", "Right"]
            final_df = final_df[["Room", "Bench"] + seat_order]
            final_df["Room"] = pd.Categorical(final_df["Room"], categories=ordered_rooms, ordered=True)
            final_df = final_df.sort_values(["Room", "Bench"]).reset_index(drop=True)
            st.subheader("🪑 Seating Arrangement")
            st.dataframe(final_df)

            # --- Room-wise summary ---
            summary_records = []
            all_subjects = []
            for room in ordered_rooms:
                room_students = seating_df[seating_df["Room"] == room]
                valid_subjects = room_students[room_students["Subjects"] != "-"]["Subjects"]
                room_subjects = [normalize_subject(s) for subj in valid_subjects for s in subj.split(",") if s.strip()]
                all_subjects.extend(room_subjects)
                summary_records.append({
                    "Room": room,
                    "Total Students": len(room_students[room_students["Class No"] != "-"]),
                    "Subjects in Room": ", ".join(sorted(set(room_subjects)))
                })
            summary_df = pd.DataFrame(summary_records)
            st.subheader("📋 Room Summary (Subjects)")
            st.dataframe(summary_df)

            # --- QP Totals across all rooms ---
            qp_counts = pd.Series(all_subjects).value_counts().reset_index()
            qp_counts.columns = ["Subject", "Total QPs Needed"]
            st.subheader("📑 Total QPs Needed (All Rooms)")
            st.dataframe(qp_counts)

            # --- Room-wise QP Summary with Bench/Seat ---
            qp_summary_records = []
            for _, row in seating_df[seating_df["Subjects"] != "-"].iterrows():
                subjects = [normalize_subject(s) for s in row["Subjects"].split(",") if s.strip()]
                for subj in subjects:
                    qp_summary_records.append({
                        "Room": row["Room"],
                        "Bench": row["Bench"],
                        "Seat": row["Seat"],
                        "Subject": subj
                    })
            qp_summary_df = pd.DataFrame(qp_summary_records)
            qp_count_df = (
                qp_summary_df.groupby(["Room", "Subject"])
                .agg(
                    QP_Needed=("Subject", "count"),
                    Bench_Seat_Locations=("Bench", lambda x: ", ".join([f"{b}-{s}" for b, s in zip(x, qp_summary_df.loc[x.index, "Seat"])]))
                )
                .reset_index()
                .sort_values(["Room", "Subject"])
            )
            st.subheader("📑 QP Requirement per Room (with Bench/Seat)")
            st.dataframe(qp_count_df)

            # --- Generate Room-wise QP PDFs and persist all downloads in session_state ---
            room_pdfs_local = {}  # temporary container
            if qp_files:
                for room in ordered_rooms:
                    room_students = seating_df[seating_df["Room"] == room]
                    valid_students = room_students[room_students["Subjects"] != "-"]
                    writer = PdfWriter()
                    for _, r in valid_students.iterrows():
                        subjects = [s.strip() for s in r["Subjects"].split(",") if s.strip()]
                        for subj in subjects:
                            # normalized subj
                            subj_norm = normalize_subject(subj)
                            if subj_norm in qp_mapping:
                                pdf_bytes = qp_mapping[subj_norm]
                            else:
                                match = get_close_matches(subj_norm, qp_mapping.keys(), n=1, cutoff=0.7)
                                pdf_bytes = qp_mapping[match[0]] if match else None
                            if pdf_bytes:
                                reader = PdfReader(io.BytesIO(pdf_bytes))
                                for page in reader.pages:
                                    writer.add_page(page)
                    if len(writer.pages) > 0:
                        output_bytes = io.BytesIO()
                        writer.write(output_bytes)
                        room_pdfs_local[room] = output_bytes.getvalue()
                    # if no pages, skip storing

            # --- Persist generated files (excel bytes + room pdfs) in session_state ---
            st.session_state["final_df_bytes"] = df_to_bytes(final_df)
            st.session_state["detailed_seating_bytes"] = df_to_bytes(seating_df)
            st.session_state["room_summary_bytes"] = df_to_bytes(summary_df)
            st.session_state["qp_detailed_bytes"] = df_to_bytes(qp_summary_df if not qp_summary_df.empty else pd.DataFrame())
            st.session_state["qp_count_bytes"] = df_to_bytes(qp_count_df if not qp_count_df.empty else pd.DataFrame())
            st.session_state["room_pdfs"] = room_pdfs_local
            st.session_state["generated"] = True

    # --- Show download buttons (read from session_state so they persist across reruns) ---
    if st.session_state.get("generated"):
        st.markdown("---")
        st.subheader("📥 Downloads")

        if st.session_state["final_df_bytes"]:
            st.download_button(
                label="📥 Download Seating Plan",
                data=st.session_state["final_df_bytes"],
                file_name="SeatingPlan.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_seatingplan"
            )
        if st.session_state["detailed_seating_bytes"]:
            st.download_button(
                label="📥 Download Detailed Seating",
                data=st.session_state["detailed_seating_bytes"],
                file_name="DetailedSeating.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_detailed"
            )
        if st.session_state["room_summary_bytes"]:
            st.download_button(
                label="📥 Download Room Summary",
                data=st.session_state["room_summary_bytes"],
                file_name="RoomSummary.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_room_summary"
            )
        if st.session_state["qp_detailed_bytes"]:
            st.download_button(
                label="📥 Download QP Summary (Detailed)",
                data=st.session_state["qp_detailed_bytes"],
                file_name="QP_Detailed.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_qp_detailed"
            )
        if st.session_state["qp_count_bytes"]:
            st.download_button(
                label="📥 Download QP Counts per Room",
                data=st.session_state["qp_count_bytes"],
                file_name="QP_Count.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_qp_counts"
            )

        # Room-wise PDF downloads
        if st.session_state["room_pdfs"]:
            st.subheader("📄 Room-wise QP PDFs")
            for room, pdf_bytes in st.session_state["room_pdfs"].items():
                st.download_button(
                    label=f"📥 Download {room} QPs",
                    data=pdf_bytes,
                    file_name=f"{room}_QPs.pdf",
                    mime="application/pdf",
                    key=f"dl_room_pdf_{room}"
                )
        else:
            st.info("No room PDFs were generated (no matching QPs uploaded).")
