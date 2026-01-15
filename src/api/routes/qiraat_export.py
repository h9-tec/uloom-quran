"""
Qiraat Export API routes - تصدير بيانات القراءات
Export functionality for Quranic readings (القراءات)
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Optional
import csv
import io
import json
from datetime import datetime

from ..database import get_db, dict_from_row

# Try to import reportlab for PDF generation
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

router = APIRouter(prefix="/api/qiraat/export", tags=["Qiraat Export"])


# ============================================================================
# Helper Functions
# ============================================================================

def get_riwayat_list(cursor):
    """Get all riwayat from database"""
    cursor.execute("""
        SELECT id, code, name_arabic, name_english
        FROM riwayat
        ORDER BY id
    """)
    return [dict_from_row(row) for row in cursor.fetchall()]


def get_surah_info(cursor, surah_id: int):
    """Get surah information"""
    cursor.execute("""
        SELECT id, name_arabic, name_english, ayah_count, revelation_type
        FROM surahs WHERE id = ?
    """, (surah_id,))
    row = cursor.fetchone()
    return dict_from_row(row) if row else None


def get_verse_info(cursor, surah_id: int, ayah_number: int):
    """Get verse information"""
    cursor.execute("""
        SELECT v.id, v.verse_key, v.text_uthmani, s.name_arabic as surah_name,
               s.name_english as surah_name_english
        FROM verses v
        JOIN surahs s ON v.surah_id = s.id
        WHERE v.surah_id = ? AND v.ayah_number = ?
    """, (surah_id, ayah_number))
    row = cursor.fetchone()
    return dict_from_row(row) if row else None


# ============================================================================
# JSON Export Endpoint
# ============================================================================

@router.get("/json")
def export_qiraat_json(
    surah: int = Query(..., ge=1, le=114, description="Surah number (1-114)")
):
    """
    Export all 8 qiraat texts for a surah as JSON

    Returns complete text of the surah in all available riwayat (transmissions),
    including Hafs, Warsh, Qaloon, Shouba, Doori, Soosi, Bazzi, and Qumbul.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Verify surah exists
        surah_info = get_surah_info(cursor, surah)
        if not surah_info:
            raise HTTPException(status_code=404, detail=f"Surah {surah} not found")

        # Get all riwayat
        riwayat = get_riwayat_list(cursor)

        # Get all verses for each riwaya
        export_data = {
            "metadata": {
                "surah": surah_info,
                "export_date": datetime.now().isoformat(),
                "total_riwayat": len(riwayat),
                "format": "JSON"
            },
            "riwayat": {}
        }

        for riwaya in riwayat:
            cursor.execute("""
                SELECT qt.ayah_number, qt.text_uthmani, qt.text_simple, qt.juz, qt.page
                FROM qiraat_texts qt
                WHERE qt.riwaya_id = ? AND qt.surah_id = ?
                ORDER BY qt.ayah_number
            """, (riwaya['id'], surah))

            verses = []
            for row in cursor.fetchall():
                verse = dict_from_row(row)
                verse['verse_key'] = f"{surah}:{verse['ayah_number']}"
                verses.append(verse)

            export_data["riwayat"][riwaya['code']] = {
                "riwaya_info": riwaya,
                "verses": verses,
                "verse_count": len(verses)
            }

        # Return as downloadable JSON file
        json_content = json.dumps(export_data, ensure_ascii=False, indent=2)

        return StreamingResponse(
            io.BytesIO(json_content.encode('utf-8')),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=qiraat_surah_{surah}.json"
            }
        )


# ============================================================================
# CSV Export Endpoint - Differences
# ============================================================================

@router.get("/csv/differences")
def export_differences_csv(
    surah: Optional[int] = Query(default=None, ge=1, le=114, description="Filter by surah number"),
    difference_type: Optional[str] = Query(default=None, description="Filter by difference type")
):
    """
    Export differences between readings as CSV

    Exports all documented reading differences (qiraat variants) across
    the Quran or for a specific surah, showing how each riwaya reads
    differently at specific words or phrases.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Build query for differences
        query = """
            SELECT qd.id, qd.surah_id, s.name_arabic as surah_name, s.name_english as surah_name_english,
                   qd.ayah_number, qd.word_position, qd.word_text, qd.difference_type, qd.description
            FROM qiraat_differences qd
            JOIN surahs s ON qd.surah_id = s.id
            WHERE 1=1
        """
        params = []

        if surah:
            query += " AND qd.surah_id = ?"
            params.append(surah)

        if difference_type:
            query += " AND qd.difference_type = ?"
            params.append(difference_type)

        query += " ORDER BY qd.surah_id, qd.ayah_number, qd.word_position"

        cursor.execute(query, params)
        differences = cursor.fetchall()

        if not differences:
            raise HTTPException(
                status_code=404,
                detail="No differences found matching the criteria"
            )

        # Get all riwayat for column headers
        riwayat = get_riwayat_list(cursor)
        riwayat_codes = [r['code'] for r in riwayat]

        # Create CSV output
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_ALL)

        # Write header
        header = [
            'difference_id', 'surah_id', 'surah_name_arabic', 'surah_name_english',
            'ayah_number', 'verse_key', 'word_position', 'word_text',
            'difference_type', 'description'
        ] + [f'reading_{code}' for code in riwayat_codes]
        writer.writerow(header)

        # Write data rows
        for diff_row in differences:
            diff = dict_from_row(diff_row)
            diff_id = diff['id']
            verse_key = f"{diff['surah_id']}:{diff['ayah_number']}"

            # Get readings for this difference
            cursor.execute("""
                SELECT qdr.riwaya_id, r.code, qdr.reading_text
                FROM qiraat_difference_readings qdr
                JOIN riwayat r ON qdr.riwaya_id = r.id
                WHERE qdr.difference_id = ?
            """, (diff_id,))

            readings_map = {row[1]: row[2] for row in cursor.fetchall()}

            row_data = [
                diff['id'],
                diff['surah_id'],
                diff['surah_name'],
                diff['surah_name_english'],
                diff['ayah_number'],
                verse_key,
                diff['word_position'],
                diff['word_text'],
                diff['difference_type'] or '',
                diff['description'] or ''
            ]

            # Add reading for each riwaya
            for code in riwayat_codes:
                row_data.append(readings_map.get(code, ''))

            writer.writerow(row_data)

        # Prepare response
        output.seek(0)
        csv_content = output.getvalue()

        filename = "qiraat_differences"
        if surah:
            filename += f"_surah_{surah}"
        if difference_type:
            filename += f"_{difference_type}"
        filename += ".csv"

        # Return with BOM for Excel compatibility with Arabic
        csv_bytes = ('\ufeff' + csv_content).encode('utf-8')

        return StreamingResponse(
            io.BytesIO(csv_bytes),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )


# ============================================================================
# PDF Export Endpoint - Side-by-Side Comparison
# ============================================================================

@router.get("/comparison")
def export_comparison_pdf(
    verse: str = Query(..., description="Verse key in format 'surah:ayah' (e.g., '1:4')")
):
    """
    Export side-by-side comparison of a verse as PDF

    Creates a PDF document showing how each of the 8 riwayat reads
    a specific verse, formatted in a side-by-side comparison table.
    """
    if not REPORTLAB_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="PDF generation requires reportlab. Install with: pip install reportlab"
        )

    # Parse verse key
    try:
        parts = verse.split(":")
        surah_id = int(parts[0])
        ayah_number = int(parts[1])
    except (ValueError, IndexError):
        raise HTTPException(
            status_code=400,
            detail="Invalid verse key format. Use format 'surah:ayah' (e.g., '1:4')"
        )

    with get_db() as conn:
        cursor = conn.cursor()

        # Get verse info
        verse_info = get_verse_info(cursor, surah_id, ayah_number)
        if not verse_info:
            raise HTTPException(status_code=404, detail="Verse not found")

        # Get all riwayat texts for this verse
        cursor.execute("""
            SELECT r.id, r.code, r.name_arabic, r.name_english,
                   qt.text_uthmani, qt.text_simple
            FROM riwayat r
            LEFT JOIN qiraat_texts qt ON r.id = qt.riwaya_id
                AND qt.surah_id = ? AND qt.ayah_number = ?
            ORDER BY r.id
        """, (surah_id, ayah_number))

        readings = [dict_from_row(row) for row in cursor.fetchall()]

        # Get differences for this verse
        cursor.execute("""
            SELECT qd.id, qd.word_position, qd.word_text, qd.difference_type, qd.description
            FROM qiraat_differences qd
            WHERE qd.surah_id = ? AND qd.ayah_number = ?
        """, (surah_id, ayah_number))

        differences = []
        for diff_row in cursor.fetchall():
            diff = dict_from_row(diff_row)

            # Get readings for this difference
            cursor.execute("""
                SELECT qdr.riwaya_id, r.code, r.name_arabic, qdr.reading_text
                FROM qiraat_difference_readings qdr
                JOIN riwayat r ON qdr.riwaya_id = r.id
                WHERE qdr.difference_id = ?
                ORDER BY r.id
            """, (diff['id'],))
            diff['readings'] = [dict_from_row(r) for r in cursor.fetchall()]
            differences.append(diff)

    # Generate PDF
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=landscape(A4),
        rightMargin=1*cm,
        leftMargin=1*cm,
        topMargin=1*cm,
        bottomMargin=1*cm
    )

    # Styles
    styles = getSampleStyleSheet()

    # Create RTL style for Arabic text
    arabic_style = ParagraphStyle(
        'Arabic',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=14,
        alignment=TA_RIGHT,
        leading=20,
        wordWrap='RTL'
    )

    title_style = ParagraphStyle(
        'Title',
        parent=styles['Title'],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=20
    )

    header_style = ParagraphStyle(
        'Header',
        parent=styles['Heading2'],
        fontSize=12,
        alignment=TA_CENTER,
        spaceAfter=10
    )

    # Build document content
    elements = []

    # Title
    title_text = f"Qiraat Comparison - {verse_info['surah_name']} ({verse_info['verse_key']})"
    elements.append(Paragraph(title_text, title_style))
    elements.append(Spacer(1, 0.5*cm))

    # Verse info section
    info_text = f"""
    <b>Surah:</b> {verse_info['surah_name']} ({verse_info['surah_name_english']})<br/>
    <b>Verse:</b> {verse_info['verse_key']}<br/>
    <b>Uthmani Text:</b> {verse_info['text_uthmani']}
    """
    elements.append(Paragraph(info_text, styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))

    # Readings comparison table
    elements.append(Paragraph("All Riwayat Readings", header_style))

    # Build table data
    table_data = [['Riwaya (Arabic)', 'Riwaya (English)', 'Code', 'Text']]

    for reading in readings:
        text = reading['text_uthmani'] or reading['text_simple'] or 'N/A'
        table_data.append([
            reading['name_arabic'] or '',
            reading['name_english'] or '',
            reading['code'] or '',
            text
        ])

    # Create table
    col_widths = [3*cm, 4*cm, 2*cm, 15*cm]
    table = Table(table_data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (3, 1), (3, -1), 'RIGHT'),  # RTL for Arabic text column
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 1*cm))

    # Differences section
    if differences:
        elements.append(Paragraph("Documented Differences", header_style))

        for i, diff in enumerate(differences, 1):
            diff_info = f"""
            <b>Difference {i}:</b><br/>
            <b>Word:</b> {diff['word_text'] or 'N/A'}<br/>
            <b>Position:</b> {diff['word_position'] or 'N/A'}<br/>
            <b>Type:</b> {diff['difference_type'] or 'N/A'}<br/>
            <b>Description:</b> {diff['description'] or 'N/A'}
            """
            elements.append(Paragraph(diff_info, styles['Normal']))

            if diff['readings']:
                diff_table_data = [['Riwaya', 'Reading Text']]
                for r in diff['readings']:
                    diff_table_data.append([
                        f"{r['name_arabic']} ({r['code']})",
                        r['reading_text'] or ''
                    ])

                diff_table = Table(diff_table_data, colWidths=[6*cm, 12*cm])
                diff_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                ]))
                elements.append(diff_table)
                elements.append(Spacer(1, 0.5*cm))
    else:
        elements.append(Paragraph("No documented differences for this verse.", styles['Normal']))

    # Export timestamp
    elements.append(Spacer(1, 1*cm))
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elements.append(Paragraph(f"<i>Generated on: {timestamp}</i>", styles['Normal']))

    # Build PDF
    doc.build(elements)
    pdf_buffer.seek(0)

    filename = f"qiraat_comparison_{surah_id}_{ayah_number}.pdf"

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )


# ============================================================================
# Individual Surah Export with All Readings
# ============================================================================

@router.get("/surah/{surah_id}")
def export_surah_all_readings(
    surah_id: int,
    format: str = Query(default="json", description="Export format: json, csv")
):
    """
    Export individual surah with all readings

    Exports the complete text of a surah showing all 8 riwayat readings
    for each verse, along with any documented differences.
    """
    if surah_id < 1 or surah_id > 114:
        raise HTTPException(status_code=400, detail="Surah ID must be between 1 and 114")

    with get_db() as conn:
        cursor = conn.cursor()

        # Get surah info
        surah_info = get_surah_info(cursor, surah_id)
        if not surah_info:
            raise HTTPException(status_code=404, detail=f"Surah {surah_id} not found")

        # Get all riwayat
        riwayat = get_riwayat_list(cursor)

        # Get all verses for this surah
        cursor.execute("""
            SELECT ayah_number, text_uthmani
            FROM verses
            WHERE surah_id = ?
            ORDER BY ayah_number
        """, (surah_id,))
        verses = cursor.fetchall()

        if format.lower() == "csv":
            return _export_surah_csv(cursor, surah_id, surah_info, riwayat, verses)
        else:
            return _export_surah_json(cursor, surah_id, surah_info, riwayat, verses)


def _export_surah_json(cursor, surah_id, surah_info, riwayat, verses):
    """Export surah data as JSON"""
    export_data = {
        "metadata": {
            "surah": surah_info,
            "export_date": datetime.now().isoformat(),
            "total_verses": len(verses),
            "total_riwayat": len(riwayat),
            "format": "JSON"
        },
        "verses": []
    }

    for verse_row in verses:
        ayah_number = verse_row[0]
        verse_key = f"{surah_id}:{ayah_number}"

        verse_data = {
            "verse_key": verse_key,
            "ayah_number": ayah_number,
            "text_uthmani": verse_row[1],
            "readings": {},
            "differences": []
        }

        # Get readings for each riwaya
        for riwaya in riwayat:
            cursor.execute("""
                SELECT text_uthmani, text_simple, juz, page
                FROM qiraat_texts
                WHERE riwaya_id = ? AND surah_id = ? AND ayah_number = ?
            """, (riwaya['id'], surah_id, ayah_number))

            reading_row = cursor.fetchone()
            if reading_row:
                verse_data["readings"][riwaya['code']] = {
                    "text_uthmani": reading_row[0],
                    "text_simple": reading_row[1],
                    "juz": reading_row[2],
                    "page": reading_row[3]
                }

        # Get differences for this verse
        cursor.execute("""
            SELECT qd.id, qd.word_position, qd.word_text, qd.difference_type, qd.description
            FROM qiraat_differences qd
            WHERE qd.surah_id = ? AND qd.ayah_number = ?
        """, (surah_id, ayah_number))

        for diff_row in cursor.fetchall():
            diff = dict_from_row(diff_row)

            # Get readings for this difference
            cursor.execute("""
                SELECT r.code, qdr.reading_text
                FROM qiraat_difference_readings qdr
                JOIN riwayat r ON qdr.riwaya_id = r.id
                WHERE qdr.difference_id = ?
            """, (diff['id'],))

            diff['variant_readings'] = {row[0]: row[1] for row in cursor.fetchall()}
            verse_data["differences"].append(diff)

        export_data["verses"].append(verse_data)

    # Return as downloadable JSON
    json_content = json.dumps(export_data, ensure_ascii=False, indent=2)

    return StreamingResponse(
        io.BytesIO(json_content.encode('utf-8')),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=surah_{surah_id}_all_readings.json"
        }
    )


def _export_surah_csv(cursor, surah_id, surah_info, riwayat, verses):
    """Export surah data as CSV"""
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)

    riwayat_codes = [r['code'] for r in riwayat]

    # Write header
    header = ['verse_key', 'ayah_number', 'text_uthmani_standard']
    header.extend([f'text_{code}' for code in riwayat_codes])
    header.append('has_differences')
    writer.writerow(header)

    # Write data
    for verse_row in verses:
        ayah_number = verse_row[0]
        verse_key = f"{surah_id}:{ayah_number}"

        row_data = [verse_key, ayah_number, verse_row[1]]

        # Get readings for each riwaya
        for riwaya in riwayat:
            cursor.execute("""
                SELECT text_uthmani
                FROM qiraat_texts
                WHERE riwaya_id = ? AND surah_id = ? AND ayah_number = ?
            """, (riwaya['id'], surah_id, ayah_number))

            reading_row = cursor.fetchone()
            row_data.append(reading_row[0] if reading_row else '')

        # Check for differences
        cursor.execute("""
            SELECT COUNT(*) FROM qiraat_differences
            WHERE surah_id = ? AND ayah_number = ?
        """, (surah_id, ayah_number))
        diff_count = cursor.fetchone()[0]
        row_data.append('Yes' if diff_count > 0 else 'No')

        writer.writerow(row_data)

    # Prepare response with BOM for Excel compatibility
    output.seek(0)
    csv_bytes = ('\ufeff' + output.getvalue()).encode('utf-8')

    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=surah_{surah_id}_all_readings.csv"
        }
    )


# ============================================================================
# Bulk Export - All Differences
# ============================================================================

@router.get("/all-differences")
def export_all_differences():
    """
    Export all qiraat differences across the entire Quran

    Creates a comprehensive export of all documented reading differences,
    organized by surah and verse.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        # Get all differences with surah info
        cursor.execute("""
            SELECT qd.id, qd.surah_id, s.name_arabic, s.name_english,
                   qd.ayah_number, qd.word_position, qd.word_text,
                   qd.difference_type, qd.description
            FROM qiraat_differences qd
            JOIN surahs s ON qd.surah_id = s.id
            ORDER BY qd.surah_id, qd.ayah_number, qd.word_position
        """)

        differences = []
        for diff_row in cursor.fetchall():
            diff = dict_from_row(diff_row)

            # Get readings for this difference
            cursor.execute("""
                SELECT r.code, r.name_arabic, r.name_english, qdr.reading_text
                FROM qiraat_difference_readings qdr
                JOIN riwayat r ON qdr.riwaya_id = r.id
                WHERE qdr.difference_id = ?
                ORDER BY r.id
            """, (diff['id'],))

            diff['readings'] = [dict_from_row(r) for r in cursor.fetchall()]
            diff['verse_key'] = f"{diff['surah_id']}:{diff['ayah_number']}"
            differences.append(diff)

        # Group by surah
        by_surah = {}
        for diff in differences:
            sid = diff['surah_id']
            if sid not in by_surah:
                by_surah[sid] = {
                    "surah_id": sid,
                    "surah_name_arabic": diff['name_arabic'],
                    "surah_name_english": diff['name_english'],
                    "differences": []
                }
            by_surah[sid]['differences'].append(diff)

        export_data = {
            "metadata": {
                "export_date": datetime.now().isoformat(),
                "total_differences": len(differences),
                "surahs_with_differences": len(by_surah),
                "format": "JSON"
            },
            "surahs": list(by_surah.values())
        }

        json_content = json.dumps(export_data, ensure_ascii=False, indent=2)

        return StreamingResponse(
            io.BytesIO(json_content.encode('utf-8')),
            media_type="application/json",
            headers={
                "Content-Disposition": "attachment; filename=qiraat_all_differences.json"
            }
        )


# ============================================================================
# Export Statistics
# ============================================================================

@router.get("/stats")
def get_export_stats():
    """
    Get statistics about available qiraat data for export

    Returns counts and coverage information to help users understand
    what data is available for export.
    """
    with get_db() as conn:
        cursor = conn.cursor()

        stats = {
            "riwayat": [],
            "coverage": {},
            "differences": {}
        }

        # Get riwayat info
        cursor.execute("""
            SELECT r.id, r.code, r.name_arabic, r.name_english,
                   (SELECT COUNT(*) FROM qiraat_texts WHERE riwaya_id = r.id) as text_count
            FROM riwayat r
            ORDER BY r.id
        """)
        stats["riwayat"] = [dict_from_row(row) for row in cursor.fetchall()]

        # Total texts
        cursor.execute("SELECT COUNT(*) FROM qiraat_texts")
        stats["coverage"]["total_texts"] = cursor.fetchone()[0]

        # Total differences
        cursor.execute("SELECT COUNT(*) FROM qiraat_differences")
        stats["differences"]["total"] = cursor.fetchone()[0]

        # Differences by type
        cursor.execute("""
            SELECT difference_type, COUNT(*) as count
            FROM qiraat_differences
            GROUP BY difference_type
        """)
        stats["differences"]["by_type"] = {
            row[0] or 'unspecified': row[1] for row in cursor.fetchall()
        }

        # Surahs with differences
        cursor.execute("""
            SELECT COUNT(DISTINCT surah_id) FROM qiraat_differences
        """)
        stats["differences"]["surahs_with_differences"] = cursor.fetchone()[0]

        # Export formats available
        stats["available_formats"] = {
            "json": True,
            "csv": True,
            "pdf": REPORTLAB_AVAILABLE
        }

        if not REPORTLAB_AVAILABLE:
            stats["pdf_notice"] = "PDF export requires reportlab. Install with: pip install reportlab"

        return stats
