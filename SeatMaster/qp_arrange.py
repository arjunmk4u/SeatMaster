import io
from PyPDF2 import PdfReader, PdfWriter
import pandas as pd
import streamlit as st
from utils import normalize_subject


def generate_summaries(seating_df, ordered_rooms):
    summary_records = []
    qp_summary_records = []
    all_subjects = []

    for _, row in seating_df[seating_df["Subjects"] != "-"].iterrows():
        bench, seat, room = row["Bench"], row["Seat"], row["Room"]
        for s in str(row["Subjects"]).split(","):
            s_norm = normalize_subject(s)
            if s_norm:
                qp_summary_records.append({"Room": room, "Bench": bench, "Seat": seat, "Subject": s_norm})
                all_subjects.append(s_norm)

    qp_summary_df = pd.DataFrame(qp_summary_records)

    # Room summary
    for room in ordered_rooms:
        rs = seating_df[seating_df["Room"] == room]
        room_subjects = []
        for subj_list in rs[rs["Subjects"] != "-"]["Subjects"]:
            for s in str(subj_list).split(","):
                s_norm = normalize_subject(s)
                if s_norm:
                    room_subjects.append(s_norm)
        summary_records.append({
            "Room": room,
            "Total Students": len(rs[rs["Class No"] != "-"]),
            "Subjects in Room": ", ".join(sorted(set(room_subjects)))
        })

    summary_df = pd.DataFrame(summary_records)

    # QP detailed counts
    if not qp_summary_df.empty:
        qp_count_df = (
            qp_summary_df.groupby(["Room","Subject"])
            .agg(
                QP_Needed=("Subject","count"),
                Bench_Seat_Locations=("Bench", 
                    lambda x: ", ".join([f"{b}-{s}" for b,s in zip(x, qp_summary_df.loc[x.index,"Seat"])]))
            )
            .reset_index()
            .sort_values(["Room","Subject"])
        )
    else:
        qp_count_df = pd.DataFrame(columns=["Room","Subject","QP_Needed","Bench_Seat_Locations"])

    # Hall summary
    if not qp_summary_df.empty:
        hall_qp_summary_df = (
            qp_summary_df.groupby(["Room","Subject"])
            .size()
            .reset_index(name="Total QPs Needed")
            .sort_values(["Room","Subject"])
        )
    else:
        hall_qp_summary_df = pd.DataFrame(columns=["Room","Subject","Total QPs Needed"])

    return summary_df, qp_summary_df, qp_count_df, hall_qp_summary_df

def generate_room_pdfs(mapping_df, qp_summary_df, uploaded_qps, ordered_rooms):
    room_pdfs = {}
    room_summary_rows = []

    if mapping_df is not None and not qp_summary_df.empty and uploaded_qps:
        for room in ordered_rooms:
            room_rows = qp_summary_df[qp_summary_df["Room"] == room]
            if room_rows.empty:
                continue

            subject_counts = room_rows["Subject"].value_counts().to_dict()
            writer = PdfWriter()

            for subj, count in subject_counts.items():
                matched = mapping_df[mapping_df["Subject Name"] == subj]["QP Code"].values
                if matched.size == 0:
                    st.warning(f"No QP code found for subject '{subj}' (room {room})")
                    continue
                qp_code = matched[0]
                if qp_code not in uploaded_qps:
                    st.warning(f"No uploaded PDF found for QP code '{qp_code}' (subject {subj}, room {room})")
                    continue

                reader = PdfReader(io.BytesIO(uploaded_qps[qp_code]))
                for _ in range(int(count)):
                    for p in reader.pages:
                        writer.add_page(p)

                # Add to summary
                room_summary_rows.append({
                    "Room": room,
                    "Subject": subj,
                    "QP Code": qp_code,
                    "Students": count
                })

            if len(writer.pages) > 0:
                out = io.BytesIO()
                writer.write(out)
                out.seek(0)
                room_pdfs[room] = out.getvalue()

    # Create summary DataFrame
    room_summary_df = pd.DataFrame(room_summary_rows)
    if not room_summary_df.empty:
        # Group by Room and Subject for cleaner view
        room_summary_df = (
            room_summary_df
            .groupby(["Room", "Subject", "QP Code"], as_index=False)
            .agg({"Students": "sum"})
            .sort_values("Room")
        )

        # Optionally, add total students per room
        total_per_room = room_summary_df.groupby("Room")["Students"].sum().reset_index()
        total_per_room.rename(columns={"Students": "Total Students"}, inplace=True)
        room_summary_df = room_summary_df.merge(total_per_room, on="Room")

    return room_pdfs, room_summary_df
