#!/usr/bin/env python3
"""
Script to insert tajweed rules into the uloom_quran database.
This populates the qiraat_usul table with tajweed rule differences between qiraat.
"""

import sqlite3
import json
import os

DB_PATH = '/home/hesham-haroun/Quran/db/uloom_quran.db'

def insert_tajweed_rules():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Tajweed rules data to insert into qiraat_usul table
    # Structure: (qari_id, rule_name, rule_description, examples)

    tajweed_rules = [
        # الإمالة (Imalah) rules
        (1, "الإمالة - قالون", "قالون له الفتح مع إمالة في مواضع محدودة جداً", json.dumps(["هار في سورة التوبة"], ensure_ascii=False)),
        (1, "الإمالة - ورش", "ورش يقرأ بالإمالة الصغرى (التقليل/بين بين) في ذوات الياء", json.dumps(["الهدى", "الدنيا", "موسى", "عيسى"], ensure_ascii=False)),
        (2, "الإمالة", "ابن كثير يقرأ بالفتح ولا إمالة عنده", json.dumps([], ensure_ascii=False)),
        (3, "الإمالة", "أبو عمرو له الإمالة الكبرى في مواضع والفتح في أخرى", json.dumps(["طه", "ها من مريم", "را من فواتح السور"], ensure_ascii=False)),
        (4, "الإمالة - ابن ذكوان", "ابن ذكوان يميل في مواضع محدودة", json.dumps(["أدرى", "ذكرى في مواضع"], ensure_ascii=False)),
        (5, "الإمالة - شعبة", "شعبة له الإمالة الكبرى في مواضع", json.dumps(["أدراك", "أدراكم"], ensure_ascii=False)),
        (5, "الإمالة - حفص", "حفص يقرأ بالفتح إلا في كلمة واحدة: مجريها في سورة هود", json.dumps(["مجريها 11:41"], ensure_ascii=False)),
        (6, "الإمالة", "حمزة يقرأ بالإمالة الكبرى في ذوات الياء ورؤوس الآي وغيرها", json.dumps(["الهدى", "النار", "الكفار", "الأبرار"], ensure_ascii=False)),
        (7, "الإمالة", "الكسائي أوسع القراء إمالة، يقرأ بالإمالة الكبرى", json.dumps(["طه", "ها", "را", "يا", "كافة ذوات الياء"], ensure_ascii=False)),
        (8, "الإمالة", "أبو جعفر يقرأ بالفتح ولا إمالة عنده", json.dumps([], ensure_ascii=False)),
        (9, "الإمالة", "يعقوب له الإمالة الكبرى في مواضع", json.dumps(["طه", "ها"], ensure_ascii=False)),
        (10, "الإمالة", "خلف العاشر يقرأ بالإمالة الكبرى كحمزة", json.dumps(["ذوات الياء"], ensure_ascii=False)),

        # المد المنفصل rules
        (1, "المد المنفصل - قالون", "قالون له القصر (حركتان) والتوسط (4 حركات) بخلف عنه", json.dumps({"length_harakat": [2, 4], "has_khilaf": True}, ensure_ascii=False)),
        (1, "المد المنفصل - ورش", "ورش يمد بالإشباع (6 حركات)", json.dumps({"length_harakat": [6], "has_khilaf": False}, ensure_ascii=False)),
        (2, "المد المنفصل", "ابن كثير يقصر المنفصل (حركتان)", json.dumps({"length_harakat": [2], "has_khilaf": False}, ensure_ascii=False)),
        (3, "المد المنفصل - الدوري", "الدوري له القصر والتوسط بخلف عنه", json.dumps({"length_harakat": [2, 4], "has_khilaf": True}, ensure_ascii=False)),
        (3, "المد المنفصل - السوسي", "السوسي يقصر المنفصل (حركتان)", json.dumps({"length_harakat": [2], "has_khilaf": False}, ensure_ascii=False)),
        (4, "المد المنفصل", "ابن عامر يتوسط (4-5 حركات)", json.dumps({"length_harakat": [4, 5], "has_khilaf": False}, ensure_ascii=False)),
        (5, "المد المنفصل", "عاصم يتوسط (4-5 حركات) من طريق الشاطبية", json.dumps({"length_harakat": [4, 5], "has_khilaf": False}, ensure_ascii=False)),
        (6, "المد المنفصل", "حمزة يمد بالإشباع (6 حركات)", json.dumps({"length_harakat": [6], "has_khilaf": False}, ensure_ascii=False)),
        (7, "المد المنفصل", "الكسائي يتوسط (4-5 حركات)", json.dumps({"length_harakat": [4, 5], "has_khilaf": False}, ensure_ascii=False)),
        (8, "المد المنفصل", "أبو جعفر يقصر المنفصل (حركتان)", json.dumps({"length_harakat": [2], "has_khilaf": False}, ensure_ascii=False)),
        (9, "المد المنفصل", "يعقوب يقصر المنفصل (حركتان)", json.dumps({"length_harakat": [2], "has_khilaf": False}, ensure_ascii=False)),
        (10, "المد المنفصل", "خلف العاشر يتوسط (4-5 حركات)", json.dumps({"length_harakat": [4, 5], "has_khilaf": False}, ensure_ascii=False)),

        # الإدغام الكبير rules
        (3, "الإدغام الكبير - السوسي", "السوسي يقرأ بالإدغام الكبير في المتماثلين والمتقاربين والمتجانسين", json.dumps(["الرحيم مالك", "يعلم ما", "ذهب بنورهم", "سَبَقَكُم → سَبَكُّم"], ensure_ascii=False)),
        (3, "الإدغام الكبير - الدوري", "الدوري له الإدغام الكبير بخلف عنه والمأخوذ به الإظهار", json.dumps({"has_khilaf": True, "preferred": "الإظهار"}, ensure_ascii=False)),
        (1, "الإدغام الكبير", "نافع بروايتيه لا يدغم إدغاماً كبيراً", json.dumps({"rule": "الإظهار"}, ensure_ascii=False)),
        (2, "الإدغام الكبير", "ابن كثير لا يدغم إدغاماً كبيراً", json.dumps({"rule": "الإظهار"}, ensure_ascii=False)),
        (4, "الإدغام الكبير", "ابن عامر لا يدغم إدغاماً كبيراً", json.dumps({"rule": "الإظهار"}, ensure_ascii=False)),
        (5, "الإدغام الكبير", "عاصم لا يدغم إدغاماً كبيراً", json.dumps({"rule": "الإظهار"}, ensure_ascii=False)),
        (6, "الإدغام الكبير", "حمزة لا يدغم إدغاماً كبيراً", json.dumps({"rule": "الإظهار"}, ensure_ascii=False)),
        (7, "الإدغام الكبير", "الكسائي لا يدغم إدغاماً كبيراً", json.dumps({"rule": "الإظهار"}, ensure_ascii=False)),
        (8, "الإدغام الكبير", "أبو جعفر لا يدغم إدغاماً كبيراً", json.dumps({"rule": "الإظهار"}, ensure_ascii=False)),
        (9, "الإدغام الكبير", "يعقوب لا يدغم إدغاماً كبيراً", json.dumps({"rule": "الإظهار"}, ensure_ascii=False)),
        (10, "الإدغام الكبير", "خلف العاشر لا يدغم إدغاماً كبيراً", json.dumps({"rule": "الإظهار"}, ensure_ascii=False)),

        # صلة ميم الجمع rules
        (1, "صلة ميم الجمع - قالون", "قالون له صلة ميم الجمع إذا جاء بعدها متحرك بخلف عنه", json.dumps({"rule": "الصلة بخلف", "examples": ["عليهمُو غير", "أنذرتهمُو أم"]}, ensure_ascii=False)),
        (1, "صلة ميم الجمع - ورش", "ورش يسكن ميم الجمع ولا يصلها", json.dumps({"rule": "الإسكان"}, ensure_ascii=False)),
        (2, "صلة ميم الجمع", "ابن كثير يصل ميم الجمع بواو إذا جاء بعدها متحرك", json.dumps({"rule": "الصلة", "examples": ["عليهمُو ولا الضالين", "أنتمُو تشهدون"]}, ensure_ascii=False)),
        (3, "صلة ميم الجمع", "أبو عمرو يسكن ميم الجمع", json.dumps({"rule": "الإسكان"}, ensure_ascii=False)),
        (4, "صلة ميم الجمع", "ابن عامر يسكن ميم الجمع", json.dumps({"rule": "الإسكان"}, ensure_ascii=False)),
        (5, "صلة ميم الجمع", "عاصم يسكن ميم الجمع", json.dumps({"rule": "الإسكان"}, ensure_ascii=False)),
        (6, "صلة ميم الجمع", "حمزة يسكن ميم الجمع", json.dumps({"rule": "الإسكان"}, ensure_ascii=False)),
        (7, "صلة ميم الجمع", "الكسائي يسكن ميم الجمع", json.dumps({"rule": "الإسكان"}, ensure_ascii=False)),
        (8, "صلة ميم الجمع", "أبو جعفر يصل ميم الجمع كابن كثير إذا جاء بعدها متحرك", json.dumps({"rule": "الصلة"}, ensure_ascii=False)),
        (9, "صلة ميم الجمع", "يعقوب يسكن ميم الجمع", json.dumps({"rule": "الإسكان"}, ensure_ascii=False)),
        (10, "صلة ميم الجمع", "خلف العاشر يسكن ميم الجمع", json.dumps({"rule": "الإسكان"}, ensure_ascii=False)),

        # هاء الكناية rules
        (2, "هاء الكناية", "ابن كثير يصل هاء الضمير حتى لو سبقها ساكن وتبعها متحرك (انفراد)", json.dumps({"rule": "الصلة الموسعة", "examples": ["عقلوهُو وهم", "اجتباهُو وهداهُو", "أرجئهُو وأخاه"]}, ensure_ascii=False)),
        (5, "هاء الكناية - حفص", "حفص يصل الهاء إذا وقعت بين متحركين، ويوافق ابن كثير في فيهِ مهاناً", json.dumps({"examples": ["فيهِي مهاناً 25:69", "يؤدهِ إليك بكسر الهاء والقصر"]}, ensure_ascii=False)),
        (6, "هاء الكناية", "حمزة يسكن الهاء في كلمات: يؤدهْ، نؤتهْ، نصلهْ، نولهْ، فألقهْ", json.dumps({"rule": "الإسكان في كلمات", "words": ["يؤدهْ", "نؤتهْ", "نصلهْ", "نولهْ", "فألقهْ"]}, ensure_ascii=False)),
        (3, "هاء الكناية", "أبو عمرو يسكن الهاء في: يؤدهْ، نؤتهْ، نصلهْ، نولهْ، فألقهْ", json.dumps({"rule": "الإسكان في كلمات", "words": ["يؤدهْ", "نؤتهْ", "نصلهْ", "نولهْ", "فألقهْ"]}, ensure_ascii=False)),
        (1, "هاء الكناية", "نافع يصل الهاء إذا وقعت بين متحركين", json.dumps({"rule": "الصلة بين متحركين"}, ensure_ascii=False)),
        (4, "هاء الكناية - هشام", "هشام له الصلة في مواضع والخلاف في أخرى مثل أرجئه", json.dumps({"special": "أرجئه بالهمز والضم والصلة بخلف"}, ensure_ascii=False)),
        (7, "هاء الكناية", "الكسائي يصل الهاء إذا وقعت بين متحركين", json.dumps({"rule": "الصلة بين متحركين"}, ensure_ascii=False)),
        (8, "هاء الكناية", "أبو جعفر يصل الهاء إذا وقعت بين متحركين", json.dumps({"rule": "الصلة بين متحركين"}, ensure_ascii=False)),
        (9, "هاء الكناية", "يعقوب يصل الهاء إذا وقعت بين متحركين", json.dumps({"rule": "الصلة بين متحركين"}, ensure_ascii=False)),
        (10, "هاء الكناية", "خلف العاشر يصل الهاء إذا وقعت بين متحركين", json.dumps({"rule": "الصلة بين متحركين"}, ensure_ascii=False)),
    ]

    # Insert the rules
    cursor.executemany('''
        INSERT INTO qiraat_usul (qari_id, rule_name, rule_description, examples)
        VALUES (?, ?, ?, ?)
    ''', tajweed_rules)

    conn.commit()
    print(f"Successfully inserted {len(tajweed_rules)} tajweed rules into qiraat_usul table")

    # Verify the insertion
    cursor.execute('SELECT COUNT(*) FROM qiraat_usul')
    print(f"Total rows in qiraat_usul: {cursor.fetchone()[0]}")

    conn.close()

if __name__ == '__main__':
    insert_tajweed_rules()
