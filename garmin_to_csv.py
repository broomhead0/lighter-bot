#!/usr/bin/env python3
"""
Garmin FIT to CSV Converter

Extracts data from Garmin .fit files contained in zip archives and combines
them into a single CSV file. Handles multiple zip files and nested directory structures.

Usage:
    python garmin_to_csv.py <zip_file_or_directory> [output.csv]

Example:
    python garmin_to_csv.py daily_data.zip garmin_data.csv
    python garmin_to_csv.py ./zip_files/ all_data.csv
"""

import os
import sys
import zipfile
import csv
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict

try:
    from fitparse import FitFile
except ImportError:
    print("Error: fitparse library not found. Install it with: pip install fitparse")
    sys.exit(1)


def extract_zip(zip_path: str, extract_to: str) -> List[str]:
    """Extract zip file and return list of all .fit file paths."""
    fit_files = []

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

        # Find all .fit files in extracted directory
        for root, dirs, files in os.walk(extract_to):
            for file in files:
                if file.lower().endswith('.fit'):
                    fit_files.append(os.path.join(root, file))

    return fit_files


def parse_fit_file(fit_path: str, date_directory: str = None) -> List[Dict[str, Any]]:
    """Parse a .fit file and extract all data records."""
    records = []

    try:
        fitfile = FitFile(fit_path)

        # Extract date from directory name if available
        source_info = {'source_file': os.path.basename(fit_path)}
        if date_directory:
            source_info['date_directory'] = os.path.basename(date_directory)

        # Extract data from ALL message types
        # Process all messages in the file (not just specific types)
        for message in fitfile.get_messages():
            message_data = source_info.copy()
            message_data['message_type'] = message.name if hasattr(message, 'name') else 'unknown'

            for data in message:
                if data.value is not None:
                    # Handle different data types
                    if isinstance(data.value, (int, float, str, bool)):
                        message_data[data.name] = data.value
                    elif isinstance(data.value, (list, tuple)):
                        # Convert lists/tuples to comma-separated string
                        message_data[data.name] = ','.join(str(v) for v in data.value)
                    else:
                        # Convert complex types to string
                        message_data[data.name] = str(data.value)

            # Only add if we got some actual data (beyond just source info)
            if len(message_data) > len(source_info):
                records.append(message_data)

    except Exception as e:
        print(f"Warning: Error parsing {fit_path}: {e}", file=sys.stderr)

    return records


def find_fit_files(directory: str) -> List[str]:
    """Recursively find all .fit files in a directory."""
    fit_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.lower().endswith('.fit'):
                fit_files.append(os.path.join(root, file))
    return fit_files


def process_zip_files(input_path: str) -> List[Dict[str, Any]]:
    """Process zip file(s) or directory/ies and extract all FIT data."""
    all_records = []

    # Determine if input is a file or directory
    if os.path.isfile(input_path):
        # Single zip file
        zip_files = [input_path]
        is_zip = True
    elif os.path.isdir(input_path):
        # Check if directory contains subdirectories (prioritize these over zip files)
        items = os.listdir(input_path)
        subdirs = [os.path.join(input_path, d) for d in items if os.path.isdir(os.path.join(input_path, d))]
        zip_files = [os.path.join(input_path, f) for f in items if f.lower().endswith('.zip')]

        if subdirs:
            # Directory contains subdirectories - process those (likely date directories)
            is_zip = False
            directories_to_process = subdirs
        elif zip_files:
            # Directory contains zip files but no subdirectories
            is_zip = True
        else:
            # Directory might contain .fit files directly
            is_zip = False
            directories_to_process = [input_path]
    else:
        print(f"Error: {input_path} is not a valid file or directory", file=sys.stderr)
        return []

    if is_zip:
        # Process zip files
        if not zip_files:
            print(f"Error: No zip files found in {input_path}", file=sys.stderr)
            return []

        # Create temporary directory for extraction
        with tempfile.TemporaryDirectory() as temp_dir:
            for zip_file in zip_files:
                print(f"Processing {zip_file}...")

                try:
                    # Extract zip file
                    fit_files = extract_zip(zip_file, temp_dir)

                    if not fit_files:
                        print(f"  Warning: No .fit files found in {zip_file}", file=sys.stderr)
                        continue

                    print(f"  Found {len(fit_files)} .fit file(s)")

                    # Parse each .fit file
                    for fit_file in fit_files:
                        records = parse_fit_file(fit_file)
                        all_records.extend(records)
                        print(f"    Extracted {len(records)} records from {os.path.basename(fit_file)}")

                except Exception as e:
                    print(f"  Error processing {zip_file}: {e}", file=sys.stderr)
                    continue
    else:
        # Process directories directly
        for directory in directories_to_process:
            print(f"Processing directory {directory}...")

            try:
                fit_files = find_fit_files(directory)

                if not fit_files:
                    print(f"  Warning: No .fit files found in {directory}", file=sys.stderr)
                    continue

                print(f"  Found {len(fit_files)} .fit file(s)")

                # Parse each .fit file
                for fit_file in fit_files:
                    records = parse_fit_file(fit_file, date_directory=directory)
                    all_records.extend(records)
                    print(f"    Extracted {len(records)} records from {os.path.basename(fit_file)}")

            except Exception as e:
                print(f"  Error processing {directory}: {e}", file=sys.stderr)
                continue

    return all_records


def write_csv(records: List[Dict[str, Any]], output_path: str):
    """Write records to CSV file."""
    if not records:
        print("No data to write to CSV", file=sys.stderr)
        return

    # Collect all unique field names
    fieldnames = set()
    for record in records:
        fieldnames.update(record.keys())

    # Sort fieldnames, but put important fields first if they exist
    fieldnames = sorted(fieldnames)
    priority_fields = ['date_directory', 'source_file', 'message_type', 'timestamp', 'timestamp_1']
    ordered_fieldnames = []
    for field in priority_fields:
        if field in fieldnames:
            ordered_fieldnames.append(field)
            fieldnames.remove(field)
    ordered_fieldnames.extend(sorted(fieldnames))

    # Write CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=ordered_fieldnames)
        writer.writeheader()

        for record in records:
            # Ensure all fields are present (fill missing with empty string)
            row = {field: record.get(field, '') for field in ordered_fieldnames}
            writer.writerow(row)

    print(f"\nSuccessfully wrote {len(records)} records to {output_path}")
    print(f"CSV contains {len(ordered_fieldnames)} columns")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else 'garmin_data.csv'

    if not os.path.exists(input_path):
        print(f"Error: {input_path} does not exist", file=sys.stderr)
        sys.exit(1)

    print(f"Processing Garmin data from: {input_path}")
    print(f"Output will be written to: {output_path}\n")

    # Process all zip files and extract data
    all_records = process_zip_files(input_path)

    if all_records:
        write_csv(all_records, output_path)
    else:
        print("No data extracted. Please check your input files.", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

