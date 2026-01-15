#!/usr/bin/env python3
"""
Script to insert idgham rules into the uloom_quran database.
Creates necessary tables and populates them with data from idgham_rules.json
"""

import json
import sqlite3
from pathlib import Path

# Paths
BASE_DIR = Path("/home/hesham-haroun/Quran")
JSON_FILE = BASE_DIR / "data/processed/idgham_rules.json"
DB_FILE = BASE_DIR / "db/uloom_quran.db"


def create_idgham_tables(conn):
    """Create tables for idgham rules if they don't exist."""
    cursor = conn.cursor()

    # Table for idgham types (kabir, saghir, mutamathlain, etc.)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS idgham_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_arabic TEXT NOT NULL,
            name_english TEXT,
            definition TEXT,
            definition_english TEXT,
            condition TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table for letter groups in idgham (e.g., natiyah, lathawiyah, etc.)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS idgham_letter_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            idgham_type_id INTEGER,
            group_name TEXT NOT NULL,
            letters TEXT NOT NULL,  -- JSON array of letters
            examples TEXT,  -- JSON array of examples
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (idgham_type_id) REFERENCES idgham_types(id)
        )
    """)

    # Main table for qiraat-specific idgham rules
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS qiraat_idgham_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            qari_id INTEGER NOT NULL,
            rawi_id INTEGER,  -- NULL if applies to all transmitters
            rawi_name TEXT,  -- For convenience
            idgham_type TEXT NOT NULL,  -- kabir, saghir, noon_tanween, etc.
            rule_name TEXT NOT NULL,
            rule_description TEXT,
            letters TEXT,  -- JSON array of applicable letters
            ruling TEXT,  -- idgham, izhar, etc.
            examples TEXT,  -- JSON array of examples
            exceptions TEXT,  -- JSON array of exceptions
            notes TEXT,
            with_khilaf INTEGER DEFAULT 0,  -- Has difference of opinion
            is_primary INTEGER DEFAULT 1,  -- Primary rule vs secondary
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (qari_id) REFERENCES qurra(id)
        )
    """)

    # Table for idgham kabir specific examples
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS idgham_kabir_examples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id INTEGER NOT NULL,
            original_text TEXT NOT NULL,
            reading_text TEXT NOT NULL,
            idgham_subtype TEXT,  -- mutamathlain, mutaqaribain, mutajanisain
            verse_reference TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (rule_id) REFERENCES qiraat_idgham_rules(id)
        )
    """)

    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_idgham_rules_qari ON qiraat_idgham_rules(qari_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_idgham_rules_type ON qiraat_idgham_rules(idgham_type)")

    conn.commit()
    print("Idgham tables created successfully.")


def insert_idgham_types(conn, data):
    """Insert idgham type definitions."""
    cursor = conn.cursor()

    types = data.get("idgham_types", {})

    for type_key, type_data in types.items():
        cursor.execute("""
            INSERT OR REPLACE INTO idgham_types
            (name_arabic, name_english, definition, definition_english, condition)
            VALUES (?, ?, ?, ?, ?)
        """, (
            type_data.get("name_arabic"),
            type_data.get("name_english"),
            type_data.get("definition"),
            type_data.get("definition_english"),
            type_data.get("condition")
        ))

        type_id = cursor.lastrowid

        # Insert letter groups if present
        letter_groups = type_data.get("letter_groups", [])
        for group in letter_groups:
            cursor.execute("""
                INSERT INTO idgham_letter_groups
                (idgham_type_id, group_name, letters, examples)
                VALUES (?, ?, ?, ?)
            """, (
                type_id,
                group.get("group_name"),
                json.dumps(group.get("letters", []), ensure_ascii=False),
                json.dumps(group.get("examples", []), ensure_ascii=False)
            ))

    conn.commit()
    print(f"Inserted {len(types)} idgham types.")


def insert_qiraat_rules(conn, data):
    """Insert qiraat-specific idgham rules."""
    cursor = conn.cursor()

    qiraat_rules = data.get("qiraat_rules", {})
    total_rules = 0
    total_examples = 0

    for qari_key, qari_data in qiraat_rules.items():
        qari_id = qari_data.get("qari_id")
        qari_name = qari_data.get("name_arabic")

        idgham = qari_data.get("idgham_rules", {})

        # Process idgham kabir
        kabir = idgham.get("idgham_kabir", {})
        if kabir.get("applies"):
            # Insert main kabir rule
            cursor.execute("""
                INSERT INTO qiraat_idgham_rules
                (qari_id, idgham_type, rule_name, rule_description, notes, with_khilaf, is_primary)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                qari_id,
                "kabir",
                "الإدغام الكبير",
                kabir.get("description", kabir.get("note", "")),
                kabir.get("notes", ""),
                1 if kabir.get("with_khilaf") else 0,
                1
            ))
            kabir_rule_id = cursor.lastrowid
            total_rules += 1

            # Process Soosi-specific rules if present
            soosi = kabir.get("soosi_rules", {})
            if soosi:
                for type_info in soosi.get("types", []):
                    for example in type_info.get("examples", []):
                        cursor.execute("""
                            INSERT INTO idgham_kabir_examples
                            (rule_id, original_text, reading_text, idgham_subtype, notes)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            kabir_rule_id,
                            example.get("text", ""),
                            example.get("reading", ""),
                            type_info.get("type", ""),
                            example.get("note", "")
                        ))
                        total_examples += 1

        # Process idgham saghir
        saghir = idgham.get("idgham_saghir", {})
        if saghir.get("applies"):
            for rule in saghir.get("rules", []):
                cursor.execute("""
                    INSERT INTO qiraat_idgham_rules
                    (qari_id, idgham_type, rule_name, rule_description, letters, ruling, examples, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    qari_id,
                    "saghir",
                    rule.get("rule", ""),
                    rule.get("rule", ""),
                    json.dumps(rule.get("letters", []), ensure_ascii=False),
                    rule.get("ruling", ""),
                    json.dumps(rule.get("examples", []), ensure_ascii=False),
                    rule.get("note", "")
                ))
                total_rules += 1

            # Warsh-specific rules
            warsh = saghir.get("warsh_specific")
            if warsh:
                cursor.execute("""
                    INSERT INTO qiraat_idgham_rules
                    (qari_id, rawi_name, idgham_type, rule_name, rule_description, examples, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    qari_id,
                    "ورش",
                    "saghir",
                    warsh.get("rule", "خاص بورش"),
                    warsh.get("rule", ""),
                    json.dumps(warsh.get("examples", []), ensure_ascii=False),
                    warsh.get("note", "")
                ))
                total_rules += 1

            # Hisham-specific rules
            hisham_rules = saghir.get("hisham_rules", [])
            for rule in hisham_rules:
                cursor.execute("""
                    INSERT INTO qiraat_idgham_rules
                    (qari_id, rawi_name, idgham_type, rule_name, rule_description, letters, ruling, examples, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    qari_id,
                    "هشام",
                    "saghir",
                    rule.get("rule", ""),
                    rule.get("rule", ""),
                    json.dumps(rule.get("letters", []), ensure_ascii=False),
                    rule.get("ruling", ""),
                    json.dumps(rule.get("examples", []), ensure_ascii=False),
                    rule.get("note", "")
                ))
                total_rules += 1

        # Process idgham noon and tanween
        noon_tanween = idgham.get("idgham_noon_tanween", {})
        if noon_tanween:
            cursor.execute("""
                INSERT INTO qiraat_idgham_rules
                (qari_id, idgham_type, rule_name, rule_description, letters, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                qari_id,
                "noon_tanween",
                "إدغام النون الساكنة والتنوين",
                "حروف يرملون",
                json.dumps(noon_tanween.get("yarmaloon_letters", []), ensure_ascii=False),
                f"بغنة: {noon_tanween.get('with_ghunnah', [])}, بدون غنة: {noon_tanween.get('without_ghunnah', [])}"
            ))
            total_rules += 1

            # Specific rawi rules
            for specific_key in ["hafs_specific", "warsh_exception", "khalaf_specific"]:
                specific = noon_tanween.get(specific_key)
                if specific:
                    cursor.execute("""
                        INSERT INTO qiraat_idgham_rules
                        (qari_id, rawi_name, idgham_type, rule_name, rule_description, notes)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        qari_id,
                        specific_key.replace("_specific", "").replace("_exception", "").title(),
                        "noon_tanween",
                        specific.get("rule", ""),
                        specific.get("rule", ""),
                        specific.get("note", "")
                    ))
                    total_rules += 1

        # Process idgham mutamathlain
        mutamathlain = idgham.get("idgham_mutamathlain", {})
        if mutamathlain:
            cursor.execute("""
                INSERT INTO qiraat_idgham_rules
                (qari_id, idgham_type, rule_name, rule_description, examples)
                VALUES (?, ?, ?, ?, ?)
            """, (
                qari_id,
                "mutamathlain",
                "إدغام المتماثلين",
                mutamathlain.get("rule", ""),
                json.dumps(mutamathlain.get("examples", []), ensure_ascii=False)
            ))
            total_rules += 1

        # Process idgham mutajanisain
        mutajanisain = idgham.get("idgham_mutajanisain", {})
        if mutajanisain:
            examples = mutajanisain.get("examples", [])
            cursor.execute("""
                INSERT INTO qiraat_idgham_rules
                (qari_id, idgham_type, rule_name, rule_description, examples)
                VALUES (?, ?, ?, ?, ?)
            """, (
                qari_id,
                "mutajanisain",
                "إدغام المتجانسين",
                mutajanisain.get("rule", ""),
                json.dumps(examples, ensure_ascii=False)
            ))
            total_rules += 1

        print(f"  Processed: {qari_name}")

    conn.commit()
    print(f"Inserted {total_rules} idgham rules and {total_examples} examples.")


def insert_comparative_summary(conn, data):
    """Insert comparative summary data."""
    cursor = conn.cursor()

    summary = data.get("comparative_summary", {})

    # Create a summary table if needed
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS idgham_comparative_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            summary_type TEXT NOT NULL,
            description TEXT,
            data TEXT NOT NULL,  -- JSON object
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insert kabir readers summary
    kabir_readers = summary.get("idgham_kabir_readers", [])
    if kabir_readers:
        cursor.execute("""
            INSERT INTO idgham_comparative_summary (summary_type, description, data)
            VALUES (?, ?, ?)
        """, (
            "idgham_kabir_readers",
            "القراء الذين يقرأون بالإدغام الكبير",
            json.dumps(kabir_readers, ensure_ascii=False)
        ))

    # Insert idh table
    idh_table = summary.get("idgham_idh_table", {})
    if idh_table:
        cursor.execute("""
            INSERT INTO idgham_comparative_summary (summary_type, description, data)
            VALUES (?, ?, ?)
        """, (
            "idgham_idh",
            idh_table.get("description", ""),
            json.dumps(idh_table, ensure_ascii=False)
        ))

    # Insert qad table
    qad_table = summary.get("idgham_qad_table", {})
    if qad_table:
        cursor.execute("""
            INSERT INTO idgham_comparative_summary (summary_type, description, data)
            VALUES (?, ?, ?)
        """, (
            "idgham_qad",
            qad_table.get("description", ""),
            json.dumps(qad_table, ensure_ascii=False)
        ))

    # Insert ta tanith table
    ta_table = summary.get("idgham_ta_tanith_table", {})
    if ta_table:
        cursor.execute("""
            INSERT INTO idgham_comparative_summary (summary_type, description, data)
            VALUES (?, ?, ?)
        """, (
            "idgham_ta_tanith",
            ta_table.get("description", ""),
            json.dumps(ta_table, ensure_ascii=False)
        ))

    conn.commit()
    print("Inserted comparative summary data.")


def main():
    """Main function to run the script."""
    print("=" * 60)
    print("Inserting Idgham Rules into uloom_quran.db")
    print("=" * 60)

    # Load JSON data
    print(f"\nLoading data from: {JSON_FILE}")
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Loaded data with {len(data.get('qiraat_rules', {}))} qiraat entries.")

    # Connect to database
    print(f"\nConnecting to database: {DB_FILE}")
    conn = sqlite3.connect(DB_FILE)

    try:
        # Create tables
        print("\nCreating idgham tables...")
        create_idgham_tables(conn)

        # Insert data
        print("\nInserting idgham types...")
        insert_idgham_types(conn, data)

        print("\nInserting qiraat-specific rules...")
        insert_qiraat_rules(conn, data)

        print("\nInserting comparative summary...")
        insert_comparative_summary(conn, data)

        print("\n" + "=" * 60)
        print("SUCCESS: All idgham rules inserted into database!")
        print("=" * 60)

        # Verify insertion
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM idgham_types")
        type_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM qiraat_idgham_rules")
        rule_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM idgham_kabir_examples")
        example_count = cursor.fetchone()[0]

        print(f"\nDatabase summary:")
        print(f"  - Idgham types: {type_count}")
        print(f"  - Qiraat rules: {rule_count}")
        print(f"  - Kabir examples: {example_count}")

    except Exception as e:
        print(f"\nERROR: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
