#!/usr/bin/env python3
"""
Script to create madd rules tables and insert data into uloom_quran.db
"""

import sqlite3
import json
from pathlib import Path

def main():
    # Connect to database
    db_path = Path('/home/hesham-haroun/Quran/db/uloom_quran.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create madd types table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS madd_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name_arabic TEXT NOT NULL UNIQUE,
        name_english TEXT NOT NULL,
        alternate_names TEXT,
        definition_arabic TEXT,
        definition_english TEXT,
        ruling TEXT,
        min_length INTEGER,
        max_length INTEGER,
        fixed_length INTEGER,
        examples TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Create madd subtypes table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS madd_subtypes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        madd_type_id INTEGER NOT NULL,
        name_arabic TEXT NOT NULL,
        name_english TEXT,
        definition_arabic TEXT,
        definition_english TEXT,
        examples TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (madd_type_id) REFERENCES madd_types(id)
    )
    ''')

    # Create qiraa madd rules table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS qiraa_madd_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        qari_id INTEGER NOT NULL,
        rawi_id INTEGER,
        madd_type_id INTEGER NOT NULL,
        min_length INTEGER,
        max_length INTEGER,
        preferred_length INTEGER,
        has_khilaf INTEGER DEFAULT 0,
        has_qasr INTEGER DEFAULT 0,
        qasr_only INTEGER DEFAULT 0,
        description_arabic TEXT,
        description_english TEXT,
        tariq TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (qari_id) REFERENCES qurra(id),
        FOREIGN KEY (rawi_id) REFERENCES ruwat(id),
        FOREIGN KEY (madd_type_id) REFERENCES madd_types(id)
    )
    ''')

    # Create madd ranks table for madd munfasil
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS madd_munfasil_ranks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rank_number INTEGER NOT NULL,
        name_arabic TEXT NOT NULL,
        name_english TEXT,
        length_harakat INTEGER NOT NULL,
        readers TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Insert madd types
    madd_types_data = [
        ('المد المتصل', 'Connected Elongation (Madd Muttasil)',
         '["المد الواجب المتصل", "مد التمكين"]',
         'ان ياتي بعد حرف المد همزة في كلمة واحدة',
         'When a madd letter (alif, waw, ya) is followed by a hamza in the same word',
         'واجب', 4, 6, None,
         '[{"word": "السماء", "verse": "2:22"}, {"word": "جاء", "verse": "110:1"}, {"word": "سوء", "verse": "4:123"}]',
         None),

        ('المد المنفصل', 'Separated Elongation (Madd Munfasil)',
         '["المد الجائز المنفصل", "مد الفصل"]',
         'ان ياتي حرف المد في اخر الكلمة وتاتي الهمزة في اول الكلمة التالية',
         'When a madd letter at the end of a word is followed by a hamza at the beginning of the next word',
         'جائز', 2, 6, None,
         '[{"word": "يا ايها", "verse": "4:1"}, {"word": "انا انزلناه", "verse": "97:1"}]',
         None),

        ('المد العارض للسكون', 'Temporary Sukun Elongation (Madd Arid Lil-Sukun)',
         '["المد الجائز العارض للسكون"]',
         'ان ياتي بعد حرف المد حرف متحرك في اخر الكلمة ثم يسكن لاجل الوقف',
         'When a madd letter is followed by a letter that becomes sukun due to stopping',
         'جائز', 2, 6, None,
         '[{"word": "العالمين", "verse": "1:2"}, {"word": "نستعين", "verse": "1:5"}, {"word": "الرحيم", "verse": "1:3"}]',
         'Applies only when stopping (waqf) at the end of a word'),

        ('المد اللازم', 'Obligatory Elongation (Madd Lazim)',
         '["مد الاشباع"]',
         'ان ياتي بعد حرف المد حرف ساكن سكونا اصليا في الكلمة نفسها',
         'When a madd letter is followed by an original sukun or shadda in the same word',
         'لازم', 6, 6, 6,
         '[{"word": "الضالين", "verse": "1:7"}, {"word": "الطامة", "verse": "79:34"}, {"word": "الصاخة", "verse": "80:33"}]',
         'All readers agree on 6 harakat'),

        ('مد البدل', 'Substitution Elongation (Madd Badal)',
         '["مد البدل"]',
         'ان تتقدم الهمزة على حرف المد في كلمة واحدة',
         'When a hamza is followed by a madd letter (the hamza comes first)',
         'جائز', 2, 6, None,
         '[{"word": "آمنوا", "verse": "2:9"}, {"word": "ايمان", "verse": "2:93"}, {"word": "اوتوا", "verse": "2:101"}]',
         'Called badal because the madd letter substitutes for an original hamza')
    ]

    # Check if data already exists
    cursor.execute('SELECT COUNT(*) FROM madd_types')
    if cursor.fetchone()[0] == 0:
        for data in madd_types_data:
            cursor.execute('''
            INSERT INTO madd_types (name_arabic, name_english, alternate_names, definition_arabic,
                                   definition_english, ruling, min_length, max_length, fixed_length,
                                   examples, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', data)
        print("Inserted madd types")
    else:
        print("Madd types already exist, skipping insertion")

    # Get madd type IDs
    cursor.execute('SELECT id, name_arabic FROM madd_types')
    madd_type_ids = {row[1]: row[0] for row in cursor.fetchall()}

    # Insert madd subtypes for Madd Lazim
    madd_lazim_id = madd_type_ids.get('المد اللازم')
    if madd_lazim_id:
        madd_subtypes = [
            (madd_lazim_id, 'المد اللازم الكلمي المثقل', 'Heavy Word-Level Obligatory Elongation',
             'ان ياتي بعد حرف المد حرف ساكن مشدد في كلمة',
             'Madd letter followed by a shadda in a word',
             '[{"word": "الضالين", "verse": "1:7"}, {"word": "الطامة", "verse": "79:34"}]', None),

            (madd_lazim_id, 'المد اللازم الكلمي المخفف', 'Light Word-Level Obligatory Elongation',
             'ان ياتي بعد حرف المد حرف ساكن اصلي بدون تشديد في كلمة',
             'Madd letter followed by sukun without shadda in a word',
             '[{"word": "ءآلآن", "verse": "10:51"}, {"word": "ءآلذكرين", "verse": "6:143"}]',
             'Very rare in the Quran'),

            (madd_lazim_id, 'المد اللازم الحرفي المثقل', 'Heavy Letter-Level Obligatory Elongation',
             'في فواتح السور حين يكون الحرف الاوسط ساكنا ويدغم فيما بعده',
             'In opening letters of surahs when middle letter is sukun and followed by idgham',
             '[{"letter": "لام في الم", "verse": "2:1"}]', None),

            (madd_lazim_id, 'المد اللازم الحرفي المخفف', 'Light Letter-Level Obligatory Elongation',
             'في فواتح السور حين يكون الحرف الاوسط ساكنا بدون ادغام',
             'In opening letters of surahs when middle letter is sukun without idgham',
             '[{"letter": "ن", "verse": "68:1"}, {"letter": "ق", "verse": "50:1"}, {"letter": "ص", "verse": "38:1"}]',
             'Letters collected in: نقص عسلكم')
        ]

        cursor.execute('SELECT COUNT(*) FROM madd_subtypes')
        if cursor.fetchone()[0] == 0:
            for data in madd_subtypes:
                cursor.execute('''
                INSERT INTO madd_subtypes (madd_type_id, name_arabic, name_english, definition_arabic,
                                          definition_english, examples, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', data)
            print("Inserted madd subtypes")
        else:
            print("Madd subtypes already exist, skipping insertion")

    # Insert madd munfasil ranks
    madd_munfasil_ranks = [
        (1, 'الطول', 'Full Elongation (Tul)', 6,
         '["ورش عن نافع", "حمزة"]'),
        (2, 'فويق التوسط', 'Above Middle (Fuwayq al-Tawassut)', 5,
         '["عاصم"]'),
        (3, 'التوسط', 'Middle (Tawassut)', 4,
         '["ابن عامر", "الكسائي", "خلف العاشر", "حفص (الشاطبية)", "قالون (بخلف)"]'),
        (4, 'فويق القصر', 'Above Shortening (Fuwayq al-Qasr)', 3,
         '["قالون (بخلف)", "الدوري عن ابو عمرو (بخلف)", "يعقوب (بخلف)"]'),
        (5, 'القصر', 'Shortening (Qasr)', 2,
         '["ابن كثير", "السوسي عن ابو عمرو", "ابو جعفر", "يعقوب"]')
    ]

    cursor.execute('SELECT COUNT(*) FROM madd_munfasil_ranks')
    if cursor.fetchone()[0] == 0:
        for data in madd_munfasil_ranks:
            cursor.execute('''
            INSERT INTO madd_munfasil_ranks (rank_number, name_arabic, name_english, length_harakat, readers)
            VALUES (?, ?, ?, ?, ?)
            ''', data)
        print("Inserted madd munfasil ranks")
    else:
        print("Madd munfasil ranks already exist, skipping insertion")

    # Get qari IDs from existing table
    cursor.execute('SELECT id, name_arabic FROM qurra')
    qari_rows = cursor.fetchall()
    qari_ids = {}
    for row in qari_rows:
        qari_ids[row[1]] = row[0]
        # Also add simplified names
        if 'نافع' in row[1]:
            qari_ids['نافع'] = row[0]
        elif 'كثير' in row[1]:
            qari_ids['ابن كثير'] = row[0]
        elif 'عمرو' in row[1]:
            qari_ids['ابو عمرو'] = row[0]
        elif 'عامر' in row[1]:
            qari_ids['ابن عامر'] = row[0]
        elif 'عاصم' in row[1]:
            qari_ids['عاصم'] = row[0]
        elif 'حمزة' in row[1]:
            qari_ids['حمزة'] = row[0]
        elif 'الكسائي' in row[1]:
            qari_ids['الكسائي'] = row[0]
        elif 'أبو جعفر' in row[1] or 'جعفر' in row[1]:
            qari_ids['ابو جعفر'] = row[0]
        elif 'يعقوب' in row[1]:
            qari_ids['يعقوب'] = row[0]
        elif 'خلف' in row[1] and 'هشام' in row[1]:
            qari_ids['خلف العاشر'] = row[0]

    # Get rawi IDs
    cursor.execute('SELECT id, name_arabic, qari_id FROM ruwat')
    rawi_rows = cursor.fetchall()
    rawi_ids = {}
    for row in rawi_rows:
        rawi_ids[(row[1], row[2])] = row[0]
        # Simple name mapping
        rawi_ids[row[1]] = row[0]

    # Insert qiraa madd rules
    cursor.execute('SELECT COUNT(*) FROM qiraa_madd_rules')
    if cursor.fetchone()[0] == 0:
        madd_rules_data = []

        # Nafi - Qalun
        nafi_id = qari_ids.get('نافع', 1)
        qalun_id = rawi_ids.get('قالون')
        warsh_id = rawi_ids.get('ورش')

        muttasil_id = madd_type_ids['المد المتصل']
        munfasil_id = madd_type_ids['المد المنفصل']
        arid_id = madd_type_ids['المد العارض للسكون']
        lazim_id = madd_type_ids['المد اللازم']
        badal_id = madd_type_ids['مد البدل']

        # Qalun rules
        if qalun_id:
            madd_rules_data.extend([
                (nafi_id, qalun_id, muttasil_id, 4, 5, 4, 0, 0, 0,
                 'يمد المتصل اربع او خمس حركات والتوسط اولى',
                 'Elongates connected madd 4-5 counts, with 4 being preferred', None, None),
                (nafi_id, qalun_id, munfasil_id, 2, 4, 2, 1, 1, 0,
                 'له القصر والتوسط في المنفصل والقصر اولى',
                 'Has shortening (2) and middle (4) options, with shortening preferred', None, None),
                (nafi_id, qalun_id, arid_id, 2, 6, None, 0, 0, 0,
                 'له الثلاثة: القصر والتوسط والاشباع',
                 'All three lengths permissible', None, None),
                (nafi_id, qalun_id, lazim_id, 6, 6, 6, 0, 0, 0,
                 'ست حركات لزوما', '6 counts obligatory', None, None),
                (nafi_id, qalun_id, badal_id, 2, 2, 2, 0, 0, 1,
                 'القصر فقط حركتان', 'Only 2 counts (like natural madd)', None, None),
            ])

        # Warsh rules
        if warsh_id:
            madd_rules_data.extend([
                (nafi_id, warsh_id, muttasil_id, 6, 6, 6, 0, 0, 0,
                 'يشبع المتصل ست حركات', 'Full elongation of 6 counts', 'طريق الازرق', None),
                (nafi_id, warsh_id, munfasil_id, 6, 6, 6, 0, 0, 0,
                 'يشبع المنفصل ست حركات كالمتصل',
                 'Full elongation of 6 counts like connected madd', 'طريق الازرق', None),
                (nafi_id, warsh_id, arid_id, 2, 6, None, 0, 0, 0,
                 'له الثلاثة مع ملاحظة تناسب المدود',
                 'All three with consideration of madd proportionality', 'طريق الازرق', None),
                (nafi_id, warsh_id, lazim_id, 6, 6, 6, 0, 0, 0,
                 'ست حركات لزوما', '6 counts obligatory', None, None),
                (nafi_id, warsh_id, badal_id, 2, 6, 6, 0, 0, 0,
                 'له الاوجه الثلاثة: القصر والتوسط والاشباع من طريق الازرق',
                 'All three options via Al-Azraq: 2, 4, or 6 counts', 'طريق الازرق', None),
            ])

        # Ibn Kathir rules
        ibn_kathir_id = qari_ids.get('ابن كثير', 2)
        madd_rules_data.extend([
            (ibn_kathir_id, None, muttasil_id, 4, 5, 4, 0, 0, 0,
             'يمد المتصل اربع او خمس حركات', '4-5 counts for connected madd', None, None),
            (ibn_kathir_id, None, munfasil_id, 2, 2, 2, 0, 1, 1,
             'القصر فقط حركتان بلا خلاف', 'Only shortening (2 counts) without dispute', None, None),
            (ibn_kathir_id, None, arid_id, 2, 6, None, 0, 0, 0,
             'له الثلاثة', 'All three lengths permissible', None, None),
            (ibn_kathir_id, None, lazim_id, 6, 6, 6, 0, 0, 0,
             'ست حركات لزوما', '6 counts obligatory', None, None),
            (ibn_kathir_id, None, badal_id, 2, 2, 2, 0, 0, 1,
             'القصر فقط حركتان', 'Only 2 counts', None, None),
        ])

        # Abu Amr - Al-Duri
        abu_amr_id = qari_ids.get('ابو عمرو', 3)
        duri_id = rawi_ids.get('الدوري')
        susi_id = rawi_ids.get('السوسي')

        if duri_id:
            madd_rules_data.extend([
                (abu_amr_id, duri_id, muttasil_id, 4, 5, 4, 0, 0, 0,
                 'يمد المتصل اربع او خمس حركات', '4-5 counts for connected madd', None, None),
                (abu_amr_id, duri_id, munfasil_id, 2, 4, None, 1, 1, 0,
                 'له القصر وفويق القصر والتوسط بخلف عنه',
                 'Has 2, 3, or 4 counts with variation', None, None),
                (abu_amr_id, duri_id, arid_id, 2, 6, None, 0, 0, 0,
                 'له الثلاثة', 'All three lengths permissible', None, None),
                (abu_amr_id, duri_id, lazim_id, 6, 6, 6, 0, 0, 0,
                 'ست حركات لزوما', '6 counts obligatory', None, None),
                (abu_amr_id, duri_id, badal_id, 2, 2, 2, 0, 0, 1,
                 'القصر فقط حركتان', 'Only 2 counts', None, None),
            ])

        # Abu Amr - Al-Susi
        if susi_id:
            madd_rules_data.extend([
                (abu_amr_id, susi_id, muttasil_id, 4, 5, 4, 0, 0, 0,
                 'يمد المتصل اربع او خمس حركات', '4-5 counts for connected madd', None, None),
                (abu_amr_id, susi_id, munfasil_id, 2, 2, 2, 0, 1, 1,
                 'القصر فقط بلا خلاف', 'Only shortening (2 counts) without dispute', None, None),
                (abu_amr_id, susi_id, arid_id, 2, 6, None, 0, 0, 0,
                 'له الثلاثة', 'All three lengths permissible', None, None),
                (abu_amr_id, susi_id, lazim_id, 6, 6, 6, 0, 0, 0,
                 'ست حركات لزوما', '6 counts obligatory', None, None),
                (abu_amr_id, susi_id, badal_id, 2, 2, 2, 0, 0, 1,
                 'القصر فقط حركتان', 'Only 2 counts', None, None),
            ])

        # Ibn Amir rules
        ibn_amir_id = qari_ids.get('ابن عامر', 4)
        madd_rules_data.extend([
            (ibn_amir_id, None, muttasil_id, 4, 5, None, 0, 0, 0,
             'يمد المتصل اربع او خمس حركات', '4-5 counts for connected madd', None, None),
            (ibn_amir_id, None, munfasil_id, 4, 4, 4, 0, 0, 0,
             'التوسط اربع حركات', 'Middle length of 4 counts', None, None),
            (ibn_amir_id, None, arid_id, 2, 6, None, 0, 0, 0,
             'له الثلاثة', 'All three lengths permissible', None, None),
            (ibn_amir_id, None, lazim_id, 6, 6, 6, 0, 0, 0,
             'ست حركات لزوما', '6 counts obligatory', None, None),
            (ibn_amir_id, None, badal_id, 2, 2, 2, 0, 0, 1,
             'القصر فقط حركتان', 'Only 2 counts', None, None),
        ])

        # Asim - Shuba and Hafs
        asim_id = qari_ids.get('عاصم', 5)
        shuba_id = rawi_ids.get('شعبة')
        hafs_id = rawi_ids.get('حفص')

        if shuba_id:
            madd_rules_data.extend([
                (asim_id, shuba_id, muttasil_id, 4, 5, None, 0, 0, 0,
                 'يمد المتصل اربع او خمس حركات', '4-5 counts for connected madd', None, None),
                (asim_id, shuba_id, munfasil_id, 4, 5, None, 0, 0, 0,
                 'فويق التوسط اربع او خمس حركات', 'Above middle: 4-5 counts', None, None),
                (asim_id, shuba_id, arid_id, 2, 6, None, 0, 0, 0,
                 'له الثلاثة', 'All three lengths permissible', None, None),
                (asim_id, shuba_id, lazim_id, 6, 6, 6, 0, 0, 0,
                 'ست حركات لزوما', '6 counts obligatory', None, None),
                (asim_id, shuba_id, badal_id, 2, 2, 2, 0, 0, 1,
                 'القصر فقط حركتان', 'Only 2 counts', None, None),
            ])

        if hafs_id:
            madd_rules_data.extend([
                (asim_id, hafs_id, muttasil_id, 4, 5, 4, 0, 0, 0,
                 'من طريق الشاطبية يمد اربع او خمس حركات ومن طريق الطيبة يجوز ست حركات',
                 'Via Shatibiyyah: 4-5 counts; via Tayyibah: up to 6 counts', 'الشاطبية', None),
                (asim_id, hafs_id, munfasil_id, 4, 5, 4, 0, 0, 0,
                 'من طريق الشاطبية يمد اربع او خمس حركات ومن طريق الطيبة له مراتب متعددة',
                 'Via Shatibiyyah: 4-5 counts; via Tayyibah: multiple options including qasr', 'الشاطبية', None),
                (asim_id, hafs_id, arid_id, 2, 6, None, 0, 0, 0,
                 'له الثلاثة: القصر والتوسط والطول', 'All three lengths: 2, 4, or 6 counts', None, None),
                (asim_id, hafs_id, lazim_id, 6, 6, 6, 0, 0, 0,
                 'ست حركات لزوما بالاجماع', '6 counts obligatory by consensus', None, None),
                (asim_id, hafs_id, badal_id, 2, 2, 2, 0, 0, 1,
                 'القصر فقط حركتان كالمد الطبيعي', 'Only 2 counts like natural madd', None, None),
            ])

        # Hamza rules
        hamza_id = qari_ids.get('حمزة', 6)
        madd_rules_data.extend([
            (hamza_id, None, muttasil_id, 6, 6, 6, 0, 0, 0,
             'يشبع المتصل ست حركات', 'Full elongation of 6 counts', None, None),
            (hamza_id, None, munfasil_id, 6, 6, 6, 0, 0, 0,
             'يشبع المنفصل ست حركات كالمتصل',
             'Full elongation of 6 counts like connected madd', None, None),
            (hamza_id, None, arid_id, 2, 6, None, 0, 0, 0,
             'له الثلاثة', 'All three lengths permissible', None, None),
            (hamza_id, None, lazim_id, 6, 6, 6, 0, 0, 0,
             'ست حركات لزوما', '6 counts obligatory', None, None),
            (hamza_id, None, badal_id, 2, 2, 2, 0, 0, 1,
             'القصر فقط حركتان', 'Only 2 counts', None, None),
        ])

        # Al-Kisai rules
        kisai_id = qari_ids.get('الكسائي', 7)
        madd_rules_data.extend([
            (kisai_id, None, muttasil_id, 4, 5, None, 0, 0, 0,
             'يمد المتصل اربع او خمس حركات', '4-5 counts for connected madd', None, None),
            (kisai_id, None, munfasil_id, 4, 4, 4, 0, 0, 0,
             'التوسط اربع حركات', 'Middle length of 4 counts', None, None),
            (kisai_id, None, arid_id, 2, 6, None, 0, 0, 0,
             'له الثلاثة', 'All three lengths permissible', None, None),
            (kisai_id, None, lazim_id, 6, 6, 6, 0, 0, 0,
             'ست حركات لزوما', '6 counts obligatory', None, None),
            (kisai_id, None, badal_id, 2, 2, 2, 0, 0, 1,
             'القصر فقط حركتان', 'Only 2 counts', None, None),
        ])

        # Abu Jafar rules
        abu_jafar_id = qari_ids.get('ابو جعفر', 8)
        madd_rules_data.extend([
            (abu_jafar_id, None, muttasil_id, 4, 5, None, 0, 0, 0,
             'يمد المتصل اربع او خمس حركات', '4-5 counts for connected madd', None, None),
            (abu_jafar_id, None, munfasil_id, 2, 2, 2, 0, 1, 1,
             'القصر فقط بلا خلاف', 'Only shortening (2 counts) without dispute', None, None),
            (abu_jafar_id, None, arid_id, 2, 6, None, 0, 0, 0,
             'له الثلاثة', 'All three lengths permissible', None, None),
            (abu_jafar_id, None, lazim_id, 6, 6, 6, 0, 0, 0,
             'ست حركات لزوما', '6 counts obligatory', None, None),
            (abu_jafar_id, None, badal_id, 2, 2, 2, 0, 0, 1,
             'القصر فقط حركتان', 'Only 2 counts', None, None),
        ])

        # Yaqub rules
        yaqub_id = qari_ids.get('يعقوب', 9)
        madd_rules_data.extend([
            (yaqub_id, None, muttasil_id, 4, 5, None, 0, 0, 0,
             'يمد المتصل اربع او خمس حركات', '4-5 counts for connected madd', None, None),
            (yaqub_id, None, munfasil_id, 2, 4, None, 1, 1, 0,
             'له القصر وفويق القصر والتوسط', 'Has 2, 3, or 4 counts', None, None),
            (yaqub_id, None, arid_id, 2, 6, None, 0, 0, 0,
             'له الثلاثة', 'All three lengths permissible', None, None),
            (yaqub_id, None, lazim_id, 6, 6, 6, 0, 0, 0,
             'ست حركات لزوما', '6 counts obligatory', None, None),
            (yaqub_id, None, badal_id, 2, 2, 2, 0, 0, 1,
             'القصر فقط حركتان', 'Only 2 counts', None, None),
        ])

        # Khalaf al-Ashir rules
        khalaf_id = qari_ids.get('خلف العاشر', 10)
        madd_rules_data.extend([
            (khalaf_id, None, muttasil_id, 4, 5, None, 0, 0, 0,
             'يمد المتصل اربع او خمس حركات', '4-5 counts for connected madd', None, None),
            (khalaf_id, None, munfasil_id, 4, 4, 4, 0, 0, 0,
             'التوسط اربع حركات فقط', 'Middle length of 4 counts only', None, None),
            (khalaf_id, None, arid_id, 2, 6, None, 0, 0, 0,
             'له الثلاثة', 'All three lengths permissible', None, None),
            (khalaf_id, None, lazim_id, 6, 6, 6, 0, 0, 0,
             'ست حركات لزوما', '6 counts obligatory', None, None),
            (khalaf_id, None, badal_id, 2, 2, 2, 0, 0, 1,
             'القصر فقط حركتان', 'Only 2 counts', None, None),
        ])

        for data in madd_rules_data:
            cursor.execute('''
            INSERT INTO qiraa_madd_rules (qari_id, rawi_id, madd_type_id, min_length, max_length,
                                         preferred_length, has_khilaf, has_qasr, qasr_only,
                                         description_arabic, description_english, tariq, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', data)

        print(f"Inserted {len(madd_rules_data)} qiraa madd rules")
    else:
        print("Qiraa madd rules already exist, skipping insertion")

    # Create indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_madd_rules_qari ON qiraa_madd_rules(qari_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_madd_rules_type ON qiraa_madd_rules(madd_type_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_madd_subtypes_type ON madd_subtypes(madd_type_id)')

    # Create view for easy querying
    cursor.execute('''
    CREATE VIEW IF NOT EXISTS v_qiraa_madd_rules AS
    SELECT
        qmr.id,
        q.name_arabic as qari_name,
        r.name_arabic as rawi_name,
        mt.name_arabic as madd_type,
        mt.name_english as madd_type_english,
        qmr.min_length,
        qmr.max_length,
        qmr.preferred_length,
        qmr.has_khilaf,
        qmr.has_qasr,
        qmr.qasr_only,
        qmr.description_arabic,
        qmr.description_english,
        qmr.tariq
    FROM qiraa_madd_rules qmr
    JOIN qurra q ON qmr.qari_id = q.id
    LEFT JOIN ruwat r ON qmr.rawi_id = r.id
    JOIN madd_types mt ON qmr.madd_type_id = mt.id
    ''')

    conn.commit()
    print("Database updated successfully!")

    # Print summary
    cursor.execute('SELECT COUNT(*) FROM madd_types')
    print(f"Total madd types: {cursor.fetchone()[0]}")

    cursor.execute('SELECT COUNT(*) FROM madd_subtypes')
    print(f"Total madd subtypes: {cursor.fetchone()[0]}")

    cursor.execute('SELECT COUNT(*) FROM qiraa_madd_rules')
    print(f"Total qiraa madd rules: {cursor.fetchone()[0]}")

    cursor.execute('SELECT COUNT(*) FROM madd_munfasil_ranks')
    print(f"Total madd munfasil ranks: {cursor.fetchone()[0]}")

    conn.close()

if __name__ == '__main__':
    main()
