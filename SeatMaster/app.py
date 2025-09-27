# app.py
import streamlit as st
import pandas as pd
import io

from utils import df_to_bytes, normalize_subject
from seating import generate_seating
from qp_arrange import generate_room_pdfs, generate_summaries

st.set_page_config(page_title="SeatMaster", layout="wide")
st.title("🎓 SeatMaster – Seating Arrangement & QP Generator")

# -------------------------
# Session state init
# -------------------------
default_keys = {
    "room_file_obj": None,
    "student_file_obj": None,
    "mapping_file_obj": None,
    "qp_file_objs": None,  # list of file-like objects
    "room_df": None,
    "students_df": None,
    "mapping_df": None,
    "uploaded_qps": None,  # dict qp_code -> bytes
    "selected_rooms": None,
    "selected_day": None,
    # outputs (bytes)
    "final_df_bytes": None,
    "detailed_seating_bytes": None,
    "room_summary_bytes": None,
    "qp_summary_bytes": None,
    "qp_count_bytes": None,
    "hall_qp_summary_bytes": None,
    "room_pdfs": None,
    "generated_seating": False,
    "generated_qp": False
}
for k, v in default_keys.items():
    if k not in st.session_state:
        st.session_state[k] = v

# -------------------------
# Helper to load uploaded files into session_state (but not parse until tab action)
# -------------------------
def save_uploaded_files(room_file, student_file, mapping_file, qp_files):
    if room_file:
        st.session_state["room_file_obj"] = room_file
    if student_file:
        st.session_state["student_file_obj"] = student_file
    if mapping_file:
        st.session_state["mapping_file_obj"] = mapping_file
    if qp_files:
        st.session_state["qp_file_objs"] = qp_files

def build_uploaded_qps(qp_file_objs):
    """Return dict keyed by QP code (filename without .pdf, uppercased) -> bytes"""
    if not qp_file_objs:
        return {}
    return {qp.name.rsplit(".pdf",1)[0].upper().strip(): qp.getvalue() for qp in qp_file_objs}

# -------------------------
# Tabs
# -------------------------
tabs = st.tabs(["Uploads", "Seating", "QP Arrangement", "Downloads"])

# -------------------------
# Tab 1: Uploads
# -------------------------
with tabs[0]:
    st.header("Upload files")
    st.markdown("Upload the room details, student list, optional QP mapping, and QP PDFs.")
    room_file = st.file_uploader("Upload Room Details (Excel with Room, Start, End)", type=["xlsx", "csv"], key="u_room")
    student_file = st.file_uploader("Upload Student List (Excel/CSV with Class No, Student Name, DAY1...)", type=["xlsx", "csv"], key="u_students")
    mapping_file = st.file_uploader("Upload QP Mapping (Excel/CSV with QP Code and Subject Name)", type=["xlsx", "csv"], key="u_mapping")
    qp_files = st.file_uploader("Upload QP PDFs (filename = QP Code)", type=["pdf"], accept_multiple_files=True, key="u_qps")

    if st.button("Save uploads to session", key="save_uploads"):
        save_uploaded_files(room_file, student_file, mapping_file, qp_files)
        # Build small preview / basic validation
        st.success("Files saved in session. Parse in Seating / QP tabs when you generate.")
        if qp_files:
            st.info(f"{len(qp_files)} QP PDFs uploaded.")

    st.markdown("---")
    st.subheader("Current session uploads")
    col1, col2 = st.columns(2)
    with col1:
        st.write("Room file:", getattr(st.session_state["room_file_obj"], "name", None))
        st.write("Students file:", getattr(st.session_state["student_file_obj"], "name", None))
    with col2:
        st.write("Mapping file:", getattr(st.session_state["mapping_file_obj"], "name", None))
        qps_list = [f.name for f in st.session_state["qp_file_objs"]] if st.session_state["qp_file_objs"] else None
        st.write("QP PDFs:", qps_list)

# -------------------------
# Tab 2: Seating
# -------------------------
with tabs[1]:
    st.header("Seating plan")
    st.markdown("Select rooms and the DAY column to use for subjects, then Generate Seating Plan.")

    # Load (parse) room and student files only when available in session
    room_df = None
    students = None
    if st.session_state["room_file_obj"]:
        rf = st.session_state["room_file_obj"]
        try:
            room_df = pd.read_csv(rf) if rf.name.endswith(".csv") else pd.read_excel(rf)
            st.session_state["room_df"] = room_df
        except Exception as e:
            st.error(f"Failed to parse room file: {e}")
    if st.session_state["student_file_obj"]:
        sf = st.session_state["student_file_obj"]
        try:
            students = pd.read_csv(sf) if sf.name.endswith(".csv") else pd.read_excel(sf)
            st.session_state["students_df"] = students
        except Exception as e:
            st.error(f"Failed to parse student file: {e}")

    if room_df is None or students is None:
        st.info("Please upload room and student files in the Uploads tab and save them to session.")
    else:
        st.subheader(f"📊 Total Students: {len(students)}")
        rooms = room_df["Room"].unique().tolist()
        selected_rooms = st.multiselect("Select Rooms (order is preserved)", rooms, key="select_rooms")
        subject_columns = [c for c in students.columns if c.upper().startswith("DAY")]
        selected_day = st.selectbox("Select Day to Conduct Subjects", subject_columns, key="select_day") if subject_columns else None

        # store selections
        st.session_state["selected_rooms"] = selected_rooms
        st.session_state["selected_day"] = selected_day

        if selected_rooms:
            total_capacity = sum(
                (int(room_df[room_df["Room"] == room].iloc[0]["End"]) - int(room_df[room_df["Room"] == room].iloc[0]["Start"]) + 1) * 3
                for room in selected_rooms
            )
            st.info(f"🪑 Total Capacity of Selected Rooms: {total_capacity} seats")

        if st.button("Generate Seating Plan", key="gen_seating"):
            # validations (same as your original logic)
            if not selected_rooms:
                st.error("Please select at least one room.")
            elif "Class No" not in students.columns or "Student Name" not in students.columns:
                st.error("Student list must contain 'Class No' and 'Student Name'.")
            else:
                # call generate_seating from seating.py
                seating_df, final_df = generate_seating(st.session_state["room_df"], st.session_state["students_df"], selected_rooms, selected_day)

                # generate summaries
                summary_df, qp_summary_df, qp_count_df, hall_qp_summary_df = generate_summaries(seating_df, selected_rooms)

                # persist bytes and dataframes in session
                st.session_state["final_df_bytes"] = df_to_bytes(final_df)
                st.session_state["detailed_seating_bytes"] = df_to_bytes(seating_df)
                st.session_state["room_summary_bytes"] = df_to_bytes(summary_df)
                st.session_state["qp_summary_bytes"] = df_to_bytes(qp_summary_df)
                st.session_state["qp_count_bytes"] = df_to_bytes(qp_count_df)
                st.session_state["hall_qp_summary_bytes"] = df_to_bytes(hall_qp_summary_df)

                # also store raw dataframes for tab preview
                st.session_state["seating_df_raw"] = seating_df
                st.session_state["final_df_raw"] = final_df
                st.session_state["qp_summary_raw"] = qp_summary_df

                st.session_state["generated_seating"] = True
                st.success("Seating plan generated and stored in session.")

        # Display previews if available
        if st.session_state.get("generated_seating"):
            st.subheader("🪑 Seating Arrangement (Preview)")
            try:
                st.dataframe(pd.read_excel(io.BytesIO(st.session_state["final_df_bytes"])))
            except Exception:
                st.write("Seating plan preview not available.")
            

# -------------------------
# Tab 3: QP Arrangement
# -------------------------
with tabs[2]:
    st.header("QP Arrangement & PDF generation")
    st.markdown("Provide mapping file (subject -> QP code) and QP PDFs, then generate room-wise QP PDFs.")

    # Parse mapping if present in session
    mapping_df = None
    if st.session_state["mapping_file_obj"]:
        mf = st.session_state["mapping_file_obj"]
        try:
            mapping_df = pd.read_csv(mf) if mf.name.endswith(".csv") else pd.read_excel(mf)
            if "QP Code" in mapping_df.columns:
                mapping_df['QP Code'] = mapping_df['QP Code'].astype(str).str.upper().str.strip()
            if "Subject Name" in mapping_df.columns:
                mapping_df['Subject Name'] = mapping_df['Subject Name'].apply(normalize_subject)
            st.session_state["mapping_df"] = mapping_df
        except Exception as e:
            st.error(f"Failed to parse mapping file: {e}")

    # Build uploaded_qps if files saved in session
    if st.session_state["qp_file_objs"]:
        uploaded_qps = build_uploaded_qps(st.session_state["qp_file_objs"])
        st.session_state["uploaded_qps"] = uploaded_qps

    if not st.session_state.get("generated_seating"):
        st.info("Please generate seating in the Seating tab first.")
    else:
        
        st.subheader("📋 Room Summary (Subjects)")
        try:
            st.dataframe(pd.read_excel(io.BytesIO(st.session_state["room_summary_bytes"])))
        except Exception:
            st.write("Room summary not available.")
        # show QP summary preview (from seating)
        st.subheader("QP Summary (detailed)")
        if st.session_state.get("qp_summary_bytes"):
            try:
                st.dataframe(pd.read_excel(io.BytesIO(st.session_state["qp_summary_bytes"])))
            except Exception:
                st.write("QP summary preview not available.")
        else:
            st.write("No QP summary data present. Generate seating first.")

        if st.button("Generate Room-wise QP PDFs", key="gen_qp_pdfs"):
            # validations
            if st.session_state["mapping_df"] is None:
                st.warning("No mapping file found in session; QP codes cannot be resolved.")
            if not st.session_state["uploaded_qps"]:
                st.warning("No QP PDFs uploaded; cannot build room PDFs.")

            # call generator and get room-wise summary
            ordered_rooms = st.session_state.get("selected_rooms") or []
            qp_summary_df = st.session_state.get("qp_summary_raw", pd.DataFrame())
            room_pdfs, room_qp_summary_df = generate_room_pdfs(
                st.session_state.get("mapping_df"),
                qp_summary_df,
                st.session_state.get("uploaded_qps", {}),
                ordered_rooms
            )

            st.session_state["room_pdfs"] = room_pdfs
            st.session_state["room_qp_summary_df"] = room_qp_summary_df  # store for display & download
            st.session_state["generated_qp"] = True
            st.success("Room-wise QP PDFs generated (where mappings + uploads matched).")

        # show room-wise QP summary table
        if st.session_state.get("room_qp_summary_df") is not None:
            st.subheader("📋 Room-wise QP Summary")
            st.dataframe(st.session_state["room_qp_summary_df"])
        else:
            st.info("Room-wise QP summary will appear here after generation.")

        # show room PDFs present
        if st.session_state.get("room_pdfs"):
            st.subheader("Generated Room PDFs (preview list)")
            st.write(list(st.session_state["room_pdfs"].keys()))

# -------------------------
# Tab 4: Downloads
# -------------------------
with tabs[3]:
    st.header("Downloads")
    st.markdown("Download generated spreadsheets and room PDFs.")

    if not st.session_state.get("generated_seating"):
        st.info("No outputs to download yet. Generate seating and/or QP PDFs first.")
    else:
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
        if st.session_state.get("room_pdfs"):
            st.subheader("📄 Room-wise QP PDFs")
            for i, (room, pdf_bytes) in enumerate(st.session_state["room_pdfs"].items()):
                st.download_button(f"📥 Download {room} QPs", pdf_bytes, f"{room}_QPs.pdf", "application/pdf", key=f"dl_room_pdf_{i}")

# -------------------------
# End of app
# -------------------------
st.sidebar.markdown("SeatMaster")
st.sidebar.write("Use tabs to manage workflow: Uploads → Seating → QP Arrangement → Downloads.")
