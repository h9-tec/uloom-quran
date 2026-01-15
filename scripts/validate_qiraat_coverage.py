#!/usr/bin/env python3
"""
Qiraat Data Validation Script

This script validates the coverage of qiraat texts in the uloom_quran database.
It checks:
1. Coverage for each riwaya in qiraat_texts table
2. Reports missing surahs/verses for each riwaya
3. Identifies gaps in coverage
4. Compares verse counts (expected ~6236 per riwaya with minor variations)
5. Generates a comprehensive coverage report
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple, Set, Optional

# Database path
DB_PATH = Path("/home/hesham-haroun/Quran/db/uloom_quran.db")

# Expected 20 riwayat with their qari associations
EXPECTED_RIWAYAT = {
    # Asim (عاصم)
    "Hafs": {"qari": "عاصم", "qari_en": "Asim", "arabic": "حفص"},
    "Shuba": {"qari": "عاصم", "qari_en": "Asim", "arabic": "شعبة"},
    # Nafi (نافع)
    "Warsh": {"qari": "نافع", "qari_en": "Nafi", "arabic": "ورش"},
    "Qaloon": {"qari": "نافع", "qari_en": "Nafi", "arabic": "قالون"},
    # Abu Amr (أبو عمرو)
    "Doori": {"qari": "أبو عمرو", "qari_en": "Abu Amr", "arabic": "الدوري"},
    "Soosi": {"qari": "أبو عمرو", "qari_en": "Abu Amr", "arabic": "السوسي"},
    # Ibn Kathir (ابن كثير)
    "Bazzi": {"qari": "ابن كثير", "qari_en": "Ibn Kathir", "arabic": "البزي"},
    "Qunbul": {"qari": "ابن كثير", "qari_en": "Ibn Kathir", "arabic": "قنبل"},
    # Ibn Amir (ابن عامر)
    "Hisham": {"qari": "ابن عامر", "qari_en": "Ibn Amir", "arabic": "هشام"},
    "Ibn Dhakwan": {"qari": "ابن عامر", "qari_en": "Ibn Amir", "arabic": "ابن ذكوان"},
    # Hamza (حمزة)
    "Khalaf": {"qari": "حمزة", "qari_en": "Hamza", "arabic": "خلف"},
    "Khallad": {"qari": "حمزة", "qari_en": "Hamza", "arabic": "خلاد"},
    # Al-Kisai (الكسائي)
    "Doori Al-Kisai": {"qari": "الكسائي", "qari_en": "Al-Kisai", "arabic": "الدوري"},
    "Abu Al-Harith": {"qari": "الكسائي", "qari_en": "Al-Kisai", "arabic": "أبو الحارث"},
    # Abu Jafar (أبو جعفر)
    "Ibn Wardan": {"qari": "أبو جعفر", "qari_en": "Abu Jafar", "arabic": "ابن وردان"},
    "Ibn Jamaz": {"qari": "أبو جعفر", "qari_en": "Abu Jafar", "arabic": "ابن جماز"},
    # Yaqub (يعقوب)
    "Ruways": {"qari": "يعقوب", "qari_en": "Yaqub", "arabic": "رويس"},
    "Rawh": {"qari": "يعقوب", "qari_en": "Yaqub", "arabic": "روح"},
    # Khalaf Al-Ashir (خلف العاشر)
    "Ishaq": {"qari": "خلف العاشر", "qari_en": "Khalaf Al-Ashir", "arabic": "إسحاق"},
    "Idris": {"qari": "خلف العاشر", "qari_en": "Khalaf Al-Ashir", "arabic": "إدريس"},
}

# Standard verse count is 6236, but some counting systems differ slightly
STANDARD_VERSE_COUNT = 6236
ACCEPTABLE_VERSE_RANGE = (6200, 6250)  # Allow for counting system variations


class QiraatCoverageValidator:
    """Validates qiraat text coverage in the database."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.surahs: Dict[int, dict] = {}
        self.riwayat: Dict[int, dict] = {}
        self.qiraat_coverage: Dict[int, Dict[int, Set[int]]] = defaultdict(lambda: defaultdict(set))
        self.orphan_riwaya_ids: Set[int] = set()
        self.report_lines: List[str] = []

    def connect(self):
        """Establish database connection."""
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def log(self, message: str, level: str = "INFO"):
        """Add message to report."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] [{level}] {message}"
        self.report_lines.append(line)
        print(line)

    def load_surahs(self):
        """Load surah information from database."""
        self.cursor.execute("""
            SELECT id, name_arabic, name_english, ayah_count
            FROM surahs ORDER BY id
        """)
        for row in self.cursor.fetchall():
            self.surahs[row[0]] = {
                "id": row[0],
                "name_arabic": row[1],
                "name_english": row[2],
                "ayah_count": row[3]
            }
        self.log(f"Loaded {len(self.surahs)} surahs from database")

    def load_riwayat(self):
        """Load riwayat information from database."""
        self.cursor.execute("""
            SELECT id, code, name_arabic, name_english, qari_id, source
            FROM riwayat ORDER BY id
        """)
        for row in self.cursor.fetchall():
            self.riwayat[row[0]] = {
                "id": row[0],
                "code": row[1],
                "name_arabic": row[2],
                "name_english": row[3],
                "qari_id": row[4],
                "source": row[5]
            }
        self.log(f"Loaded {len(self.riwayat)} riwayat from database")

    def load_qiraat_coverage(self):
        """Load qiraat text coverage data."""
        self.cursor.execute("""
            SELECT riwaya_id, surah_id, ayah_number
            FROM qiraat_texts
        """)
        count = 0
        for row in self.cursor.fetchall():
            riwaya_id, surah_id, ayah_number = row
            self.qiraat_coverage[riwaya_id][surah_id].add(ayah_number)
            count += 1

            # Track orphan riwaya IDs (in qiraat_texts but not in riwayat table)
            if riwaya_id not in self.riwayat:
                self.orphan_riwaya_ids.add(riwaya_id)

        self.log(f"Loaded {count:,} verse records from qiraat_texts")
        if self.orphan_riwaya_ids:
            self.log(f"Found {len(self.orphan_riwaya_ids)} orphan riwaya IDs: {sorted(self.orphan_riwaya_ids)}", "WARNING")

    def get_expected_verses(self, surah_id: int) -> Set[int]:
        """Get expected verse numbers for a surah."""
        if surah_id not in self.surahs:
            return set()
        return set(range(1, self.surahs[surah_id]["ayah_count"] + 1))

    def check_riwaya_coverage(self, riwaya_id: int) -> dict:
        """Check coverage for a specific riwaya."""
        riwaya_info = self.riwayat.get(riwaya_id, {})

        # For orphan riwaya IDs, create placeholder info
        if not riwaya_info and riwaya_id in self.orphan_riwaya_ids:
            riwaya_info = {
                "id": riwaya_id,
                "code": f"orphan_{riwaya_id}",
                "name_arabic": f"غير معرف (ID: {riwaya_id})",
                "name_english": f"Orphan Riwaya (ID: {riwaya_id})",
                "qari_id": None,
                "source": "ORPHAN - Missing from riwayat table"
            }

        result = {
            "riwaya_id": riwaya_id,
            "riwaya_info": riwaya_info,
            "is_orphan": riwaya_id in self.orphan_riwaya_ids,
            "total_verses": 0,
            "missing_surahs": [],
            "incomplete_surahs": [],
            "extra_verses": [],
            "gaps": [],
            "coverage_percentage": 0.0
        }

        total_expected = sum(s["ayah_count"] for s in self.surahs.values())
        total_found = 0

        for surah_id in range(1, 115):
            if surah_id not in self.surahs:
                continue

            expected_verses = self.get_expected_verses(surah_id)
            found_verses = self.qiraat_coverage[riwaya_id].get(surah_id, set())

            total_found += len(found_verses)

            if not found_verses:
                result["missing_surahs"].append({
                    "surah_id": surah_id,
                    "name_arabic": self.surahs[surah_id]["name_arabic"],
                    "name_english": self.surahs[surah_id]["name_english"],
                    "expected_verses": len(expected_verses)
                })
            else:
                missing = expected_verses - found_verses
                extra = found_verses - expected_verses

                if missing:
                    result["incomplete_surahs"].append({
                        "surah_id": surah_id,
                        "name_arabic": self.surahs[surah_id]["name_arabic"],
                        "name_english": self.surahs[surah_id]["name_english"],
                        "missing_verses": sorted(missing),
                        "found": len(found_verses),
                        "expected": len(expected_verses)
                    })

                    # Check for gaps (non-consecutive missing verses)
                    if len(missing) > 1:
                        sorted_missing = sorted(missing)
                        gaps = []
                        gap_start = sorted_missing[0]
                        gap_end = sorted_missing[0]

                        for v in sorted_missing[1:]:
                            if v == gap_end + 1:
                                gap_end = v
                            else:
                                gaps.append((gap_start, gap_end))
                                gap_start = v
                                gap_end = v
                        gaps.append((gap_start, gap_end))

                        if gaps:
                            result["gaps"].append({
                                "surah_id": surah_id,
                                "name": self.surahs[surah_id]["name_english"],
                                "gaps": gaps
                            })

                if extra:
                    result["extra_verses"].append({
                        "surah_id": surah_id,
                        "name": self.surahs[surah_id]["name_english"],
                        "extra_verses": sorted(extra)
                    })

        result["total_verses"] = total_found
        result["coverage_percentage"] = (total_found / total_expected * 100) if total_expected > 0 else 0

        return result

    def map_riwaya_to_expected(self) -> Dict[int, Optional[str]]:
        """Map database riwayat to expected riwayat names."""
        mapping = {}

        # Keywords to match riwayat
        riwaya_keywords = {
            "hafs": "Hafs",
            "shuba": "Shuba",
            "shouba": "Shuba",
            "warsh": "Warsh",
            "qaloon": "Qaloon",
            "bazzi": "Bazzi",
            "qunbul": "Qunbul",
            "qumbul": "Qunbul",
            "hisham": "Hisham",
            "ibn_dhakwan": "Ibn Dhakwan",
            "ibn dhakwan": "Ibn Dhakwan",
            "khalaf": "Khalaf",
            "khallad": "Khallad",
            "doori_kisai": "Doori Al-Kisai",
            "abu_harith": "Abu Al-Harith",
            "abu harith": "Abu Al-Harith",
            "ibn_wardan": "Ibn Wardan",
            "ibn wardan": "Ibn Wardan",
            "ibn_jamaz": "Ibn Jamaz",
            "ibn jamaz": "Ibn Jamaz",
            "ruways": "Ruways",
            "rawh": "Rawh",
            "ishaq": "Ishaq",
            "idris": "Idris",
        }

        for riwaya_id, info in self.riwayat.items():
            code = info.get("code", "").lower()
            name_en = info.get("name_english", "").lower()

            matched = None
            for keyword, expected_name in riwaya_keywords.items():
                if keyword in code or keyword in name_en:
                    matched = expected_name
                    break

            # Special handling for Doori (two riwayat with same name)
            if "doori" in code or "douri" in code:
                if "kisai" in code or "kisai" in name_en:
                    matched = "Doori Al-Kisai"
                elif "abu amr" in name_en.lower():
                    matched = "Doori"
                else:
                    matched = "Doori"  # Default to Abu Amr's Doori

            # Special handling for Soosi
            if "soosi" in code or "susi" in code:
                matched = "Soosi"

            mapping[riwaya_id] = matched

        return mapping

    def generate_report(self) -> str:
        """Generate comprehensive coverage report."""
        report = []
        report.append("=" * 80)
        report.append("QIRAAT DATA COVERAGE VALIDATION REPORT")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Database: {self.db_path}")
        report.append("=" * 80)
        report.append("")

        # Section 1: Summary Statistics
        report.append("-" * 80)
        report.append("SECTION 1: SUMMARY STATISTICS")
        report.append("-" * 80)

        total_surahs = len(self.surahs)
        total_expected_verses = sum(s["ayah_count"] for s in self.surahs.values())
        total_riwayat_in_db = len(self.riwayat)
        riwayat_with_data = len(self.qiraat_coverage)

        orphan_count = len(self.orphan_riwaya_ids)

        report.append(f"Total Surahs in Database: {total_surahs}")
        report.append(f"Total Expected Verses (per riwaya): {total_expected_verses}")
        report.append(f"Standard Quran Verse Count: {STANDARD_VERSE_COUNT}")
        report.append(f"Total Riwayat Defined: {total_riwayat_in_db}")
        report.append(f"Riwayat with Qiraat Data: {riwayat_with_data}")
        report.append(f"Orphan Riwaya IDs (data without definition): {orphan_count}")
        if orphan_count > 0:
            report.append(f"  Orphan IDs: {sorted(self.orphan_riwaya_ids)}")
        report.append(f"Expected Riwayat (20 canonical): {len(EXPECTED_RIWAYAT)}")
        report.append("")

        # Section 2: Riwayat in Database
        report.append("-" * 80)
        report.append("SECTION 2: RIWAYAT IN DATABASE")
        report.append("-" * 80)

        riwaya_mapping = self.map_riwaya_to_expected()

        report.append(f"{'ID':<6} {'Code':<20} {'Arabic Name':<35} {'English Name':<40} {'Mapped To':<20}")
        report.append("-" * 121)

        for riwaya_id, info in sorted(self.riwayat.items()):
            mapped = riwaya_mapping.get(riwaya_id, "Unknown")
            report.append(
                f"{riwaya_id:<6} {info['code']:<20} {info['name_arabic']:<35} "
                f"{info['name_english']:<40} {mapped or 'N/A':<20}"
            )
        report.append("")

        # Section 3: Coverage Analysis by Riwaya
        report.append("-" * 80)
        report.append("SECTION 3: COVERAGE ANALYSIS BY RIWAYA")
        report.append("-" * 80)

        coverage_summary = []

        for riwaya_id in sorted(self.qiraat_coverage.keys()):
            coverage = self.check_riwaya_coverage(riwaya_id)
            info = coverage["riwaya_info"]

            status = "OK"
            if coverage["missing_surahs"]:
                status = "MISSING SURAHS"
            elif coverage["incomplete_surahs"]:
                status = "INCOMPLETE"
            elif coverage["total_verses"] < ACCEPTABLE_VERSE_RANGE[0]:
                status = "LOW COUNT"
            elif coverage["total_verses"] > ACCEPTABLE_VERSE_RANGE[1]:
                status = "HIGH COUNT"

            coverage_summary.append({
                "riwaya_id": riwaya_id,
                "name": info.get("name_english", "Unknown"),
                "code": info.get("code", ""),
                "total_verses": coverage["total_verses"],
                "coverage": coverage["coverage_percentage"],
                "missing_surahs": len(coverage["missing_surahs"]),
                "incomplete_surahs": len(coverage["incomplete_surahs"]),
                "status": status,
                "is_orphan": coverage.get("is_orphan", False),
                "details": coverage
            })

        report.append(f"{'ID':<6} {'Riwaya Name':<40} {'Verses':<10} {'Coverage':<12} {'Missing':<10} {'Incomplete':<12} {'Status':<20}")
        report.append("-" * 110)

        for item in coverage_summary:
            status = item['status']
            if item.get('is_orphan'):
                status = f"ORPHAN - {status}" if status != "OK" else "ORPHAN"
            report.append(
                f"{item['riwaya_id']:<6} {item['name']:<40} {item['total_verses']:<10} "
                f"{item['coverage']:.2f}%{'':<5} {item['missing_surahs']:<10} "
                f"{item['incomplete_surahs']:<12} {status:<20}"
            )
        report.append("")

        # Section 4: Missing Surahs Detail
        report.append("-" * 80)
        report.append("SECTION 4: MISSING SURAHS DETAIL")
        report.append("-" * 80)

        has_missing = False
        for item in coverage_summary:
            if item["details"]["missing_surahs"]:
                has_missing = True
                report.append(f"\nRiwaya: {item['name']} (ID: {item['riwaya_id']})")
                report.append("Missing Surahs:")
                for surah in item["details"]["missing_surahs"]:
                    report.append(
                        f"  - Surah {surah['surah_id']}: {surah['name_arabic']} ({surah['name_english']}) "
                        f"- {surah['expected_verses']} verses"
                    )

        if not has_missing:
            report.append("No completely missing surahs found in any riwaya.")
        report.append("")

        # Section 5: Incomplete Surahs Detail
        report.append("-" * 80)
        report.append("SECTION 5: INCOMPLETE SURAHS DETAIL")
        report.append("-" * 80)

        has_incomplete = False
        for item in coverage_summary:
            if item["details"]["incomplete_surahs"]:
                has_incomplete = True
                report.append(f"\nRiwaya: {item['name']} (ID: {item['riwaya_id']})")
                report.append("Incomplete Surahs:")
                for surah in item["details"]["incomplete_surahs"]:
                    missing_str = self._format_verse_list(surah["missing_verses"])
                    report.append(
                        f"  - Surah {surah['surah_id']}: {surah['name_arabic']} ({surah['name_english']})"
                    )
                    report.append(f"    Found: {surah['found']}/{surah['expected']} verses")
                    report.append(f"    Missing verses: {missing_str}")

        if not has_incomplete:
            report.append("No incomplete surahs found in any riwaya.")
        report.append("")

        # Section 6: Coverage Gaps
        report.append("-" * 80)
        report.append("SECTION 6: COVERAGE GAPS")
        report.append("-" * 80)

        has_gaps = False
        for item in coverage_summary:
            if item["details"]["gaps"]:
                has_gaps = True
                report.append(f"\nRiwaya: {item['name']} (ID: {item['riwaya_id']})")
                for gap_info in item["details"]["gaps"]:
                    gaps_str = ", ".join(
                        f"{g[0]}-{g[1]}" if g[0] != g[1] else str(g[0])
                        for g in gap_info["gaps"]
                    )
                    report.append(f"  Surah {gap_info['surah_id']} ({gap_info['name']}): gaps at verses {gaps_str}")

        if not has_gaps:
            report.append("No coverage gaps found.")
        report.append("")

        # Section 7: Verse Count Comparison
        report.append("-" * 80)
        report.append("SECTION 7: VERSE COUNT COMPARISON")
        report.append("-" * 80)
        report.append(f"Expected verse count: ~{STANDARD_VERSE_COUNT} (with minor variations)")
        report.append(f"Acceptable range: {ACCEPTABLE_VERSE_RANGE[0]} - {ACCEPTABLE_VERSE_RANGE[1]}")
        report.append("")

        report.append(f"{'Riwaya':<45} {'Verses':<10} {'Deviation':<15} {'Status':<15}")
        report.append("-" * 85)

        for item in coverage_summary:
            deviation = item["total_verses"] - STANDARD_VERSE_COUNT
            deviation_str = f"+{deviation}" if deviation > 0 else str(deviation)
            status = "NORMAL"
            if item["total_verses"] < ACCEPTABLE_VERSE_RANGE[0]:
                status = "TOO LOW"
            elif item["total_verses"] > ACCEPTABLE_VERSE_RANGE[1]:
                status = "TOO HIGH"
            report.append(
                f"{item['name']:<45} {item['total_verses']:<10} {deviation_str:<15} {status:<15}"
            )
        report.append("")

        # Section 8: Expected vs Found Riwayat
        report.append("-" * 80)
        report.append("SECTION 8: EXPECTED VS FOUND RIWAYAT (20 Canonical)")
        report.append("-" * 80)

        found_expected = set()
        for riwaya_id, mapped_name in riwaya_mapping.items():
            if mapped_name and riwaya_id in self.qiraat_coverage:
                found_expected.add(mapped_name)

        report.append(f"{'Expected Riwaya':<25} {'Qari':<20} {'Status':<15}")
        report.append("-" * 60)

        for expected_name, info in EXPECTED_RIWAYAT.items():
            status = "FOUND" if expected_name in found_expected else "MISSING"
            report.append(f"{expected_name:<25} {info['qari_en']:<20} {status:<15}")

        report.append("")
        report.append(f"Total Expected: {len(EXPECTED_RIWAYAT)}")
        report.append(f"Total Found: {len(found_expected)}")
        report.append(f"Missing: {len(EXPECTED_RIWAYAT) - len(found_expected)}")

        missing_expected = set(EXPECTED_RIWAYAT.keys()) - found_expected
        if missing_expected:
            report.append(f"\nMissing Riwayat: {', '.join(sorted(missing_expected))}")
        report.append("")

        # Section 9: Data Integrity Issues
        report.append("-" * 80)
        report.append("SECTION 9: DATA INTEGRITY ISSUES")
        report.append("-" * 80)

        integrity_issues = []

        # Orphan riwaya IDs
        orphan_items = [item for item in coverage_summary if item.get("is_orphan")]
        if orphan_items:
            integrity_issues.append("ORPHAN RIWAYA IDs (data exists without riwayat table entry):")
            for item in orphan_items:
                integrity_issues.append(
                    f"  - ID {item['riwaya_id']}: {item['total_verses']} verses, "
                    f"coverage: {item['coverage']:.2f}%"
                )
            integrity_issues.append("")
            integrity_issues.append("  Recommendation: Add entries to riwayat table for these IDs")
            integrity_issues.append("  or migrate data to existing valid riwaya IDs.")

        if not integrity_issues:
            integrity_issues.append("No data integrity issues found.")

        for issue in integrity_issues:
            report.append(issue)
        report.append("")

        # Section 10: Recommendations
        report.append("-" * 80)
        report.append("SECTION 10: RECOMMENDATIONS")
        report.append("-" * 80)

        recommendations = []

        if len(found_expected) < len(EXPECTED_RIWAYAT):
            recommendations.append(
                f"- Add data for missing riwayat: {', '.join(sorted(missing_expected))}"
            )

        if orphan_items:
            recommendations.append(
                f"- Fix orphan riwaya IDs: {', '.join(str(item['riwaya_id']) for item in orphan_items)}"
            )

        low_coverage = [item for item in coverage_summary if item["total_verses"] < ACCEPTABLE_VERSE_RANGE[0] and not item.get("is_orphan")]
        if low_coverage:
            recommendations.append(
                f"- Investigate low verse counts in: {', '.join(item['name'] for item in low_coverage)}"
            )

        with_incomplete = [item for item in coverage_summary if item["incomplete_surahs"] > 0 and not item.get("is_orphan")]
        if with_incomplete:
            recommendations.append(
                f"- Complete missing verses in: {', '.join(item['name'] for item in with_incomplete)}"
            )

        with_missing_surahs = [item for item in coverage_summary if item["missing_surahs"] > 0 and not item.get("is_orphan")]
        if with_missing_surahs:
            recommendations.append(
                f"- Add missing surahs for: {', '.join(item['name'] for item in with_missing_surahs)}"
            )

        if not recommendations:
            recommendations.append("- All coverage checks passed. No immediate action required.")

        for rec in recommendations:
            report.append(rec)
        report.append("")

        report.append("=" * 80)
        report.append("END OF REPORT")
        report.append("=" * 80)

        return "\n".join(report)

    def _format_verse_list(self, verses: List[int], max_display: int = 20) -> str:
        """Format a list of verses for display, condensing ranges."""
        if not verses:
            return "None"

        if len(verses) <= max_display:
            # Condense consecutive numbers into ranges
            ranges = []
            start = verses[0]
            end = verses[0]

            for v in verses[1:]:
                if v == end + 1:
                    end = v
                else:
                    ranges.append(f"{start}-{end}" if start != end else str(start))
                    start = v
                    end = v
            ranges.append(f"{start}-{end}" if start != end else str(start))

            return ", ".join(ranges)
        else:
            return f"{verses[0]}, {verses[1]}, ... ({len(verses)} total)"

    def validate(self) -> Tuple[bool, str]:
        """Run full validation and return success status and report."""
        try:
            self.connect()
            self.log("Connected to database")

            self.load_surahs()
            self.load_riwayat()
            self.load_qiraat_coverage()

            report = self.generate_report()

            # Determine overall success
            success = True
            for riwaya_id in self.qiraat_coverage:
                coverage = self.check_riwaya_coverage(riwaya_id)
                if coverage["missing_surahs"] or coverage["incomplete_surahs"]:
                    success = False
                    break
                if coverage["total_verses"] < ACCEPTABLE_VERSE_RANGE[0]:
                    success = False
                    break

            return success, report

        except Exception as e:
            error_msg = f"Validation error: {str(e)}"
            self.log(error_msg, "ERROR")
            return False, error_msg
        finally:
            self.close()


def main():
    """Main entry point."""
    print("Qiraat Coverage Validation Script")
    print("=" * 40)
    print()

    validator = QiraatCoverageValidator(DB_PATH)
    success, report = validator.validate()

    print()
    print(report)

    # Save report to file
    report_path = Path("/home/hesham-haroun/Quran/data/exports/qiraat_coverage_report.txt")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    print(f"\nReport saved to: {report_path}")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
