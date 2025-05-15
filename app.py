import re
import pandas as pd
import pdfplumber
import tempfile
import streamlit as st
from io import BytesIO
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# If a time goes over 60 seconds we start getting MM:SS:MS formats that we need to be numeric
# Helper function to convert time to seconds
def time_to_seconds(time_str):
    if ":" in time_str:
        # Handle minute:second.millisecond format
        minutes, seconds = time_str.split(":")
        return int(minutes) * 60 + float(seconds)
    else:
        # Handle second.millisecond format
        return float(time_str)

# Helper function to process each athlete's runs
def process_athlete_runs(data, athlete_info, run_data, race_counter):
    athlete_no = athlete_info['No']
    
    # Initialize counter for new athletes
    if athlete_no not in race_counter:
        race_counter[athlete_no] = 0

    for run in run_data:
        # Increment counter for each individual run
        race_counter[athlete_no] += 1
        race_number = race_counter[athlete_no]
        
        main_times = run[0::2]
        bracket_numbers = run[:-1][1::2]
        combined_run = []
        for main_time, bracket_number in zip(main_times[:-1], bracket_numbers):
            combined_run.append(main_time)
            combined_run.append(bracket_number)
        combined_run.append(run[-1])
        data.append([athlete_info['No'], athlete_info['Nat'], athlete_info['Name'], race_number] + combined_run)

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
st.set_page_config(layout='wide')
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
    athlete_info = None  # Changed to None initially
    run_data = []
    race_counter = {}

    # Regex patterns
    athlete_pattern = r'(\d+)\s+([A-Z]{3})\s+([A-Za-z\s]+)'
    run_pattern = r'([\d:]+\.\d+)\s+\((\d+)\)\s+([\d:]+\.\d+)\s+\((\d+)\)\s+([\d:]+\.\d+)\s+\((\d+)\)\s+([\d:]+\.\d+)\s+\((\d+)\)\s+([\d:]+\.\d+)\s+\((\d+)\)\s+([\d:]+\.\d+)\s+\((\d+)\)\s+([\d:]+\.\d+)'


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
            # Process previous athlete's data if exists
            if athlete_info and run_data:
                process_athlete_runs(data, athlete_info, run_data, race_counter)
            
            # Store new athlete info
            athlete_info = {
                'No': athlete_match.group(1),
                'Nat': athlete_match.group(2),
                'Name': athlete_match.group(3).strip()
            }
            # Clear run data for new athlete
            run_data = []

        run_match = re.findall(run_pattern, line)
        if run_match:
            run_data.append(run_match[0])

    # Process the last athlete's data
    if athlete_info and run_data:
        process_athlete_runs(data, athlete_info, run_data, race_counter)

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

    # Normalize time columns to seconds
    for col in ["split_1", "split_2", "split_3", "split_4", "split_5", "finish_time"]:
        df[col] = df[col].apply(time_to_seconds)

    # Calculate split differences for the entire dataset
    df_process = calculate_split_differences(df)

    # Save both DataFrames to Excel
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        with pd.ExcelWriter(tmp.name, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Original Data', index=False)
            df_process.to_excel(writer, sheet_name='Processed Data', index=False)

        # Download link
        st.download_button(
            label="Download Excel file",
            data=BytesIO(tmp.read()),
            file_name=f"{input_filename}-Processed.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    if not df.empty:
        unique_names = df['Name'].unique()

        # User selection inputs with columns
        col1, col2 = st.columns(2)
        with col1:
            selected_racer = st.selectbox("Select a racer to focus on:", unique_names)
        with col2:
            racer_races = df[df['Name'] == selected_racer]['Race'].unique()
            selected_race = st.selectbox("Select a race for the selected racer:", racer_races)
        
        col3, col4 = st.columns(2)
        with col3:
            comparison_racer = st.selectbox("Select a racer to compare against:", unique_names)
        with col4:
            comparison_racer_races = df[df['Name'] == comparison_racer]['Race'].unique()
            selected_comparison_race = st.selectbox("Select a race for the comparison racer:", comparison_racer_races)

        # Filter data for selected pair
        selected_df = df[(df['Name'] == selected_racer) & (df['Race'] == selected_race)]
        comparison_df = df[(df['Name'] == comparison_racer) & (df['Race'] == selected_comparison_race)]

        # Calculate split differences for selected pair
        df_pair = pd.concat([selected_df, comparison_df])
        df_pair_processed = calculate_split_differences(df_pair)

        # Extract split times for plotting
        splits = [f'split_{i}' for i in range(6)]
        selected_splits = df_pair_processed[df_pair_processed['Name'] == selected_racer][splits].values.flatten()
        comparison_splits = df_pair_processed[df_pair_processed['Name'] == comparison_racer][splits].values.flatten()

        # Calculate percentage differences
        percentage_diffs = [(selected - comparison) / comparison * 100 if comparison != 0 else 0
                            for selected, comparison in zip(selected_splits, comparison_splits)]

                # Define bar colors based on percentage difference
        bar_colors = ['green' if diff < 0 else 'red' for diff in percentage_diffs]

        # Create subplots for separate line and bar charts
        fig = make_subplots(rows=2, cols=1, 
                            shared_xaxes=True, 
                            vertical_spacing=0.1,
                            subplot_titles=("Percentage Difference", f"{selected_racer} vs {comparison_racer} - Race Comparison"))
        
        # Add bar chart for percentage differences
        fig.add_trace(
            go.Bar(x=splits, 
                   y=percentage_diffs, 
                   name='Percentage Difference', 
                   marker_color=bar_colors),
            row=1, col=1
        )
        
        # Add line charts for selected and comparison racers
        fig.add_trace(
            go.Scatter(x=splits, 
                       y=selected_splits, 
                       mode='lines+markers', 
                       name=f'{selected_racer} (Race {selected_race})', 
                       line=dict(color='yellow')),
            row=2, col=1
        )
        
        fig.add_trace(
            go.Scatter(x=splits, 
                       y=comparison_splits, 
                       mode='lines+markers', 
                       name=f'{comparison_racer} (Race {selected_comparison_race})', 
                       line=dict(color='blue')),
            row=2, col=1
        )
        
        # Update layout for the subplots
        fig.update_layout(
            height=1000,  # Increase vertical size
            width=1400,
            title_text=f"{selected_racer}-{selected_race} vs {comparison_racer}-{selected_comparison_race} - Race Comparison",
            showlegend=True,
            legend=dict(x=1.05, y=1),  # Move legend to the far right
            margin=dict(l=50, r=50, t=50, b=50)
        )
        
        # Update axes titles separately
        fig.update_xaxes(title_text="Splits", row=1, col=1)
        fig.update_xaxes(title_text="Splits", row=2, col=1)
        fig.update_yaxes(title_text="Percentage Difference (%)", row=1, col=1)
        fig.update_yaxes(title_text="Time (seconds)", row=2, col=1)

        # Display Plotly chart
        with st.container():
            st.plotly_chart(fig, use_container_width=True)
