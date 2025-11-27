# SeatMaster - Copilot Instructions

## Project Overview
SeatMaster is a Streamlit-based exam seating arrangement and question paper (QP) distribution system. It processes Excel/CSV files to generate optimal seating plans and creates room-specific PDF bundles of question papers for exam administration.

## Architecture & Data Flow

### Core Components
- **`app.py`**: Main Streamlit interface with 4-tab workflow (Uploads → Seating → QP Arrangement → Downloads)
- **`seating.py`**: Core seating algorithm using interleaved assignment across rooms/benches/seats
- **`qp_arrange.py`**: PDF processing engine for generating room-specific QP bundles
- **`utils.py`**: Shared utilities for DataFrame-to-Excel conversion and subject normalization

### Session State Pattern
The app heavily relies on Streamlit session state for persistence across tabs:
```python
# Key session variables to understand:
st.session_state["room_df"]          # Parsed room data
st.session_state["students_df"]       # Student list with DAY columns
st.session_state["selected_rooms"]    # User-selected rooms in order
st.session_state["*_bytes"]          # Excel files as bytes for downloads
st.session_state["room_pdfs"]        # Generated PDF bundles per room
```

### Data Processing Workflow

1. **File Upload Phase**: Files stored as objects in session, parsed only when needed
2. **Seating Generation**: 
   - Uses interleaved assignment: Left→Right→Center seats across all rooms/benches
   - Student subjects come from selected DAY column (DAY1, DAY2, etc.)
   - Produces multiple views: pivot table for display, detailed seating for processing

3. **QP Arrangement**: 
   - Maps subjects to QP codes via mapping file
   - Generates room-specific PDF bundles using PyPDF2
   - Creates comprehensive summaries and counts

## Key Patterns & Conventions

### Subject Normalization
Always use `normalize_subject()` for consistent subject matching:
```python
from utils import normalize_subject
# Converts to uppercase, strips whitespace for reliable matching
```

### File Processing Pattern
```python
# Standard pattern for parsing uploaded files:
df = pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)
```

### Excel Output Pattern
Use `df_to_bytes()` from utils.py to convert DataFrames to downloadable Excel files:
```python
from utils import df_to_bytes
st.session_state["output_bytes"] = df_to_bytes(dataframe)
```

### Room Capacity Logic
Rooms have Start/End bench numbers. Total capacity = `(End - Start + 1) * 3` seats per room.

## Integration Points

### External Dependencies
- **PyPDF2**: PDF manipulation for QP bundling
- **pandas**: Data processing with Excel/CSV support via openpyxl
- **Streamlit**: Web interface with file upload/download capabilities

### File Format Requirements
- **Room Details**: Must have columns `Room`, `Start`, `End`
- **Student List**: Must have `Class No`, `Student Name`, and `DAY*` columns for subjects
- **QP Mapping**: Must have `Subject Name`, `QP Code` columns
- **QP PDFs**: Filename must match QP Code (case-insensitive)

## Development Patterns

### Error Handling
Graceful degradation with user-friendly warnings:
```python
if matched.size == 0:
    st.warning(f"No QP code found for subject '{subj}' (room {room})")
    continue
```

### State Management
Always check for required session state before operations:
```python
if not st.session_state.get("generated_seating"):
    st.info("Please generate seating in the Seating tab first.")
    return
```

### Multi-format Support
Support both CSV and Excel consistently across all file operations using filename-based detection.

## Running the Application
```bash
streamlit run app.py
```
The app runs as a single-page application with tab-based navigation for the complete workflow.