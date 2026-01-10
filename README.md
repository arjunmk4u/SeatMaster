
# SeatMaster

Exam Seating and Question Paper Arrangement System

## Project Status (Checkpoint)

This repository represents a stable checkpoint of SeatMaster with the following scope:
- Support for Day 1 AN FN examinations
- Rebased and stabilized seating logic
- Rebased and stabilized question paper (QP) arrangement logic
- File-based storage model
- Manual data folder setup (not committed to repository)
Further extensions (database integration) are planned but not part of this checkpoint.

## Overview

SeatMaster is a Python-based Streamlit application designed to automate:

- Examination seating arrangements
- Room-wise question paper allocation
- Question paper requirement summaries


## Key Features (Current Version)

Seating Arrangement
- Bench-wise student allocation
- Left / Center / Right seating logic
- Ensures department separation (no adjacent same-department students)
- Room capacity handling
- Day 1 – FN/AN session isolation

 Question Paper Arrangement
- Room-wise subject aggregation
- Total question paper count calculation
- Normalized subject handling to avoid mismatches
- Detection of missing QPs during arrangement

Outputs

- Seating plan tables
- Question paper requirement summaries
- Room-wise subject QP distribution
## Tech Stack

- Python
- Streamlit (UI and workflow control)
- Pandas (data processing)
- PyPDF2 (for QP handling, where applicable)
- File-based storage (current version)
## Run Locally
The **data/** directory is intentionally not included in the repository.
**Users must manually create** the required structure before running the application.

Create the following structure at the project root:

```
data/
├── rooms/
│   └── RoomDB.csv
│
├── students/
│   └── students.csv
│
├── mapping/
│   └── subject_mapping.csv
│
├── qp_pdfs/
│   └── (question paper PDFs, optional)
│
└── templates/
    └── (template for seating csv)
```
## Installation

Clone Repository

```bash
git clone https://github.com/arjunmk4u/SeatMaster.git
cd SeatMaster
```
Create Virtual Environment (Recommended)
```
python -m venv venv
Windows: venv\Scripts\activate
mac: source venv/bin/activate
```
Install Dependencies
```
pip install -r requirements.txt
```
Running the Application
```
streamlit run app.py
```
**Ensure the data/ folder and required files exist before running.**
## Known Limitations (Current Checkpoint)

- File-based storage only (no database)
- No user authentication or role separation
- No concurrency protection
- Manual data validation required
- No audit or version history
These are known and accepted limitations at this development stage.

## Authors

- [@arjunmk4u](https://www.github.com/arjunmk4u)


## Feedback

If you have any feedback, feel free to contribute

