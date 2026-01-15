#!/usr/bin/env python3
"""
Insert Hamza Rules into uloom_quran.db
This script populates the qiraat_usul table with comprehensive hamza handling rules
for each of the ten qurra (readers).
"""

import sqlite3
import json
from pathlib import Path

DB_PATH = Path("/home/hesham-haroun/Quran/db/uloom_quran.db")
JSON_PATH = Path("/home/hesham-haroun/Quran/data/processed/hamza_rules.json")

def get_qari_id(cursor, name_arabic):
    """Get qari ID by Arabic name pattern."""
    cursor.execute("SELECT id FROM qurra WHERE name_arabic LIKE ?", (f"%{name_arabic}%",))
    result = cursor.fetchone()
    return result[0] if result else None

def insert_hamza_rules(conn, cursor):
    """Insert hamza rules as usul entries."""

    # Load JSON data
    with open(JSON_PATH, 'r', encoding='utf-8') as f:
        data = json.load(json)

    # Mapping of JSON keys to qari names
    qari_mapping = {
        'nafi': 'نافع',
        'ibn_kathir': 'ابن كثير',
        'abu_amr': 'أبو عمرو',
        'ibn_amir': 'ابن عامر',
        'asim': 'عاصم',
        'hamza': 'حمزة',
        'kisai': 'الكسائي',
        'abu_jafar': 'أبو جعفر',
        'yaqub': 'يعقوب',
        'khalaf_ashir': 'خلف'
    }

    rules_inserted = 0

    for qari_key, qari_name in qari_mapping.items():
        qari_id = get_qari_id(cursor, qari_name)
        if not qari_id:
            print(f"Warning: Could not find qari: {qari_name}")
            continue

        qari_rules = data.get('qiraat_rules', {}).get(qari_key, {})
        if not qari_rules:
            continue

        # Extract and insert rules for each category
        rules_to_insert = []

        # 1. Hamz Mufrad (Single Hamza) rules
        hamz_mufrad = qari_rules.get('hamz_mufrad', {})
        if hamz_mufrad:
            rules_to_insert.append({
                'rule_name': 'الهمز المفرد',
                'rule_description': json.dumps(hamz_mufrad, ensure_ascii=False, indent=2),
                'examples': json.dumps(extract_examples(hamz_mufrad), ensure_ascii=False)
            })

        # 2. Hamzatan min Kalima (Two hamzas in one word)
        hamzatan_kalima = qari_rules.get('hamzatan_min_kalima', {})
        if hamzatan_kalima:
            rules_to_insert.append({
                'rule_name': 'الهمزتان من كلمة',
                'rule_description': json.dumps(hamzatan_kalima, ensure_ascii=False, indent=2),
                'examples': json.dumps(extract_examples(hamzatan_kalima), ensure_ascii=False)
            })

        # 3. Hamzatan min Kalimatain (Two hamzas from two words)
        hamzatan_kalimatain = qari_rules.get('hamzatan_min_kalimatain', {})
        if hamzatan_kalimatain:
            rules_to_insert.append({
                'rule_name': 'الهمزتان من كلمتين',
                'rule_description': json.dumps(hamzatan_kalimatain, ensure_ascii=False, indent=2),
                'examples': json.dumps(extract_examples(hamzatan_kalimatain), ensure_ascii=False)
            })

        # 4. Waqf ala Hamz (Stopping on hamza) - if applicable
        if 'waqf' in str(hamz_mufrad) or qari_key in ['hamza', 'khalaf_ashir']:
            waqf_rules = hamz_mufrad.get('waqf', {})
            if waqf_rules:
                rules_to_insert.append({
                    'rule_name': 'الوقف على الهمز',
                    'rule_description': json.dumps(waqf_rules, ensure_ascii=False, indent=2),
                    'examples': json.dumps(extract_examples(waqf_rules), ensure_ascii=False)
                })

        # 5. Naql (Transfer) rules - if applicable
        if qari_key == 'nafi':
            warsh_rules = qari_rules.get('ruwat', {}).get('warsh', {})
            naql = warsh_rules.get('hamz_mufrad', {}).get('naql', {})
            if naql:
                rules_to_insert.append({
                    'rule_name': 'نقل حركة الهمز (ورش)',
                    'rule_description': json.dumps(naql, ensure_ascii=False, indent=2),
                    'examples': json.dumps(naql.get('examples', []), ensure_ascii=False)
                })

        # 6. Sakt rules - if applicable
        sakt_rules = qari_rules.get('sakt_rules', {})
        if sakt_rules:
            rules_to_insert.append({
                'rule_name': 'السكت على الهمز',
                'rule_description': json.dumps(sakt_rules, ensure_ascii=False, indent=2),
                'examples': json.dumps([], ensure_ascii=False)
            })

        # Insert rules into database
        for rule in rules_to_insert:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO qiraat_usul (qari_id, rule_name, rule_description, examples)
                    VALUES (?, ?, ?, ?)
                """, (qari_id, rule['rule_name'], rule['rule_description'], rule['examples']))
                rules_inserted += 1
            except sqlite3.Error as e:
                print(f"Error inserting rule for {qari_name}: {e}")

    conn.commit()
    return rules_inserted

def extract_examples(data):
    """Recursively extract examples from nested data structure."""
    examples = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key == 'examples':
                if isinstance(value, list):
                    examples.extend(value)
                elif isinstance(value, dict):
                    for k, v in value.items():
                        if isinstance(v, list):
                            examples.extend(v)
                else:
                    examples.append(str(value))
            elif isinstance(value, (dict, list)):
                examples.extend(extract_examples(value))
    elif isinstance(data, list):
        for item in data:
            examples.extend(extract_examples(item))
    return examples

def create_hamza_rules_table(cursor):
    """Create a dedicated hamza rules table if needed."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hamza_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            qari_id INTEGER NOT NULL,
            rawi_id INTEGER,
            category TEXT NOT NULL,
            subcategory TEXT,
            rule_type TEXT NOT NULL,
            rule_arabic TEXT,
            rule_english TEXT,
            description_arabic TEXT,
            description_english TEXT,
            examples TEXT,
            exceptions TEXT,
            applies_in TEXT DEFAULT 'wasl_and_waqf',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (qari_id) REFERENCES qurra(id),
            FOREIGN KEY (rawi_id) REFERENCES ruwat(id)
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_hamza_rules_qari ON hamza_rules(qari_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_hamza_rules_category ON hamza_rules(category)
    """)

def insert_detailed_hamza_rules(conn, cursor):
    """Insert detailed hamza rules into dedicated table."""

    # Define detailed rules for each qari
    detailed_rules = [
        # Nafi - Qalun
        {
            'qari_id': 1,
            'rawi_name': 'قالون',
            'rules': [
                {
                    'category': 'hamz_mufrad',
                    'subcategory': 'sakin_fa_kalima',
                    'rule_type': 'tahqiq',
                    'rule_arabic': 'تحقيق الهمز الساكن',
                    'rule_english': 'Full articulation of quiescent hamza',
                    'description_arabic': 'يحقق قالون الهمزة الساكنة الواقعة فاء الكلمة',
                    'exceptions': json.dumps([{'word': 'رِئْيًا', 'location': '19:74', 'rule': 'إبدال ياء مع الإدغام'}], ensure_ascii=False)
                },
                {
                    'category': 'hamzatan_min_kalima',
                    'subcategory': 'muttafiqatan_fath',
                    'rule_type': 'tashil_with_idkhal',
                    'rule_arabic': 'تسهيل الثانية مع الإدخال',
                    'rule_english': 'Soften second hamza with alif insertion',
                    'description_arabic': 'يسهل قالون الهمزة الثانية بين الهمزة والألف مع إدخال ألف بينهما',
                    'examples': json.dumps(['أَأَنذرتهم', 'أَأَنت', 'أَأَسلمتم'], ensure_ascii=False)
                },
                {
                    'category': 'hamzatan_min_kalimatain',
                    'subcategory': 'muttafiqatan_fath',
                    'rule_type': 'isqat_first',
                    'rule_arabic': 'إسقاط الأولى',
                    'rule_english': 'Drop first hamza',
                    'description_arabic': 'يسقط قالون الهمزة الأولى من المفتوحتين مع القصر والمد',
                    'examples': json.dumps(['جاءَ أَمرنا'], ensure_ascii=False)
                }
            ]
        },
        # Nafi - Warsh
        {
            'qari_id': 1,
            'rawi_name': 'ورش',
            'rules': [
                {
                    'category': 'hamz_mufrad',
                    'subcategory': 'sakin_fa_kalima',
                    'rule_type': 'ibdal',
                    'rule_arabic': 'إبدال الهمز الساكن',
                    'rule_english': 'Replace quiescent hamza with vowel letter',
                    'description_arabic': 'يبدل ورش الهمزة الساكنة الواقعة فاء الكلمة حرف مد من جنس حركة ما قبلها',
                    'examples': json.dumps(['المُومنون', 'يَاتون', 'تَالمون'], ensure_ascii=False),
                    'exceptions': json.dumps({
                        'bab_al_iwaa': ['المَأْوى', 'مَأْواهم', 'مَأْواكم', 'فَأْووا', 'تُؤْوي', 'تُؤْويه', 'مَأْواه']
                    }, ensure_ascii=False)
                },
                {
                    'category': 'hamz_mufrad',
                    'subcategory': 'naql',
                    'rule_type': 'naql',
                    'rule_arabic': 'نقل حركة الهمزة',
                    'rule_english': 'Transfer hamza vowel to preceding consonant',
                    'description_arabic': 'ينقل ورش حركة الهمزة إلى الساكن قبلها وصلاً ووقفاً',
                    'examples': json.dumps(['قَدِ افْلح', 'مَنِ امَن'], ensure_ascii=False),
                    'applies_in': 'wasl_and_waqf'
                },
                {
                    'category': 'hamzatan_min_kalima',
                    'subcategory': 'muttafiqatan_fath',
                    'rule_type': 'tashil_or_ibdal',
                    'rule_arabic': 'تسهيل أو إبدال الثانية',
                    'rule_english': 'Soften or replace second hamza',
                    'description_arabic': 'لورش في الهمزتين المفتوحتين من كلمة وجهان: تسهيل الثانية أو إبدالها ألفاً مع المد',
                    'examples': json.dumps(['أَأَنذرتهم'], ensure_ascii=False)
                }
            ]
        },
        # Ibn Kathir
        {
            'qari_id': 2,
            'rawi_name': None,
            'rules': [
                {
                    'category': 'hamz_mufrad',
                    'subcategory': 'general',
                    'rule_type': 'tahqiq',
                    'rule_arabic': 'تحقيق الهمز',
                    'rule_english': 'Full articulation of hamza',
                    'description_arabic': 'يحقق ابن كثير الهمز المفرد ساكناً ومتحركاً',
                    'examples': json.dumps(['ضِئْزى'], ensure_ascii=False),
                    'notes': 'انفرد ابن كثير بقراءة ضيزى بالهمز'
                },
                {
                    'category': 'hamzatan_min_kalima',
                    'subcategory': 'general',
                    'rule_type': 'tashil_without_idkhal',
                    'rule_arabic': 'تسهيل الثانية بلا إدخال',
                    'rule_english': 'Soften second without insertion',
                    'description_arabic': 'يسهل ابن كثير الهمزة الثانية من غير إدخال ألف بينهما'
                },
                {
                    'category': 'hamzatan_min_kalimatain',
                    'subcategory': 'muttafiqatan',
                    'rule_type': 'tashil_or_ibdal_second',
                    'rule_arabic': 'تسهيل أو إبدال الثانية',
                    'rule_english': 'Soften or replace second hamza',
                    'description_arabic': 'يسهل أو يبدل ابن كثير الهمزة الثانية من كلمتين'
                }
            ]
        },
        # Abu Amr
        {
            'qari_id': 3,
            'rawi_name': None,
            'rules': [
                {
                    'category': 'hamz_mufrad',
                    'subcategory': 'general',
                    'rule_type': 'tahqiq',
                    'rule_arabic': 'تحقيق الهمز',
                    'rule_english': 'Full articulation',
                    'description_arabic': 'يحقق أبو عمرو الهمز المفرد'
                },
                {
                    'category': 'hamzatan_min_kalima',
                    'subcategory': 'general',
                    'rule_type': 'tashil_with_idkhal',
                    'rule_arabic': 'تسهيل الثانية مع الإدخال',
                    'rule_english': 'Soften second with insertion',
                    'description_arabic': 'يسهل أبو عمرو الهمزة الثانية من كلمة مع إدخال ألف بينهما'
                },
                {
                    'category': 'hamzatan_min_kalimatain',
                    'subcategory': 'muttafiqatan',
                    'rule_type': 'isqat_first',
                    'rule_arabic': 'إسقاط الأولى',
                    'rule_english': 'Drop first hamza',
                    'description_arabic': 'يسقط أبو عمرو الهمزة الأولى من الهمزتين المتفقتين من كلمتين',
                    'notes': 'اشتهر أبو عمرو بإسقاط إحدى الهمزتين المتلاقيتين'
                }
            ]
        },
        # Ibn Amir - Hisham
        {
            'qari_id': 4,
            'rawi_name': 'هشام',
            'rules': [
                {
                    'category': 'hamz_mufrad',
                    'subcategory': 'general',
                    'rule_type': 'tahqiq',
                    'rule_arabic': 'تحقيق الهمز',
                    'rule_english': 'Full articulation',
                    'description_arabic': 'يحقق هشام الهمز المفرد'
                },
                {
                    'category': 'hamzatan_min_kalima',
                    'subcategory': 'muttafiqatan_fath',
                    'rule_type': 'tahqiq_with_options',
                    'rule_arabic': 'تحقيق مع خيارات الإدخال',
                    'rule_english': 'Full articulation with insertion options',
                    'description_arabic': 'لهشام في الهمزتين من كلمة وجهان: تحقيقهما مع الإدخال وعدمه'
                },
                {
                    'category': 'waqf_ala_hamz',
                    'subcategory': 'mutatarrif',
                    'rule_type': 'takhfif',
                    'rule_arabic': 'تخفيف الهمز المتطرف وقفاً',
                    'rule_english': 'Lighten final hamza when stopping',
                    'description_arabic': 'يوافق هشام حمزة في تخفيف الهمز المتطرف عند الوقف',
                    'applies_in': 'waqf_only',
                    'notes': 'هشام يخفف الهمز المتطرف فقط، لا المتوسط'
                }
            ]
        },
        # Asim
        {
            'qari_id': 5,
            'rawi_name': None,
            'rules': [
                {
                    'category': 'hamz_mufrad',
                    'subcategory': 'general',
                    'rule_type': 'tahqiq',
                    'rule_arabic': 'تحقيق الهمز',
                    'rule_english': 'Full articulation',
                    'description_arabic': 'يحقق عاصم الهمز المفرد مطلقاً'
                },
                {
                    'category': 'hamzatan_min_kalima',
                    'subcategory': 'general',
                    'rule_type': 'tahqiq_both',
                    'rule_arabic': 'تحقيق الهمزتين',
                    'rule_english': 'Full articulation of both',
                    'description_arabic': 'يحقق عاصم الهمزتين من كلمة بلا إدخال'
                },
                {
                    'category': 'hamzatan_min_kalimatain',
                    'subcategory': 'general',
                    'rule_type': 'tahqiq_both',
                    'rule_arabic': 'تحقيق الهمزتين',
                    'rule_english': 'Full articulation of both',
                    'description_arabic': 'يحقق عاصم الهمزتين من كلمتين'
                }
            ]
        },
        # Hamza
        {
            'qari_id': 6,
            'rawi_name': None,
            'rules': [
                {
                    'category': 'hamz_mufrad',
                    'subcategory': 'wasl',
                    'rule_type': 'tahqiq',
                    'rule_arabic': 'تحقيق الهمز وصلاً',
                    'rule_english': 'Full articulation when continuing',
                    'description_arabic': 'يحقق حمزة الهمز المفرد في حال الوصل',
                    'applies_in': 'wasl_only'
                },
                {
                    'category': 'waqf_ala_hamz',
                    'subcategory': 'mutawassit_after_sakin',
                    'rule_type': 'naql',
                    'rule_arabic': 'نقل حركة الهمز',
                    'rule_english': 'Transfer hamza vowel',
                    'description_arabic': 'ينقل حمزة حركة الهمز المتوسط إلى الساكن قبله عند الوقف',
                    'applies_in': 'waqf_only'
                },
                {
                    'category': 'waqf_ala_hamz',
                    'subcategory': 'mutawassit_after_alif',
                    'rule_type': 'tashil_bayna_bayna',
                    'rule_arabic': 'تسهيل بين بين',
                    'rule_english': 'Soften between hamza and vowel letter',
                    'description_arabic': 'يسهل حمزة الهمز المتوسط بعد الألف بين بين مع المد والقصر',
                    'applies_in': 'waqf_only'
                },
                {
                    'category': 'waqf_ala_hamz',
                    'subcategory': 'mutatarrif_sakin',
                    'rule_type': 'ibdal',
                    'rule_arabic': 'إبدال الهمز الساكن المتطرف',
                    'rule_english': 'Replace final quiescent hamza',
                    'description_arabic': 'يبدل حمزة الهمز الساكن المتطرف حرف مد من جنس حركة ما قبله',
                    'applies_in': 'waqf_only',
                    'examples': json.dumps(['اقْرَأْ → اقْرَا', 'يَسْتَهْزِئ → يَسْتَهْزِي'], ensure_ascii=False)
                },
                {
                    'category': 'hamzatan_min_kalima',
                    'subcategory': 'general',
                    'rule_type': 'tahqiq_both',
                    'rule_arabic': 'تحقيق الهمزتين',
                    'rule_english': 'Full articulation of both',
                    'description_arabic': 'يحقق حمزة الهمزتين من كلمة بلا إدخال'
                }
            ]
        },
        # Kisai
        {
            'qari_id': 7,
            'rawi_name': None,
            'rules': [
                {
                    'category': 'hamz_mufrad',
                    'subcategory': 'general',
                    'rule_type': 'tahqiq',
                    'rule_arabic': 'تحقيق الهمز',
                    'rule_english': 'Full articulation',
                    'description_arabic': 'يحقق الكسائي الهمز المفرد مطلقاً'
                },
                {
                    'category': 'hamzatan_min_kalima',
                    'subcategory': 'general',
                    'rule_type': 'tahqiq_both',
                    'rule_arabic': 'تحقيق الهمزتين',
                    'rule_english': 'Full articulation of both',
                    'description_arabic': 'يحقق الكسائي الهمزتين من كلمة بلا إدخال'
                },
                {
                    'category': 'hamzatan_min_kalimatain',
                    'subcategory': 'general',
                    'rule_type': 'tahqiq_both',
                    'rule_arabic': 'تحقيق الهمزتين',
                    'rule_english': 'Full articulation of both',
                    'description_arabic': 'يحقق الكسائي الهمزتين من كلمتين'
                }
            ]
        },
        # Abu Jafar
        {
            'qari_id': 8,
            'rawi_name': None,
            'rules': [
                {
                    'category': 'hamz_mufrad',
                    'subcategory': 'sakin_fa_kalima',
                    'rule_type': 'ibdal',
                    'rule_arabic': 'إبدال الهمز الساكن',
                    'rule_english': 'Replace quiescent hamza',
                    'description_arabic': 'يبدل أبو جعفر الهمزة الساكنة الواقعة فاء الكلمة كورش',
                    'notes': 'يوافق أبو جعفر ورش في إبدال الهمز الساكن'
                },
                {
                    'category': 'hamzatan_min_kalima',
                    'subcategory': 'general',
                    'rule_type': 'tashil_with_idkhal',
                    'rule_arabic': 'تسهيل الثانية مع الإدخال',
                    'rule_english': 'Soften second with insertion',
                    'description_arabic': 'يسهل أبو جعفر الهمزة الثانية من كلمة مع إدخال ألف كقالون'
                },
                {
                    'category': 'hamzatan_min_kalimatain',
                    'subcategory': 'muttafiqatan',
                    'rule_type': 'isqat_first',
                    'rule_arabic': 'إسقاط الأولى',
                    'rule_english': 'Drop first hamza',
                    'description_arabic': 'يسقط أبو جعفر الهمزة الأولى من الهمزتين المتفقتين كأبي عمرو'
                }
            ]
        },
        # Yaqub - Ruways
        {
            'qari_id': 9,
            'rawi_name': 'رويس',
            'rules': [
                {
                    'category': 'hamz_mufrad',
                    'subcategory': 'general',
                    'rule_type': 'tahqiq',
                    'rule_arabic': 'تحقيق الهمز',
                    'rule_english': 'Full articulation',
                    'description_arabic': 'يحقق رويس الهمز المفرد'
                },
                {
                    'category': 'hamzatan_min_kalima',
                    'subcategory': 'general',
                    'rule_type': 'tashil_without_idkhal',
                    'rule_arabic': 'تسهيل الثانية بلا إدخال',
                    'rule_english': 'Soften second without insertion',
                    'description_arabic': 'يسهل رويس الهمزة الثانية من كلمة بلا إدخال كابن كثير'
                },
                {
                    'category': 'hamzatan_min_kalimatain',
                    'subcategory': 'muttafiqatan',
                    'rule_type': 'tashil_or_ibdal_second',
                    'rule_arabic': 'تسهيل أو إبدال الثانية',
                    'rule_english': 'Soften or replace second',
                    'description_arabic': 'يسهل أو يبدل رويس الهمزة الثانية من كلمتين'
                }
            ]
        },
        # Yaqub - Rawh
        {
            'qari_id': 9,
            'rawi_name': 'روح',
            'rules': [
                {
                    'category': 'hamz_mufrad',
                    'subcategory': 'general',
                    'rule_type': 'tahqiq',
                    'rule_arabic': 'تحقيق الهمز',
                    'rule_english': 'Full articulation',
                    'description_arabic': 'يحقق روح الهمز المفرد'
                },
                {
                    'category': 'hamzatan_min_kalima',
                    'subcategory': 'general',
                    'rule_type': 'tahqiq_both',
                    'rule_arabic': 'تحقيق الهمزتين',
                    'rule_english': 'Full articulation of both',
                    'description_arabic': 'يحقق روح الهمزتين من كلمة'
                },
                {
                    'category': 'hamzatan_min_kalimatain',
                    'subcategory': 'general',
                    'rule_type': 'tahqiq_both',
                    'rule_arabic': 'تحقيق الهمزتين',
                    'rule_english': 'Full articulation of both',
                    'description_arabic': 'يحقق روح الهمزتين من كلمتين'
                }
            ]
        },
        # Khalaf al-Ashir
        {
            'qari_id': 10,
            'rawi_name': None,
            'rules': [
                {
                    'category': 'hamz_mufrad',
                    'subcategory': 'wasl',
                    'rule_type': 'tahqiq',
                    'rule_arabic': 'تحقيق الهمز وصلاً',
                    'rule_english': 'Full articulation when continuing',
                    'description_arabic': 'يحقق خلف العاشر الهمز في حال الوصل',
                    'applies_in': 'wasl_only'
                },
                {
                    'category': 'waqf_ala_hamz',
                    'subcategory': 'general',
                    'rule_type': 'takhfif',
                    'rule_arabic': 'تخفيف الهمز وقفاً',
                    'rule_english': 'Lighten hamza when stopping',
                    'description_arabic': 'يخفف خلف العاشر الهمز عند الوقف كحمزة مع بعض الاختلافات',
                    'applies_in': 'waqf_only'
                },
                {
                    'category': 'hamzatan_min_kalima',
                    'subcategory': 'general',
                    'rule_type': 'tahqiq_both',
                    'rule_arabic': 'تحقيق الهمزتين',
                    'rule_english': 'Full articulation of both',
                    'description_arabic': 'يحقق خلف العاشر الهمزتين من كلمة'
                },
                {
                    'category': 'sakt',
                    'subcategory': 'before_hamza',
                    'rule_type': 'no_sakt',
                    'rule_arabic': 'عدم السكت',
                    'rule_english': 'No sakt',
                    'description_arabic': 'لا يسكت خلف العاشر قبل الهمز بخلاف روايته عن حمزة'
                }
            ]
        }
    ]

    rules_inserted = 0

    for qari_data in detailed_rules:
        qari_id = qari_data['qari_id']
        rawi_name = qari_data.get('rawi_name')

        # Get rawi_id if applicable
        rawi_id = None
        if rawi_name:
            cursor.execute(
                "SELECT id FROM ruwat WHERE qari_id = ? AND name_arabic LIKE ?",
                (qari_id, f"%{rawi_name}%")
            )
            result = cursor.fetchone()
            rawi_id = result[0] if result else None

        for rule in qari_data['rules']:
            try:
                cursor.execute("""
                    INSERT INTO hamza_rules (
                        qari_id, rawi_id, category, subcategory, rule_type,
                        rule_arabic, rule_english, description_arabic,
                        examples, exceptions, applies_in, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    qari_id,
                    rawi_id,
                    rule.get('category'),
                    rule.get('subcategory'),
                    rule.get('rule_type'),
                    rule.get('rule_arabic'),
                    rule.get('rule_english'),
                    rule.get('description_arabic'),
                    rule.get('examples', '[]'),
                    rule.get('exceptions', '[]'),
                    rule.get('applies_in', 'wasl_and_waqf'),
                    rule.get('notes')
                ))
                rules_inserted += 1
            except sqlite3.Error as e:
                print(f"Error inserting detailed rule: {e}")

    conn.commit()
    return rules_inserted

def main():
    """Main function to insert hamza rules."""
    print("Connecting to database...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Creating hamza_rules table...")
    create_hamza_rules_table(cursor)

    print("Inserting detailed hamza rules...")
    detailed_count = insert_detailed_hamza_rules(conn, cursor)
    print(f"Inserted {detailed_count} detailed hamza rules")

    # Verify insertion
    cursor.execute("SELECT COUNT(*) FROM hamza_rules")
    total = cursor.fetchone()[0]
    print(f"Total hamza rules in database: {total}")

    # Show sample data
    print("\nSample hamza rules:")
    cursor.execute("""
        SELECT q.name_arabic, hr.category, hr.rule_arabic, hr.description_arabic
        FROM hamza_rules hr
        JOIN qurra q ON hr.qari_id = q.id
        LIMIT 5
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} - {row[2]}")

    conn.close()
    print("\nDone!")

if __name__ == "__main__":
    main()
