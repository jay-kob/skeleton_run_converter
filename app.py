import re
import tempfile

import pandas as pd
import pdfplumber
import streamlit as st


# Helper function to process each athlete's runs
def process_athlete_runs(data, athlete_info, run_data):
    for run in run_data:
        main_times = run[0::2]  # Extract times (even indices)
        bracket_numbers = run[:-1][
            1::2
        ]  # Extract numbers in brackets (odd indices)

        combined_run = []

        # Combine times and bracketed numbers in correct order for splits and finish
        for main_time, bracket_number in zip(main_times[:-1], bracket_numbers):
            combined_run.append(main_time)  # Time value
            combined_run.append(bracket_number)  # Bracketed value

        combined_run.append(run[-1])  # Top speed (without bracket)

        # Append the athlete info and the processed run data
        data.append(
            [athlete_info["No"], athlete_info["Nat"], athlete_info["Name"]]
            + combined_run
        )


# Streamlit setup
st.title("PDF to Excel Athlete Data Processor")
st.write(
    "Upload a PDF file with athlete data, and this app will extract and process the data into an Excel file."
)

# File uploader
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf")

if uploaded_file:
    # Get the original file name without the extension
    input_filename = uploaded_file.name.rsplit(".", 1)[0]
    # Save the uploaded file to a temporary location
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
        temp_pdf.write(uploaded_file.read())
        pdf_path = temp_pdf.name

    # Initialize data storage
    data = []
    athlete_info = {}
    run_data = []

    # Regex patterns
    athlete_pattern = (
        r"(\d+)\s+([A-Z]{3})\s+([A-Za-z\s]+)"  # Matches No, Nat, Name
    )
    run_pattern = r"([\d\.]+)\s+\((\d+)\)\s+([\d\.]+)\s+\((\d+)\)\s+([\d\.]+)\s+\((\d+)\)\s+([\d\.]+)\s+\((\d+)\)\s+([\d\.]+)\s+\((\d+)\)\s+([\d\.]+)\s+\((\d+)\)\s+([\d\.]+)"

    # Open PDF and extract text
    with pdfplumber.open(pdf_path) as pdf:
        text_data = ""
        for page in pdf.pages:
            text_data += page.extract_text()

    # Process each line in the text data
    for line in text_data.splitlines():
        athlete_match = re.match(athlete_pattern, line)
        if athlete_match:
            if athlete_info and run_data:
                process_athlete_runs(data, athlete_info, run_data)

            athlete_info = {
                "No": athlete_match.group(1),
                "Nat": athlete_match.group(2),
                "Name": athlete_match.group(3).strip(),
            }
            run_data = []

        run_match = re.findall(run_pattern, line)
        if run_match:
            run_data.append(run_match[0])

        if "DNS" in line:
            run_data.append(["DNS"] * 14)

    if athlete_info and run_data:
        process_athlete_runs(data, athlete_info, run_data)

    # DataFrame columns
    columns = [
        "No",
        "Nat",
        "Name",
        "split_1",
        "split_1_bracket",
        "split_2",
        "split_2_bracket",
        "split_3",
        "split_3_bracket",
        "split_4",
        "split_4_bracket",
        "split_5",
        "split_5_bracket",
        "finish_time",
        "finish_time_bracket",
        "top_speed_kmh",
    ]

    # Convert to DataFrame
    df = pd.DataFrame(data, columns=columns)

    # Save the DataFrame as an Excel file
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=".xlsx"
    ) as temp_excel:
        df.to_excel(temp_excel.name, index=False)
        excel_path = temp_excel.name

    # Provide a download link for the Excel file with the same name as the input
    with open(excel_path, "rb") as excel_file:
        st.download_button(
            label="Download Processed Excel File",
            data=excel_file,
            file_name=f"{input_filename}_processed.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
