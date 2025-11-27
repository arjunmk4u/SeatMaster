# app.py
import streamlit as st
import pandas as pd
import io
import os

from sheet_filter import generate_exam_sheets
from utils import df_to_bytes, normalize_subject
from seating import generate_seating
from qp_arrange import generate_room_pdfs, generate_summaries
from data_loader import load_data_by_category
from remark_generator import generate_remark_sheets

# -------------------------
# Page setup
# -------------------------
st.set_page_config(page_title="SeatMaster", layout="wide")
st.title("🎓 SeatMaster")

# -------------------------
# Session state defaults
# -------------------------
default_keys = {
    # static data
    "room_df": None,
    "mapping_df": None,
    "template_path": None,
    "student_map_df": None,   # permanent student mapping
    "uploaded_qps": None,

    # dynamic exam data
    "exam_students_df": None,
    "qp_file_objs": None,
    "selected_rooms": None,
    "selected_day": None,

    # outputs
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
# Sidebar: UG/PG selector
# -------------------------
st.sidebar.markdown("### 🎯 Select Category")
mode = st.sidebar.radio("Choose Data Type", ["UG", "PG"], index=1, horizontal=True)
st.session_state["category"] = mode

# Auto-load static data
if st.session_state.get("room_df") is None or st.session_state.get("mapping_df") is None:
    loaded_data = load_data_by_category(mode)
    st.session_state.update(loaded_data)
    st.sidebar.success(f"📂 Loaded {mode} data from /data/")

if st.sidebar.button("🔄 Reload Static Data"):
    loaded_data = load_data_by_category(mode)
    st.session_state.update(loaded_data)
    st.sidebar.info(f"✅ Reloaded static data for {mode}")

# -------------------------
# Tabs
# -------------------------
tabs = st.tabs(["📁 Exam Uploads", "🪑 Seating Plan", "📄 QP Arrangement", "📝 Remark Sheet Generator"])

# -------------------------
# Tab 1: Exam Uploads
# -------------------------
with tabs[0]:
    st.header("📁 Exam-specific Uploads")
    st.markdown("""
    Upload the **exam student list** (with DAY columns) and optional QP PDFs for the current exam.  
    Static data — rooms, student mappings, templates, and QP code maps — are loaded automatically from `/data/`.
    """)

    col1, col2 = st.columns(2)
    with col1:
        exam_students_file = st.file_uploader(
            "📥 Upload Exam Student List (Class No, Student Name, DAY1, DAY2...)", 
            type=["xlsx", "csv"],
            key="u_exam_students"
        )
    with col2:
        exam_qp_files = st.file_uploader(
            "📑 Upload QP PDFs (optional, overrides static /data/qp_pdfs/)", 
            type=["pdf"], 
            accept_multiple_files=True,
            key="u_exam_qps"
        )

    st.markdown("---")
    if st.button("📦 Load Exam Files into Session"):
        try:
            if exam_students_file:
                df = pd.read_excel(exam_students_file) if exam_students_file.name.endswith(".xlsx") else pd.read_csv(exam_students_file)
                st.session_state["exam_students_df"] = df
                st.success(f"✅ Loaded {len(df)} exam students.")
            if exam_qp_files:
                qp_dict = {qp.name.rsplit(".pdf", 1)[0].upper(): qp.getvalue() for qp in exam_qp_files}
                existing = st.session_state.get("uploaded_qps") or {}
                existing.update(qp_dict)
                st.session_state["uploaded_qps"] = existing
                st.success(f"✅ {len(exam_qp_files)} QP PDFs loaded into session.")
        except Exception as e:
            st.error(f"Error loading exam data: {e}")

    # show status
    st.markdown("### 📊 Current Data Status")
    col1, col2, col3 = st.columns(3)

    room_df = st.session_state.get("room_df")
    exam_df = st.session_state.get("exam_students_df")
    qp_dict = st.session_state.get("uploaded_qps")

    room_count = len(room_df) if room_df is not None else 0
    exam_count = len(exam_df) if exam_df is not None else 0
    qp_count = len(qp_dict) if qp_dict is not None else 0

    with col1:
        st.metric("🏛️ Rooms", room_count)
    with col2:
        st.metric("👨‍🎓 Exam Students", exam_count)
    with col3:
        st.metric("📑 QP PDFs in Memory", qp_count)

    st.info("Permanent student mappings are auto-loaded separately for remark sheet generation. They are **not used** for seating.")

# -------------------------
# Tab 2: Seating Plan
# -------------------------
with tabs[1]:
    st.header("🪑 Seating Plan Generator")
    st.markdown("Uses only the **uploaded exam student file** (from Tab 1).")

    room_df = st.session_state.get("room_df")
    exam_students = st.session_state.get("exam_students_df")

    if room_df is None or exam_students is None or exam_students.empty:
        st.warning("Please upload the exam student file first in the 'Exam Uploads' tab.")
    else:
        st.subheader(f"📊 Total Students (for this exam): {len(exam_students)}")

        rooms = room_df["Room"].unique().tolist() if "Room" in room_df.columns else []
        selected_rooms = st.multiselect("Select Rooms", rooms, key="select_rooms")
        day_cols = [c for c in exam_students.columns if c.upper().startswith("DAY")]
        selected_day = st.selectbox("Select Exam Day", day_cols, key="select_day") if day_cols else None

        st.session_state["selected_rooms"] = selected_rooms
        st.session_state["selected_day"] = selected_day

        if selected_rooms:
            total_capacity = sum(
                (int(room_df[room_df["Room"] == room].iloc[0]["End"]) -
                 int(room_df[room_df["Room"] == room].iloc[0]["Start"]) + 1) * 3
                for room in selected_rooms
            )
            st.info(f"🪑 Total Capacity of Selected Rooms: {total_capacity}")

        if st.button("🚀 Generate Seating Plan", key="gen_seating"):
            try:
                if not selected_rooms:
                    st.error("Please select at least one room.")
                elif "Class No" not in exam_students.columns or "Student Name" not in exam_students.columns:
                    st.error("Exam file must contain 'Class No' and 'Student Name'.")
                else:
                    seating_df, final_df = generate_seating(room_df, exam_students, selected_rooms, selected_day)
                    summary_df, qp_summary_df, qp_count_df, hall_qp_summary_df = generate_summaries(seating_df, selected_rooms)

                    st.session_state["final_df_bytes"] = df_to_bytes(final_df)
                    st.session_state["detailed_seating_bytes"] = df_to_bytes(seating_df)
                    st.session_state["room_summary_bytes"] = df_to_bytes(summary_df)
                    st.session_state["qp_summary_bytes"] = df_to_bytes(qp_summary_df)
                    st.session_state["qp_count_bytes"] = df_to_bytes(qp_count_df)
                    st.session_state["hall_qp_summary_bytes"] = df_to_bytes(hall_qp_summary_df)
                    st.session_state["qp_summary_raw"] = qp_summary_df
                    st.session_state["seating_df"] = seating_df
                    st.session_state["generated_seating"] = True
                    st.success("✅ Seating plan generated successfully.")
            except Exception as e:
                st.error(f"Error generating seating: {e}")

        if st.session_state.get("generated_seating"):
            st.markdown("---")
            st.subheader("🪑 Seating Results")
            tabs2 = st.tabs(["📊 Seating Plan", "📋 Room Summary", "📄 Detailed", "📥 Downloads"])
            with tabs2[0]:
                st.dataframe(pd.read_excel(io.BytesIO(st.session_state["final_df_bytes"])), width='stretch')
            with tabs2[1]:
                st.dataframe(pd.read_excel(io.BytesIO(st.session_state["room_summary_bytes"])), width='stretch')
            with tabs2[2]:
                st.dataframe(pd.read_excel(io.BytesIO(st.session_state["detailed_seating_bytes"])), width='stretch')
            with tabs2[3]:
                st.download_button("📊 Download Seating Plan", st.session_state["final_df_bytes"], "SeatingPlan.xlsx")
                st.download_button("📋 Download Detailed Seating", st.session_state["detailed_seating_bytes"], "DetailedSeating.xlsx")
                st.download_button("🏛️ Download Room Summary", st.session_state["room_summary_bytes"], "RoomSummary.xlsx")
                st.download_button("📄 Download QP Summary", st.session_state["qp_summary_bytes"], "QP_Summary.xlsx")
                st.download_button("🔢 Download QP Counts", st.session_state["qp_count_bytes"], "QP_Counts.xlsx")
                st.download_button("🏛️ Download Hall QP Summary", st.session_state["hall_qp_summary_bytes"], "Hall_QP_Summary.xlsx")

# -------------------------
# Tab 3: QP Arrangement
# -------------------------
with tabs[2]:
    st.header(f"📄 QP Arrangement & PDF Generation ({mode})")
    st.markdown("Create room-specific question paper bundles using subject mappings and uploaded QP PDFs.")

    mapping_df = st.session_state.get("mapping_df")
    uploaded_qps = st.session_state.get("uploaded_qps") or {}

    if not st.session_state.get("generated_seating"):
        st.info("Please generate seating first.")
    else:
        summary_tabs = st.tabs(["🏛️ Room Summary", "📄 QP Details"])
        with summary_tabs[0]:
            st.markdown("**Overview of subjects by room:**")
            st.dataframe(pd.read_excel(io.BytesIO(st.session_state["room_summary_bytes"])), width='stretch')
        with summary_tabs[1]:
            st.markdown("**Detailed question paper requirements:**")
            st.dataframe(pd.read_excel(io.BytesIO(st.session_state["qp_summary_bytes"])), width='stretch')

        # --- Normalize QP mapping before generation ---
        if mapping_df is not None:
            if "QP Code" in mapping_df.columns:
                mapping_df["QP Code"] = mapping_df["QP Code"].astype(str).str.upper().str.strip()
            if "Subject Name" in mapping_df.columns:
                mapping_df["Subject Name"] = mapping_df["Subject Name"].apply(normalize_subject)
            st.session_state["mapping_df"] = mapping_df

        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🚀 Generate Room-wise QP PDFs", key="gen_qp_pdfs", use_container_width=True):
                try:
                    ordered_rooms = st.session_state.get("selected_rooms") or []
                    qp_summary_df = st.session_state.get("qp_summary_raw", pd.DataFrame())

                    # Generate PDFs
                    room_pdfs, room_qp_summary_df = generate_room_pdfs(
                        mapping_df,
                        qp_summary_df,
                        uploaded_qps,
                        ordered_rooms
                    )

                    st.session_state["room_pdfs"] = room_pdfs
                    st.session_state["room_qp_summary_df"] = room_qp_summary_df
                    st.session_state["generated_qp"] = len(room_pdfs) > 0

                    if len(room_pdfs) > 0:
                        st.success(f"✅ Room-wise QP PDFs generated successfully! ({len(room_pdfs)} rooms)")
                    else:
                        st.error("❌ No QP PDFs were generated!")

                    # --- Debug / Missing QP Detection ---
                    available_qps = list(uploaded_qps.keys())
                    required_qps = room_qp_summary_df["QP Code"].unique().tolist() if "QP Code" in room_qp_summary_df.columns else []
                    missing_qps = [qp for qp in required_qps if qp not in available_qps]

                    if missing_qps:
                        st.warning(f"⚠️ {len(missing_qps)} QP(s) not found among uploaded PDFs:")
                        st.code("\n".join(missing_qps))
                    else:
                        if len(room_pdfs) == 0:
                            st.error("❌ No matching QP PDFs found. Check mapping & PDF filenames.")
                        else:
                            st.info("✅ All required QP PDFs are available and matched correctly.")


                except Exception as e:
                    st.error(f"❌ Error generating room PDFs: {e}")

        # -------------------------
        # Styled Room-wise QP Download Section
        # -------------------------
        if st.session_state.get("room_pdfs"):
            st.markdown("---")
            st.subheader(f"📄 Generated Room PDFs ({mode})")
            st.markdown("**Download individual room QP bundles:**")

            num_rooms = len(st.session_state["room_pdfs"])
            cols_per_row = 3
            room_items = list(st.session_state["room_pdfs"].items())

            for i in range(0, num_rooms, cols_per_row):
                cols = st.columns(cols_per_row)
                for j, col in enumerate(cols):
                    if i + j < num_rooms:
                        room, pdf_bytes = room_items[i + j]
                        with col:
                            with st.container():
                                st.markdown(f"""
                                <div style="
                                    border: 2px solid #1f77b4;
                                    border-radius: 10px;
                                    padding: 15px;
                                    margin: 5px 0;
                                    background: linear-gradient(135deg, #f0f8ff 0%, #e6f3ff 100%);
                                    text-align: center;
                                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                                ">
                                    <h4 style="margin: 0 0 10px 0; color: #1f77b4;">🏛️ {room}</h4>
                                    <p style="margin: 0; color: #666; font-size: 0.9em;">
                                        PDF Bundle Ready
                                    </p>
                                </div>
                                """, unsafe_allow_html=True)

                                st.download_button(
                                    label=f"📥 Download {room} QPs",
                                    data=pdf_bytes,
                                    file_name=f"{mode}_{room}_QPs.pdf",
                                    mime="application/pdf",
                                    key=f"dl_tab3_room_pdf_{i+j}",
                                    use_container_width=True
                                )

            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📊 Total Rooms", len(st.session_state["room_pdfs"]))
            with col2:
                total_qps = (
                    st.session_state["room_qp_summary_df"]["Students"].sum()
                    if st.session_state.get("room_qp_summary_df") is not None
                    and "Students" in st.session_state["room_qp_summary_df"].columns
                    else 0
                )
                st.metric("📄 Total QP Copies", total_qps)
            with col3:
                st.metric("✅ Status", "Ready for Download")
        else:
            st.info("🔄 Generate Room-wise QP PDFs above to see download options here.")

# -------------------------
# Tab 4: Remark Sheet Generator
# -------------------------
with tabs[3]:
    st.header("📝 Remark Sheet Generator")
    st.markdown("Automatically fill remark sheets per room using seating data and the official template.")

    exam_title = st.text_input("Enter Exam Title (e.g. Internal Examination - September 2025)")
    exam_date = st.text_input("Enter Exam Date (e.g. 29/09/2025)")

    if st.button("Generate Remark Sheets", key="generate_remarks"):
        if "seating_df" not in st.session_state or st.session_state["seating_df"] is None:
            st.error("⚠️ Seating data missing. Please generate seating first.")
        else:
            try:
                seating_df = st.session_state["seating_df"]
                template_path = st.session_state.get("template_path") or "data/templates/template.xlsx"
                output_path = f"output/remarks_filled_{exam_title.replace(' ', '_')}.xlsx"

                result_path = generate_remark_sheets(seating_df, exam_title, exam_date, template_path, output_path)

                st.success(f"✅ Remark sheets generated successfully for {len(seating_df['Room'].unique())} rooms.")
                with open(result_path, "rb") as f:
                    st.download_button("📥 Download Remark Sheets", f, file_name=os.path.basename(result_path))
            except Exception as e:
                st.error(f"❌ Error generating remark sheets: {e}")

# -------------------------
# Sidebar help & status
# -------------------------
st.sidebar.markdown("---")
st.sidebar.markdown("### 📋 Workflow Guide")
st.sidebar.markdown("""
1. **Exam Uploads** – Upload the student file and QP PDFs for this exam  
2. **Seating Plan** – Generate seating from the exam list  
3. **QP Arrangement** – Produce room-specific QP bundles  
4. **Remark Sheet** – Auto-fill remark templates  
""")

st.sidebar.markdown("### ✅ Progress Tracker")
upload_status = "✅" if st.session_state.get("room_df") is not None else "⏳"
exam_status = "✅" if st.session_state.get("exam_students_df") is not None else "⏳"
seating_status = "✅" if st.session_state.get("generated_seating") else "⏳"
qp_status = "✅" if st.session_state.get("generated_qp") else "⏳"
st.sidebar.markdown(f"""
- {upload_status} Static Data Loaded  
- {exam_status} Exam Data Uploaded  
- {seating_status} Seating Generated  
- {qp_status} QP Bundles Created
""")
