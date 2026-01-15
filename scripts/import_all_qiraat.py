#!/usr/bin/env python3
"""
Master Import Script for all القراءات (Qiraat) Data

This script imports qiraat data from multiple sources:
1. KFGQPC (King Fahd Glorious Quran Printing Complex) - 8 riwayat
2. QuranJSON - 6 riwayat in text format
3. quran-meta - 7 riwayat with validated JSON data
4. quran-tajweed - Tajweed annotations for Hafs

All data is imported into the uloom_quran.db database.
"""

import sqlite3
import os
import subprocess
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'db', 'uloom_quran.db')
SCRIPTS_DIR = os.path.join(BASE_DIR, 'scripts')

# Required repositories
REPOS = {
    'quran-data-kfgqpc': 'https://github.com/thetruetruth/quran-data-kfgqpc.git',
    'QuranJSON': 'https://github.com/Ishaksmail/QuranJSON.git',
    'quran-meta': 'https://github.com/quran-center/quran-meta.git',
    'quran-tajweed': 'https://github.com/cpfair/quran-tajweed.git',
}


def check_and_clone_repos():
    """Check if required repositories exist, clone if missing"""
    raw_data_dir = os.path.join(BASE_DIR, 'data', 'raw')

    for repo_name, repo_url in REPOS.items():
        repo_path = os.path.join(raw_data_dir, repo_name)
        if not os.path.exists(repo_path):
            print(f"Cloning {repo_name}...")
            try:
                subprocess.run(['git', 'clone', '--depth', '1', repo_url, repo_path],
                               check=True, capture_output=True)
                print(f"  Successfully cloned {repo_name}")
            except subprocess.CalledProcessError as e:
                print(f"  Failed to clone {repo_name}: {e}")
        else:
            print(f"Repository {repo_name} already exists")


def run_import_script(script_name):
    """Run an import script"""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    if not os.path.exists(script_path):
        print(f"Script not found: {script_path}")
        return False

    print(f"\n{'='*60}")
    print(f"Running {script_name}")
    print('='*60)

    try:
        result = subprocess.run([sys.executable, script_path],
                                capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("Errors:", result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"Error running {script_name}: {e}")
        return False


def print_database_summary():
    """Print summary of all qiraat data in database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n" + "=" * 70)
    print("DATABASE SUMMARY - All Qiraat Data")
    print("=" * 70)

    # Count riwayat
    cursor.execute("SELECT COUNT(*) FROM riwayat")
    riwayat_count = cursor.fetchone()[0]
    print(f"\nTotal Riwayat (Narrations): {riwayat_count}")

    # List all riwayat with verse counts
    print("\nRiwayat Details:")
    print("-" * 70)
    cursor.execute("""
        SELECT r.code, r.name_arabic, r.name_english, r.source,
               COUNT(qt.id) as verse_count
        FROM riwayat r
        LEFT JOIN qiraat_texts qt ON qt.riwaya_id = r.id
        GROUP BY r.id
        ORDER BY r.source, r.code
    """)
    current_source = None
    for row in cursor.fetchall():
        if current_source != row[3]:
            current_source = row[3]
            print(f"\n  Source: {current_source or 'Unknown'}")
        print(f"    {row[1]} ({row[0]}): {row[4]:,} verses")

    # Qiraat differences
    cursor.execute("SELECT COUNT(*) FROM qiraat_differences")
    diff_count = cursor.fetchone()[0]
    print(f"\n\nQiraat Differences Found: {diff_count:,}")

    # Tajweed annotations
    try:
        cursor.execute("SELECT COUNT(*) FROM tajweed_annotations")
        tajweed_count = cursor.fetchone()[0]
        print(f"Tajweed Annotations: {tajweed_count:,}")

        cursor.execute("SELECT COUNT(DISTINCT rule_code) FROM tajweed_annotations")
        rule_count = cursor.fetchone()[0]
        print(f"Unique Tajweed Rules: {rule_count}")
    except:
        print("Tajweed Annotations: Not imported yet")

    # Total qiraat texts
    cursor.execute("SELECT COUNT(*) FROM qiraat_texts")
    total_texts = cursor.fetchone()[0]
    print(f"\nTotal Qiraat Text Entries: {total_texts:,}")

    conn.close()

    print("\n" + "=" * 70)


def main():
    print("=" * 70)
    print("MASTER QIRAAT IMPORT SCRIPT")
    print("Importing all قراءات data from multiple sources")
    print("=" * 70)

    # Step 1: Check and clone repositories
    print("\n[Step 1] Checking repositories...")
    check_and_clone_repos()

    # Step 2: Run KFGQPC import
    print("\n[Step 2] Importing KFGQPC data...")
    run_import_script('import_qiraat_kfgqpc.py')

    # Step 3: Run quran-meta import
    print("\n[Step 3] Importing quran-meta data...")
    run_import_script('import_quran_meta_riwayat.py')

    # Step 4: Run QuranJSON import (if script exists)
    print("\n[Step 4] Importing QuranJSON data...")
    run_import_script('import_quranjson_qiraat.py')

    # Step 5: Run Tajweed import
    print("\n[Step 5] Importing Tajweed annotations...")
    run_import_script('import_tajweed.py')

    # Step 6: Print summary
    print("\n[Step 6] Generating summary...")
    print_database_summary()

    print("\n" + "=" * 70)
    print("ALL QIRAAT IMPORTS COMPLETE!")
    print("=" * 70)


if __name__ == "__main__":
    main()
