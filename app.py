import re
import pandas as pd
import pdfplumber
import tempfile
import streamlit as st
from io import BytesIO

# Helper function to process each athlete's runs
def process_athlete_runs(data, athlete_info, run_data, race_number):
    athlete_key = f"{athlete_info['No']}_{athlete_info['Nat']}_{athlete_info['Name']}"
    if athlete_key not in race_counter:
        race_counter[athlete_key] = 1
    else:
        race_counter[athlete_key] += 1
    race_number = race_counter[athlete_key]

    for run in run_data:
        main_times = run[0::2]
        bracket_numbers = run[:-1][1::2]
        combined_run = []
        for main_time, bracket_number in zip(main_times[:-1], bracket_numbers):
            combined_run.append(main_time)
            combined_run.append(bracket_number)
        combined_run.append(run[-1])
        data.append([athlete_info['No'], athlete_info['Nat'], athlete_info['Name'], race_number] + combined_run)
    return race_counter

# Calculate split differences for df_process
def calculate_split_differences(df):
    df_processed_list = []
    for (name, race), group in df.groupby(['Name', 'Race']):
        split_times = [0] + [float(group[f'split_{i}'].values[0]) for i in range(1, 6)] + [float(group['finish_time'].values[0])]
        split_diffs = [split_times[i] - split_times[i - 1] for i in range(1, len(split_times))]
        df_processed_list.append([
            group['No'].values[0],
            group['Nat'].values[0],
            group['Name'].values[0],
            group['Race'].values[0],
            *split_diffs,
            group['finish_time'].values[0],
            group['finish_time_bracket'].values[0],
            group['top_speed_kmh'].values[0]
        ])
    columns = [
        "No", "Nat", "Name", "Race",
        "split_0", "split_1", "split_2", "split_3", "split_4", "split_5",
        "finish_time", "Place", "top_speed_kmh"
    ]
    return pd.DataFrame(df_processed_list, columns=columns)

# Streamlit setup
st.title("Single File PDF Processor")
st.write("Upload a PDF file, and this app will extract and process the data into an Excel file for download.")

# Single file uploader
uploaded_file = st.file_uploader("Choose a PDF file", type="pdf", accept_multiple_files=False)

if uploaded_file:
    input_filename = uploaded_file.name.rsplit('.', 1)[0]

    # Save the uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
        temp_pdf.write(uploaded_file.read())
        pdf_path = temp_pdf.name

    # Initialize data storage
    data = []
    athlete_info = {}
    run_data = []
    race_counter = {}

    # Regex patterns
    athlete_pattern = r'(\d+)\s+([A-Z]{3})\s+([A-Za-z\s]+)'
    run_pattern = r'([\d\.]+)\s+\((\d+)\)\s+([\d\.]+)\s+\((\d+)\)\s+([\d\.]+)\s+\((\d+)\)\s+([\d\.]+)\s+\((\d+)\)\s+([\d\.]+)\s+\((\d+)\)\s+([\d\.]+)\s+\((\d+)\)\s+([\d\.]+)'

    # Extract data from PDF
    with pdfplumber.open(pdf_path) as pdf:
        text_data = ""
        for page in pdf.pages:
            text_data += page.extract_text()

    # Process each line
    for line in text_data.splitlines():
        if 'DNS' in line:
            continue

        athlete_match = re.match(athlete_pattern, line)
        if athlete_match:
            if athlete_info and run_data:
        athlete_key = f"{athlete_info['No']}_{athlete_info['Nat']}_{athlete_info['Name']}"
        if athlete_key not in race_counter:
            race_counter[athlete_key] = 1
        else:
            race_counter[athlete_key] += 1
        process_athlete_runs(data, athlete_info, run_data, race_counter[athlete_key])
            
            athlete_info = {
                'No': athlete_match.group(1),
                'Nat': athlete_match.group(2),
                'Name': athlete_match.group(3).strip()
            }
            run_data = []

        run_match = re.findall(run_pattern, line)
        if run_match:
            run_data.append(run_match[0])

    if athlete_info and run_data:
        athlete_key = f"{athlete_info['No']}_{athlete_info['Nat']}_{athlete_info['Name']}"
        if athlete_key not in race_counter:
            race_counter[athlete_key] = 1
        else:
            race_counter[athlete_key] += 1
        process_athlete_runs(data, athlete_info, run_data, race_counter[athlete_key])

    # DataFrame columns
    columns = [
        "No", "Nat", "Name", "Race",
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

    # User selection inputs
    unique_names = df['Name'].unique()
    selected_racer = st.selectbox("Select a racer to focus on:", unique_names)
    comparison_racers = st.multiselect("Select one or more racers to compare against:", unique_names, default=[name for name in unique_names if name != selected_racer])

    # Create df_process based on user selections
    df_selected = df[df['Name'].isin([selected_racer] + comparison_racers)]
    df_process = calculate_split_differences(df_selected)

    # Save both DataFrames to an Excel file with two sheets
    excel_data = BytesIO()
    with pd.ExcelWriter(excel_data, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="raw", index=False)
        df_process.to_excel(writer, sheet_name="processed", index=False)
    excel_data.seek(0)

    # Download button for the processed file
    st.download_button(
        label="Download Processed Excel File",
        data=excel_data,
        file_name=f"{input_filename}_processed.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
