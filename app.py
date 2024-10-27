import re
import pandas as pd
import pdfplumber
import tempfile
import streamlit as st
from io import BytesIO
import zipfile

# Define a maximum number of files allowed
MAX_FILES = 50

# Helper function to process each athlete's runs
def process_athlete_runs(data, athlete_info, run_data):
    for run in run_data:
        main_times = run[0::2]
        bracket_numbers = run[:-1][1::2]
        combined_run = []
        for main_time, bracket_number in zip(main_times[:-1], bracket_numbers):
            combined_run.append(main_time)
            combined_run.append(bracket_number)
        combined_run.append(run[-1])
        data.append([athlete_info['No'], athlete_info['Nat'], athlete_info['Name']] + combined_run)

# Streamlit setup
st.title("Multi-File PDF Processor")
st.write("Upload one or more PDF files, and this app will extract and process the data from each file into separate Excel files.")

# Multiple file uploader
uploaded_files = st.file_uploader("Choose PDF files", type="pdf", accept_multiple_files=True)

# Initialize a dictionary to store processed files for download
output_files = {}

if uploaded_files:
    # Check if the number of uploaded files exceeds the limit
    if len(uploaded_files) > MAX_FILES:
        st.warning(f"Please upload a maximum of {MAX_FILES} files.")
    else:
        for uploaded_file in uploaded_files:
            input_filename = uploaded_file.name.rsplit('.', 1)[0]

            # Save the uploaded file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
                temp_pdf.write(uploaded_file.read())
                pdf_path = temp_pdf.name

            # Initialize data storage for each file
            data = []
            athlete_info = {}
            run_data = []

            # Regex patterns
            athlete_pattern = r'(\d+)\s+([A-Z]{3})\s+([A-Za-z\s]+)'
            run_pattern = r'([\d\.]+)\s+\((\d+)\)\s+([\d\.]+)\s+\((\d+)\)\s+([\d\.]+)\s+\((\d+)\)\s+([\d\.]+)\s+\((\d+)\)\s+([\d\.]+)\s+\((\d+)\)\s+([\d\.]+)\s+\((\d+)\)\s+([\d\.]+)'

            # Open PDF and extract text
            with pdfplumber.open(pdf_path) as pdf:
                text_data = ""
                for page in pdf.pages:
                    text_data += page.extract_text()

            # Process each line
            for line in text_data.splitlines():
                athlete_match = re.match(athlete_pattern, line)
                if athlete_match:
                    if athlete_info and run_data:
                        process_athlete_runs(data, athlete_info, run_data)
                    
                    athlete_info = {
                        'No': athlete_match.group(1),
                        'Nat': athlete_match.group(2),
                        'Name': athlete_match.group(3).strip()
                    }
                    run_data = []

                run_match = re.findall(run_pattern, line)
                if run_match:
                    run_data.append(run_match[0])
                
                if 'DNS' in line:
                    run_data.append(['DNS'] * 14)

            if athlete_info and run_data:
                process_athlete_runs(data, athlete_info, run_data)

            # DataFrame columns
            columns = [
                "No", "Nat", "Name", 
                "split_1", "split_1_bracket", 
                "split_2", "split_2_bracket", 
                "split_3", "split_3_bracket", 
                "split_4", "split_4_bracket", 
                "split_5", "split_5_bracket", 
                "finish_time", "finish_time_bracket", 
                "top_speed_kmh"
            ]

            # Convert to DataFrame
            df = pd.DataFrame(data, columns=columns)

            # Save the DataFrame to a BytesIO object for download
            excel_data = BytesIO()
            df.to_excel(excel_data, index=False, engine="openpyxl")
            excel_data.seek(0)
            output_files[f"{input_filename}_processed.xlsx"] = excel_data

        # "Download All" button to download a zip file containing all processed files
        with BytesIO() as zip_buffer:
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED) as zip_file:
                for filename, excel_data in output_files.items():
                    zip_file.writestr(filename, excel_data.getvalue())
            zip_buffer.seek(0)

            st.download_button(
                label="Download All Processed Files as ZIP",
                data=zip_buffer,
                file_name="processed_files.zip",
                mime="application/zip"
            )

        # Individual download buttons for each processed file
        st.write("## Download Individual Processed Files")
        for filename, excel_data in output_files.items():
            st.download_button(
                label=f"Download {filename}",
                data=excel_data,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
