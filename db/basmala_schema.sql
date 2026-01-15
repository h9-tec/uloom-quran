-- =============================================================================
-- أحكام البسملة في القراءات العشر
-- Basmala Rules for the Ten Qiraat
-- =============================================================================

-- Create table for basmala rules
CREATE TABLE IF NOT EXISTS basmala_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    qari_id INTEGER,
    rawi_id INTEGER,
    context TEXT NOT NULL CHECK(context IN (
        'beginning_of_surah',
        'between_surahs',
        'anfal_tawbah',
        'beginning_fatiha',
        'middle_tawbah',
        'reverse_order'
    )),
    rule TEXT NOT NULL CHECK(rule IN (
        'required',
        'prohibited',
        'three_options',
        'wasl_only',
        'optional'
    )),
    rule_arabic TEXT,
    allowed_methods TEXT,  -- JSON array of allowed methods
    description TEXT,
    description_arabic TEXT,
    notes TEXT,
    notes_arabic TEXT,
    source_reference TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (qari_id) REFERENCES qurra(id),
    FOREIGN KEY (rawi_id) REFERENCES ruwat(id)
);

-- Create table for basmala methods definitions
CREATE TABLE IF NOT EXISTS basmala_methods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    method_key TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    name_arabic TEXT NOT NULL,
    description TEXT,
    description_arabic TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert methods definitions
INSERT OR IGNORE INTO basmala_methods (method_key, name, name_arabic, description, description_arabic) VALUES
('waqf', 'Waqf (Stop)', 'الوقف', 'Stopping at the end of the surah with breathing before continuing', 'الوقف على آخر السورة مع التنفس'),
('sakt', 'Sakt (Pause)', 'السكت', 'Brief pause at the end of surah without breathing', 'الوقف على آخر السورة وقفة لطيفة من غير تنفس'),
('wasl', 'Wasl (Connection)', 'الوصل', 'Connecting the end of one surah directly to the beginning of the next', 'وصل آخر السورة بأول تاليتها'),
('basmala', 'Basmala (Separation)', 'البسملة', 'Reciting Bismillah al-Rahman al-Raheem between the two surahs', 'الإتيان ببسم الله الرحمن الرحيم بين السورتين');

-- =============================================================================
-- Insert Basmala Rules for All Ten Qiraat
-- Source: النشر في القراءات العشر - ابن الجزري / البدور الزاهرة - عبد الفتاح القاضي
-- =============================================================================

-- Universal Rules (apply to all qiraat)
INSERT INTO basmala_rules (qari_id, rawi_id, context, rule, rule_arabic, allowed_methods, description, description_arabic, notes, notes_arabic, source_reference) VALUES
(NULL, NULL, 'beginning_fatiha', 'required', 'واجبة', '["basmala"]', 'All reciters must recite basmala at the beginning of Al-Fatiha', 'جميع القراء بما فيهم حمزة وخلف اتفقوا على الإتيان بالبسملة في أول الفاتحة', 'Universal rule for all ten qiraat', 'حكم عام لجميع القراء العشرة', 'النشر في القراءات العشر - ابن الجزري'),
(NULL, NULL, 'reverse_order', 'required', 'واجبة', '["basmala"]', 'When reading a later surah before an earlier one (reverse order), all reciters must use basmala', 'إن كانت السورة الثانية قبل الأولى في ترتيب القرآن تعين الإتيان بالبسملة لجميع القراء', 'No sakt or wasl allowed in reverse order', 'لا يجوز السكت ولا الوصل لأحد منهم', 'النشر في القراءات العشر - ابن الجزري');

-- Nafi - Qaloon (qari_id=1, rawi_id=1)
INSERT INTO basmala_rules (qari_id, rawi_id, context, rule, rule_arabic, allowed_methods, description, description_arabic, source_reference) VALUES
(1, 1, 'beginning_of_surah', 'required', 'واجبة', '["basmala"]', 'Must recite basmala', 'وجوب البسملة عند الابتداء بالسورة', 'النشر في القراءات العشر'),
(1, 1, 'between_surahs', 'required', 'واجبة', '["basmala"]', 'Must separate surahs with basmala', 'الفصل بالبسملة بين كل سورتين', 'النشر في القراءات العشر'),
(1, 1, 'anfal_tawbah', 'prohibited', 'ممنوعة', '["waqf", "sakt", "wasl"]', 'Three methods allowed, all without basmala', 'ثلاثة أوجه بدون بسملة', 'النشر في القراءات العشر');

-- Nafi - Warsh (qari_id=1, rawi_id=2)
INSERT INTO basmala_rules (qari_id, rawi_id, context, rule, rule_arabic, allowed_methods, description, description_arabic, notes, notes_arabic, source_reference) VALUES
(1, 2, 'beginning_of_surah', 'required', 'واجبة', '["basmala"]', 'Must recite basmala', 'وجوب البسملة عند الابتداء بالسورة', NULL, NULL, 'النشر في القراءات العشر'),
(1, 2, 'between_surahs', 'three_options', 'ثلاثة أوجه', '["basmala", "sakt", "wasl"]', 'Three permissible methods', 'ثلاثة أوجه: البسملة أو السكت أو الوصل', 'Al-Azraq route: three options. Al-Asbahani route: basmala required', 'طريق الأزرق: ثلاثة أوجه. طريق الأصبهاني: البسملة واجبة', 'النشر في القراءات العشر'),
(1, 2, 'anfal_tawbah', 'prohibited', 'ممنوعة', '["waqf", "sakt", "wasl"]', 'Three methods allowed, all without basmala', 'ثلاثة أوجه بدون بسملة', NULL, NULL, 'النشر في القراءات العشر');

-- Ibn Kathir - Al-Bazzi (qari_id=2, rawi_id=3)
INSERT INTO basmala_rules (qari_id, rawi_id, context, rule, rule_arabic, allowed_methods, description, description_arabic, source_reference) VALUES
(2, 3, 'beginning_of_surah', 'required', 'واجبة', '["basmala"]', 'Must recite basmala', 'وجوب البسملة عند الابتداء بالسورة', 'النشر في القراءات العشر'),
(2, 3, 'between_surahs', 'required', 'واجبة', '["basmala"]', 'Must separate surahs with basmala', 'الفصل بالبسملة بين كل سورتين', 'النشر في القراءات العشر'),
(2, 3, 'anfal_tawbah', 'prohibited', 'ممنوعة', '["waqf", "sakt", "wasl"]', 'Three methods allowed, all without basmala', 'ثلاثة أوجه بدون بسملة', 'النشر في القراءات العشر');

-- Ibn Kathir - Qunbul (qari_id=2, rawi_id=4)
INSERT INTO basmala_rules (qari_id, rawi_id, context, rule, rule_arabic, allowed_methods, description, description_arabic, source_reference) VALUES
(2, 4, 'beginning_of_surah', 'required', 'واجبة', '["basmala"]', 'Must recite basmala', 'وجوب البسملة عند الابتداء بالسورة', 'النشر في القراءات العشر'),
(2, 4, 'between_surahs', 'required', 'واجبة', '["basmala"]', 'Must separate surahs with basmala', 'الفصل بالبسملة بين كل سورتين', 'النشر في القراءات العشر'),
(2, 4, 'anfal_tawbah', 'prohibited', 'ممنوعة', '["waqf", "sakt", "wasl"]', 'Three methods allowed, all without basmala', 'ثلاثة أوجه بدون بسملة', 'النشر في القراءات العشر');

-- Abu Amr - Al-Duri (qari_id=3, rawi_id=5)
INSERT INTO basmala_rules (qari_id, rawi_id, context, rule, rule_arabic, allowed_methods, description, description_arabic, source_reference) VALUES
(3, 5, 'beginning_of_surah', 'required', 'واجبة', '["basmala"]', 'Must recite basmala', 'وجوب البسملة عند الابتداء بالسورة', 'النشر في القراءات العشر'),
(3, 5, 'between_surahs', 'three_options', 'ثلاثة أوجه', '["basmala", "sakt", "wasl"]', 'Three permissible methods', 'ثلاثة أوجه: البسملة أو السكت أو الوصل', 'النشر في القراءات العشر'),
(3, 5, 'anfal_tawbah', 'prohibited', 'ممنوعة', '["waqf", "sakt", "wasl"]', 'Three methods allowed, all without basmala', 'ثلاثة أوجه بدون بسملة', 'النشر في القراءات العشر');

-- Abu Amr - Al-Susi (qari_id=3, rawi_id=6)
INSERT INTO basmala_rules (qari_id, rawi_id, context, rule, rule_arabic, allowed_methods, description, description_arabic, source_reference) VALUES
(3, 6, 'beginning_of_surah', 'required', 'واجبة', '["basmala"]', 'Must recite basmala', 'وجوب البسملة عند الابتداء بالسورة', 'النشر في القراءات العشر'),
(3, 6, 'between_surahs', 'three_options', 'ثلاثة أوجه', '["basmala", "sakt", "wasl"]', 'Three permissible methods', 'ثلاثة أوجه: البسملة أو السكت أو الوصل', 'النشر في القراءات العشر'),
(3, 6, 'anfal_tawbah', 'prohibited', 'ممنوعة', '["waqf", "sakt", "wasl"]', 'Three methods allowed, all without basmala', 'ثلاثة أوجه بدون بسملة', 'النشر في القراءات العشر');

-- Ibn Amir - Hisham (qari_id=4, rawi_id=7)
INSERT INTO basmala_rules (qari_id, rawi_id, context, rule, rule_arabic, allowed_methods, description, description_arabic, source_reference) VALUES
(4, 7, 'beginning_of_surah', 'required', 'واجبة', '["basmala"]', 'Must recite basmala', 'وجوب البسملة عند الابتداء بالسورة', 'النشر في القراءات العشر'),
(4, 7, 'between_surahs', 'three_options', 'ثلاثة أوجه', '["basmala", "sakt", "wasl"]', 'Three permissible methods', 'ثلاثة أوجه: البسملة أو السكت أو الوصل', 'النشر في القراءات العشر'),
(4, 7, 'anfal_tawbah', 'prohibited', 'ممنوعة', '["waqf", "sakt", "wasl"]', 'Three methods allowed, all without basmala', 'ثلاثة أوجه بدون بسملة', 'النشر في القراءات العشر');

-- Ibn Amir - Ibn Dhakwan (qari_id=4, rawi_id=8)
INSERT INTO basmala_rules (qari_id, rawi_id, context, rule, rule_arabic, allowed_methods, description, description_arabic, source_reference) VALUES
(4, 8, 'beginning_of_surah', 'required', 'واجبة', '["basmala"]', 'Must recite basmala', 'وجوب البسملة عند الابتداء بالسورة', 'النشر في القراءات العشر'),
(4, 8, 'between_surahs', 'three_options', 'ثلاثة أوجه', '["basmala", "sakt", "wasl"]', 'Three permissible methods', 'ثلاثة أوجه: البسملة أو السكت أو الوصل', 'النشر في القراءات العشر'),
(4, 8, 'anfal_tawbah', 'prohibited', 'ممنوعة', '["waqf", "sakt", "wasl"]', 'Three methods allowed, all without basmala', 'ثلاثة أوجه بدون بسملة', 'النشر في القراءات العشر');

-- Asim - Shuba (qari_id=5, rawi_id=9)
INSERT INTO basmala_rules (qari_id, rawi_id, context, rule, rule_arabic, allowed_methods, description, description_arabic, source_reference) VALUES
(5, 9, 'beginning_of_surah', 'required', 'واجبة', '["basmala"]', 'Must recite basmala', 'وجوب البسملة عند الابتداء بالسورة', 'النشر في القراءات العشر'),
(5, 9, 'between_surahs', 'required', 'واجبة', '["basmala"]', 'Must separate surahs with basmala', 'الفصل بالبسملة بين كل سورتين', 'النشر في القراءات العشر'),
(5, 9, 'anfal_tawbah', 'prohibited', 'ممنوعة', '["waqf", "sakt", "wasl"]', 'Three methods allowed, all without basmala', 'ثلاثة أوجه بدون بسملة', 'النشر في القراءات العشر');

-- Asim - Hafs (qari_id=5, rawi_id=10)
INSERT INTO basmala_rules (qari_id, rawi_id, context, rule, rule_arabic, allowed_methods, description, description_arabic, notes, source_reference) VALUES
(5, 10, 'beginning_of_surah', 'required', 'واجبة', '["basmala"]', 'Must recite basmala', 'وجوب البسملة عند الابتداء بالسورة', NULL, 'النشر في القراءات العشر'),
(5, 10, 'between_surahs', 'required', 'واجبة', '["basmala"]', 'Must separate surahs with basmala (most common reading worldwide)', 'الفصل بالبسملة بين كل سورتين', 'Hafs reading is the most widely used', 'النشر في القراءات العشر'),
(5, 10, 'anfal_tawbah', 'prohibited', 'ممنوعة', '["waqf", "sakt", "wasl"]', 'Three methods allowed, all without basmala', 'ثلاثة أوجه بدون بسملة', NULL, 'النشر في القراءات العشر');

-- Hamza - Khalaf (rawi) (qari_id=6, rawi_id=11)
INSERT INTO basmala_rules (qari_id, rawi_id, context, rule, rule_arabic, allowed_methods, description, description_arabic, notes, notes_arabic, source_reference) VALUES
(6, 11, 'beginning_of_surah', 'required', 'واجبة', '["basmala"]', 'Must recite basmala at beginning', 'وجوب البسملة عند الابتداء بالسورة', NULL, NULL, 'النشر في القراءات العشر'),
(6, 11, 'between_surahs', 'wasl_only', 'الوصل فقط', '["wasl"]', 'Connect surahs directly without basmala (single method only)', 'وصل آخر السورة بأول ما بعدها من غير بسملة', 'Exception: Al-Fatiha always has basmala', 'الاستثناء: الفاتحة تبدأ دائما بالبسملة', 'النشر في القراءات العشر'),
(6, 11, 'anfal_tawbah', 'prohibited', 'ممنوعة', '["waqf", "sakt", "wasl"]', 'Three methods allowed, all without basmala', 'ثلاثة أوجه بدون بسملة', NULL, NULL, 'النشر في القراءات العشر');

-- Hamza - Khallad (qari_id=6, rawi_id=12)
INSERT INTO basmala_rules (qari_id, rawi_id, context, rule, rule_arabic, allowed_methods, description, description_arabic, notes, notes_arabic, source_reference) VALUES
(6, 12, 'beginning_of_surah', 'required', 'واجبة', '["basmala"]', 'Must recite basmala at beginning', 'وجوب البسملة عند الابتداء بالسورة', NULL, NULL, 'النشر في القراءات العشر'),
(6, 12, 'between_surahs', 'wasl_only', 'الوصل فقط', '["wasl"]', 'Connect surahs directly without basmala (single method only)', 'وصل آخر السورة بأول ما بعدها من غير بسملة', 'Exception: Al-Fatiha always has basmala', 'الاستثناء: الفاتحة تبدأ دائما بالبسملة', 'النشر في القراءات العشر'),
(6, 12, 'anfal_tawbah', 'prohibited', 'ممنوعة', '["waqf", "sakt", "wasl"]', 'Three methods allowed, all without basmala', 'ثلاثة أوجه بدون بسملة', NULL, NULL, 'النشر في القراءات العشر');

-- Al-Kisai - Abu al-Harith (qari_id=7, rawi_id=13)
INSERT INTO basmala_rules (qari_id, rawi_id, context, rule, rule_arabic, allowed_methods, description, description_arabic, source_reference) VALUES
(7, 13, 'beginning_of_surah', 'required', 'واجبة', '["basmala"]', 'Must recite basmala', 'وجوب البسملة عند الابتداء بالسورة', 'النشر في القراءات العشر'),
(7, 13, 'between_surahs', 'required', 'واجبة', '["basmala"]', 'Must separate surahs with basmala', 'الفصل بالبسملة بين كل سورتين', 'النشر في القراءات العشر'),
(7, 13, 'anfal_tawbah', 'prohibited', 'ممنوعة', '["waqf", "sakt", "wasl"]', 'Three methods allowed, all without basmala', 'ثلاثة أوجه بدون بسملة', 'النشر في القراءات العشر');

-- Al-Kisai - Al-Duri (qari_id=7, rawi_id=14)
INSERT INTO basmala_rules (qari_id, rawi_id, context, rule, rule_arabic, allowed_methods, description, description_arabic, source_reference) VALUES
(7, 14, 'beginning_of_surah', 'required', 'واجبة', '["basmala"]', 'Must recite basmala', 'وجوب البسملة عند الابتداء بالسورة', 'النشر في القراءات العشر'),
(7, 14, 'between_surahs', 'required', 'واجبة', '["basmala"]', 'Must separate surahs with basmala', 'الفصل بالبسملة بين كل سورتين', 'النشر في القراءات العشر'),
(7, 14, 'anfal_tawbah', 'prohibited', 'ممنوعة', '["waqf", "sakt", "wasl"]', 'Three methods allowed, all without basmala', 'ثلاثة أوجه بدون بسملة', 'النشر في القراءات العشر');

-- Abu Jafar - Ibn Wardan (qari_id=8, rawi_id=15)
INSERT INTO basmala_rules (qari_id, rawi_id, context, rule, rule_arabic, allowed_methods, description, description_arabic, source_reference) VALUES
(8, 15, 'beginning_of_surah', 'required', 'واجبة', '["basmala"]', 'Must recite basmala', 'وجوب البسملة عند الابتداء بالسورة', 'النشر في القراءات العشر'),
(8, 15, 'between_surahs', 'required', 'واجبة', '["basmala"]', 'Must separate surahs with basmala', 'الفصل بالبسملة بين كل سورتين', 'النشر في القراءات العشر'),
(8, 15, 'anfal_tawbah', 'prohibited', 'ممنوعة', '["waqf", "sakt", "wasl"]', 'Three methods allowed, all without basmala', 'ثلاثة أوجه بدون بسملة', 'النشر في القراءات العشر');

-- Abu Jafar - Ibn Jammaz (qari_id=8, rawi_id=16)
INSERT INTO basmala_rules (qari_id, rawi_id, context, rule, rule_arabic, allowed_methods, description, description_arabic, source_reference) VALUES
(8, 16, 'beginning_of_surah', 'required', 'واجبة', '["basmala"]', 'Must recite basmala', 'وجوب البسملة عند الابتداء بالسورة', 'النشر في القراءات العشر'),
(8, 16, 'between_surahs', 'required', 'واجبة', '["basmala"]', 'Must separate surahs with basmala', 'الفصل بالبسملة بين كل سورتين', 'النشر في القراءات العشر'),
(8, 16, 'anfal_tawbah', 'prohibited', 'ممنوعة', '["waqf", "sakt", "wasl"]', 'Three methods allowed, all without basmala', 'ثلاثة أوجه بدون بسملة', 'النشر في القراءات العشر');

-- Yaqub - Ruways (qari_id=9, rawi_id=17)
INSERT INTO basmala_rules (qari_id, rawi_id, context, rule, rule_arabic, allowed_methods, description, description_arabic, source_reference) VALUES
(9, 17, 'beginning_of_surah', 'required', 'واجبة', '["basmala"]', 'Must recite basmala', 'وجوب البسملة عند الابتداء بالسورة', 'النشر في القراءات العشر'),
(9, 17, 'between_surahs', 'three_options', 'ثلاثة أوجه', '["basmala", "sakt", "wasl"]', 'Three permissible methods', 'ثلاثة أوجه: البسملة أو السكت أو الوصل', 'النشر في القراءات العشر'),
(9, 17, 'anfal_tawbah', 'prohibited', 'ممنوعة', '["waqf", "sakt", "wasl"]', 'Three methods allowed, all without basmala', 'ثلاثة أوجه بدون بسملة', 'النشر في القراءات العشر');

-- Yaqub - Rawh (qari_id=9, rawi_id=18)
INSERT INTO basmala_rules (qari_id, rawi_id, context, rule, rule_arabic, allowed_methods, description, description_arabic, source_reference) VALUES
(9, 18, 'beginning_of_surah', 'required', 'واجبة', '["basmala"]', 'Must recite basmala', 'وجوب البسملة عند الابتداء بالسورة', 'النشر في القراءات العشر'),
(9, 18, 'between_surahs', 'three_options', 'ثلاثة أوجه', '["basmala", "sakt", "wasl"]', 'Three permissible methods', 'ثلاثة أوجه: البسملة أو السكت أو الوصل', 'النشر في القراءات العشر'),
(9, 18, 'anfal_tawbah', 'prohibited', 'ممنوعة', '["waqf", "sakt", "wasl"]', 'Three methods allowed, all without basmala', 'ثلاثة أوجه بدون بسملة', 'النشر في القراءات العشر');

-- Khalaf al-Ashir - Ishaq (qari_id=10, rawi_id=19)
INSERT INTO basmala_rules (qari_id, rawi_id, context, rule, rule_arabic, allowed_methods, description, description_arabic, notes, notes_arabic, source_reference) VALUES
(10, 19, 'beginning_of_surah', 'required', 'واجبة', '["basmala"]', 'Must recite basmala at beginning', 'وجوب البسملة عند الابتداء بالسورة', NULL, NULL, 'النشر في القراءات العشر'),
(10, 19, 'between_surahs', 'wasl_only', 'الوصل فقط', '["wasl"]', 'Connect surahs directly without basmala (single method only)', 'وصل آخر السورة بأول ما بعدها من غير بسملة', 'Exception: Al-Fatiha always has basmala', 'الاستثناء: الفاتحة تبدأ دائما بالبسملة', 'النشر في القراءات العشر'),
(10, 19, 'anfal_tawbah', 'prohibited', 'ممنوعة', '["waqf", "sakt", "wasl"]', 'Three methods allowed, all without basmala', 'ثلاثة أوجه بدون بسملة', NULL, NULL, 'النشر في القراءات العشر');

-- Khalaf al-Ashir - Idris (qari_id=10, rawi_id=20)
INSERT INTO basmala_rules (qari_id, rawi_id, context, rule, rule_arabic, allowed_methods, description, description_arabic, notes, notes_arabic, source_reference) VALUES
(10, 20, 'beginning_of_surah', 'required', 'واجبة', '["basmala"]', 'Must recite basmala at beginning', 'وجوب البسملة عند الابتداء بالسورة', NULL, NULL, 'النشر في القراءات العشر'),
(10, 20, 'between_surahs', 'wasl_only', 'الوصل فقط', '["wasl"]', 'Connect surahs directly without basmala (single method only)', 'وصل آخر السورة بأول ما بعدها من غير بسملة', 'Exception: Al-Fatiha always has basmala', 'الاستثناء: الفاتحة تبدأ دائما بالبسملة', 'النشر في القراءات العشر'),
(10, 20, 'anfal_tawbah', 'prohibited', 'ممنوعة', '["waqf", "sakt", "wasl"]', 'Three methods allowed, all without basmala', 'ثلاثة أوجه بدون بسملة', NULL, NULL, 'النشر في القراءات العشر');

-- =============================================================================
-- Create View for Easy Querying
-- =============================================================================

CREATE VIEW IF NOT EXISTS v_basmala_rules AS
SELECT
    br.id,
    q.name_arabic as qari_name,
    q.name_english as qari_name_english,
    r.name_arabic as rawi_name,
    r.name_english as rawi_name_english,
    br.context,
    br.rule,
    br.rule_arabic,
    br.allowed_methods,
    br.description,
    br.description_arabic,
    br.notes,
    br.notes_arabic
FROM basmala_rules br
LEFT JOIN qurra q ON br.qari_id = q.id
LEFT JOIN ruwat r ON br.rawi_id = r.id
ORDER BY q.rank_order, br.context;

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_basmala_rules_qari ON basmala_rules(qari_id);
CREATE INDEX IF NOT EXISTS idx_basmala_rules_rawi ON basmala_rules(rawi_id);
CREATE INDEX IF NOT EXISTS idx_basmala_rules_context ON basmala_rules(context);
