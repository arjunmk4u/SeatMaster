#  SeatMaster

**SeatMaster** is a Streamlit-based tool for generating exam seating arrangements, room capacity summaries, and question paper (QP) requirements with easy Excel exports.  

---

## ✨ Features
- Upload **room details** (start–end bench numbers).  
- Upload **student list** (with Class No, Name, Day-wise subjects).  
- Automatically assign students to benches (Left, Center, Right).  
- Generate:  
  - Seating Plan  
  - Detailed Seating (with subjects)  
  - Room Summary (subjects per room)  
  - Total QPs Needed  
  - Room-wise QP Requirement with Bench/Seat mapping  
- One-click **Excel downloads** for all reports.  

---

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/SeatMaster.git
   cd SeatMaster
   ```
   
2. Create and activate a virtual environment (recommended):
    ```bash
    python -m venv venv
    source venv/bin/activate   # Linux/Mac
    venv\Scripts\activate      # Windows
    ```

3. Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Run The Application
    ```bash
    streamlit run qp_generating.py
    ```


