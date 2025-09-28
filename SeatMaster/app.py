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
tabs = st.tabs(["📁 File Uploads", "🪑 Seating Plan", "📄 QP Arrangement"])

# -------------------------
# Tab 1: Uploads
# -------------------------
with tabs[0]:
    st.header("📁 File Upload Manager")
    st.markdown("Upload all required files for the seating arrangement and QP generation process.")
    
    # Create upload sections with better organization
    with st.expander("📊 Core Data Files", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            room_file = st.file_uploader(
                "🏛️ Room Details", 
                type=["xlsx", "csv"], 
                key="u_room",
                help="Excel/CSV with columns: Room, Start, End"
            )
        with col2:
            student_file = st.file_uploader(
                "👨‍🎓 Student List", 
                type=["xlsx", "csv"], 
                key="u_students",
                help="Excel/CSV with Class No, Student Name, DAY1, DAY2..."
            )
    
    with st.expander("📄 QP Configuration Files", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            mapping_file = st.file_uploader(
                "🔗 QP Mapping", 
                type=["xlsx", "csv"], 
                key="u_mapping",
                help="Excel/CSV with QP Code and Subject Name columns"
            )
        with col2:
            qp_files = st.file_uploader(
                "📑 QP PDFs", 
                type=["pdf"], 
                accept_multiple_files=True, 
                key="u_qps",
                help="PDF files where filename matches QP Code"
            )

    # Centered save button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("💾 Save All Files to Session", key="save_uploads", type="primary", use_container_width=True):
            save_uploaded_files(room_file, student_file, mapping_file, qp_files)
            st.success("✅ Files saved successfully! Proceed to next tabs.")
            if qp_files:
                st.info(f"📑 {len(qp_files)} QP PDFs uploaded and ready.")

    st.markdown("---")
    st.subheader("📋 Upload Status")
    
    # Create status cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        room_status = "✅" if st.session_state["room_file_obj"] else "❌"
        room_name = getattr(st.session_state["room_file_obj"], "name", "Not uploaded")
        st.metric("🏛️ Room Details", room_status, room_name)
    
    with col2:
        student_status = "✅" if st.session_state["student_file_obj"] else "❌"
        student_name = getattr(st.session_state["student_file_obj"], "name", "Not uploaded")
        st.metric("👨‍🎓 Student List", student_status, student_name)
    
    with col3:
        mapping_status = "✅" if st.session_state["mapping_file_obj"] else "❌"
        mapping_name = getattr(st.session_state["mapping_file_obj"], "name", "Not uploaded")
        st.metric("🔗 QP Mapping", mapping_status, mapping_name)
    
    with col4:
        qp_count = len(st.session_state["qp_file_objs"]) if st.session_state["qp_file_objs"] else 0
        qp_status = "✅" if qp_count > 0 else "❌"
        st.metric("📑 QP PDFs", qp_status, f"{qp_count} files")

# -------------------------
# Tab 2: Seating
# -------------------------
with tabs[1]:
    st.header("🪑 Seating Plan Generator")
    st.markdown("Configure room selection and exam day, then generate optimized seating arrangements.")

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

        # Display previews and downloads if available
        if st.session_state.get("generated_seating"):
            st.markdown("---")
            st.subheader("🪑 Seating Arrangement Results")
            
            # Create tabs for different views
            result_tabs = st.tabs(["📊 Seating Plan", "📋 Room Summary", "📄 Detailed View", "📥 Downloads"])
            
            with result_tabs[0]:
                st.markdown("**Main seating arrangement by room and bench:**")
                try:
                    st.dataframe(pd.read_excel(io.BytesIO(st.session_state["final_df_bytes"])), use_container_width=True, hide_index=True)
                except Exception:
                    st.warning("Seating plan preview not available.")
            
            with result_tabs[1]:
                st.markdown("**Overview of subjects and students by room:**")
                try:
                    st.dataframe(pd.read_excel(io.BytesIO(st.session_state["room_summary_bytes"])), use_container_width=True, hide_index=True)
                except Exception:
                    st.warning("Room summary not available.")
            
            with result_tabs[2]:
                st.markdown("**Complete detailed seating with all information:**")
                try:
                    st.dataframe(pd.read_excel(io.BytesIO(st.session_state["detailed_seating_bytes"])), use_container_width=True, hide_index=True)
                except Exception:
                    st.warning("Detailed seating not available.")
            
            with result_tabs[3]:
                st.markdown("**Download seating-related files:**")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.session_state["final_df_bytes"]:
                        st.download_button(
                            "📊 Download Seating Plan", 
                            st.session_state["final_df_bytes"],
                            "SeatingPlan.xlsx", 
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_seating_plan",
                            use_container_width=True
                        )
                
                with col2:
                    if st.session_state["detailed_seating_bytes"]:
                        st.download_button(
                            "📋 Download Detailed Seating", 
                            st.session_state["detailed_seating_bytes"],
                            "DetailedSeating.xlsx", 
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_detailed_seating",
                            use_container_width=True
                        )
                
                with col3:
                    if st.session_state["room_summary_bytes"]:
                        st.download_button(
                            "🏛️ Download Room Summary", 
                            st.session_state["room_summary_bytes"],
                            "RoomSummary.xlsx", 
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_room_summary",
                            use_container_width=True
                        )
                
                # QP-related downloads in a separate row
                st.markdown("**QP Analysis Files:**")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.session_state["qp_summary_bytes"]:
                        st.download_button(
                            "📄 Download QP Summary", 
                            st.session_state["qp_summary_bytes"],
                            "QP_Summary.xlsx", 
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_qp_summary",
                            use_container_width=True
                        )
                
                with col2:
                    if st.session_state["qp_count_bytes"]:
                        st.download_button(
                            "🔢 Download QP Counts", 
                            st.session_state["qp_count_bytes"],
                            "QP_Counts.xlsx", 
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_qp_counts",
                            use_container_width=True
                        )
                
                with col3:
                    if st.session_state["hall_qp_summary_bytes"]:
                        st.download_button(
                            "🏛️ Download Hall QP Summary", 
                            st.session_state["hall_qp_summary_bytes"],
                            "Hall_QP_Summary.xlsx", 
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="dl_hall_qp_summary",
                            use_container_width=True
                        )
            

# -------------------------
# Tab 3: QP Arrangement
# -------------------------
with tabs[2]:
    st.header("📄 QP Arrangement & PDF Generation")
    st.markdown("Create room-specific question paper bundles using subject mappings and uploaded QP PDFs.")

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
        
        # Create tabs for better organization of data views
        summary_tabs = st.tabs(["🏛️ Room Summary", "📄 QP Details"])
        
        with summary_tabs[0]:
            st.markdown("**Overview of subjects by room:**")
            try:
                room_summary_df = pd.read_excel(io.BytesIO(st.session_state["room_summary_bytes"]))
                st.dataframe(room_summary_df, use_container_width=True, hide_index=True)
            except Exception:
                st.warning("Room summary not available.")
        
        with summary_tabs[1]:
            st.markdown("**Detailed question paper requirements:**")
            if st.session_state.get("qp_summary_bytes"):
                try:
                    qp_summary_df = pd.read_excel(io.BytesIO(st.session_state["qp_summary_bytes"]))
                    st.dataframe(qp_summary_df, use_container_width=True, hide_index=True)
                except Exception:
                    st.warning("QP summary preview not available.")
            else:
                st.info("No QP summary data present. Generate seating first.")

        # Style the generate button
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🚀 Generate Room-wise QP PDFs", key="gen_qp_pdfs", type="primary", use_container_width=True):
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

        # show room-wise QP summary table with better styling
        st.markdown("---")
        if st.session_state.get("room_qp_summary_df") is not None:
            st.subheader("📋 Room-wise QP Summary")
            st.markdown("**Detailed breakdown of question papers by room:**")
            
            # Style the dataframe
            st.dataframe(
                st.session_state["room_qp_summary_df"],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("🔄 Room-wise QP summary will appear here after generation.")

        # show room PDFs present with download buttons
        if st.session_state.get("room_pdfs"):
            st.subheader("📄 Generated Room PDFs")
            st.markdown("**Download individual room QP bundles:**")
            
            # Create columns for better layout
            num_rooms = len(st.session_state["room_pdfs"])
            cols_per_row = 3
            
            # Group room PDFs into rows
            room_items = list(st.session_state["room_pdfs"].items())
            
            for i in range(0, num_rooms, cols_per_row):
                cols = st.columns(cols_per_row)
                for j, col in enumerate(cols):
                    if i + j < num_rooms:
                        room, pdf_bytes = room_items[i + j]
                        with col:
                            # Create a styled container for each download button
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
                                
                                # Download button with custom styling
                                st.download_button(
                                    label=f"📥 Download {room} QPs",
                                    data=pdf_bytes,
                                    file_name=f"{room}_QPs.pdf",
                                    mime="application/pdf",
                                    key=f"dl_tab3_room_pdf_{i+j}",
                                    use_container_width=True
                                )
            
            # Add summary information
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📊 Total Rooms", len(st.session_state["room_pdfs"]))
            with col2:
                if st.session_state.get("room_qp_summary_df") is not None:
                    total_qps = st.session_state["room_qp_summary_df"]["Students"].sum() if "Students" in st.session_state["room_qp_summary_df"].columns else 0
                    st.metric("📄 Total QP Copies", total_qps)
            with col3:
                st.metric("✅ Status", "Ready for Download")
        else:
            st.info("🔄 Generate Room-wise QP PDFs above to see download options here.")

# -------------------------
# Tab 3: QP Arrangement (now tabs[2])
# -------------------------

# -------------------------
# End of app
# -------------------------
st.sidebar.markdown("# 🎓 SeatMaster")
st.sidebar.markdown("---")
st.sidebar.markdown("### 📋 Workflow Guide")
st.sidebar.markdown("""
1. **📁 File Uploads** - Upload all required files
2. **🪑 Seating Plan** - Generate seating arrangement
3. **📄 QP Arrangement** - Create room-specific QP bundles

💡 Downloads are available within each relevant tab!
""")

# Add workflow status indicators
st.sidebar.markdown("### ✅ Progress Tracker")
upload_status = "✅" if st.session_state.get("room_file_obj") and st.session_state.get("student_file_obj") else "⏳"
seating_status = "✅" if st.session_state.get("generated_seating") else "⏳"
qp_status = "✅" if st.session_state.get("generated_qp") else "⏳"

st.sidebar.markdown(f"""
- {upload_status} File Uploads
- {seating_status} Seating Generation  
- {qp_status} QP Bundle Creation
""")
