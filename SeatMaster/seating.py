import pandas as pd
from utils import normalize_subject, df_to_bytes

def generate_seating(room_df, students, selected_rooms, selected_day):
    ordered_rooms = selected_rooms
    seats = ["Left", "Right", "Center"]
    seating_data = []

    # Prepare benches per room
    room_benches = {}
    for room in ordered_rooms:
        row = room_df[room_df["Room"] == room].iloc[0]
        start, end = int(row["Start"]), int(row["End"])
        room_benches[room] = list(range(start, end + 1))

    # Interleaved seating assignment
    for seat in seats:
        for room in ordered_rooms:
            for bench in room_benches[room]:
                seating_data.append({"Room": room, "Bench": bench, "Seat": seat})

    # Assign students
    student_list = students.values.tolist()
    student_columns = students.columns.tolist()
    for i, slot in enumerate(seating_data):
        if i < len(student_list):
            row = student_list[i]
            info = dict(zip(student_columns, row))
            slot["Class No"] = info["Class No"]
            slot["Student Name"] = info["Student Name"]
            if selected_day and pd.notna(info[selected_day]):
                raw = str(info[selected_day])
                subjects = [normalize_subject(s) for s in raw.split(",") if str(s).strip() != ""]
                slot["Subjects"] = ", ".join(subjects) if subjects else "-"
            else:
                slot["Subjects"] = "-"
        else:
            slot.update({"Class No": "-", "Student Name": "-", "Subjects": "-"})

    seating_df = pd.DataFrame(seating_data)

    # Pivot view for display
    final_df = seating_df.pivot_table(
        index=["Room","Bench"], 
        columns="Seat", 
        values="Class No", 
        aggfunc="first"
    ).reset_index()

    display_cols = ["Room","Bench"]
    for c in ["Left","Center","Right"]:
        if c in final_df.columns:
            display_cols.append(c)

    final_df = final_df[display_cols]
    final_df["Room"] = pd.Categorical(final_df["Room"], categories=ordered_rooms, ordered=True)
    final_df = final_df.sort_values(["Room","Bench"]).reset_index(drop=True)

    return seating_df, final_df


