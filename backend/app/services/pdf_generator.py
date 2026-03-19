"""
ATS-friendly PDF resume generator using ReportLab.
Simple, clean formatting that passes ATS scanners.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.colors import HexColor


def generate_resume_pdf(content: str, output_path: str):
    """Generate an ATS-friendly PDF from text content."""
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    name_style = ParagraphStyle(
        "NameStyle",
        parent=styles["Title"],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=4,
        textColor=HexColor("#1a1a1a"),
    )

    contact_style = ParagraphStyle(
        "ContactStyle",
        parent=styles["Normal"],
        fontSize=10,
        alignment=TA_CENTER,
        spaceAfter=12,
        textColor=HexColor("#555555"),
    )

    section_style = ParagraphStyle(
        "SectionStyle",
        parent=styles["Heading2"],
        fontSize=12,
        spaceBefore=10,
        spaceAfter=4,
        textColor=HexColor("#2c3e50"),
        borderWidth=0,
        borderPadding=0,
    )

    body_style = ParagraphStyle(
        "BodyStyle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        spaceAfter=2,
    )

    bullet_style = ParagraphStyle(
        "BulletStyle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        leftIndent=15,
        spaceAfter=2,
        bulletIndent=5,
    )

    elements = []
    lines = content.strip().split("\n")

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            elements.append(Spacer(1, 4))
            continue

        # First non-empty line is the name
        if i == 0 or (i == 1 and not lines[0].strip()):
            elements.append(Paragraph(line, name_style))

        # Contact info (email, phone, linkedin — usually line 2)
        elif i <= 2 and ("@" in line or "linkedin" in line.lower() or "|" in line):
            elements.append(Paragraph(line, contact_style))

        # Section headers (ALL CAPS or known headings)
        elif line.isupper() or line.rstrip(":").upper() in {
            "PROFESSIONAL SUMMARY", "SUMMARY", "SKILLS", "TECHNICAL SKILLS",
            "EXPERIENCE", "WORK EXPERIENCE", "CERTIFICATIONS", "EDUCATION",
            "PROJECTS", "ACHIEVEMENTS",
        }:
            elements.append(Spacer(1, 6))
            elements.append(Paragraph(f"<b>{line.title()}</b>", section_style))

        # Bullet points
        elif line.startswith(("- ", "• ", "* ", "→ ")):
            bullet_text = line.lstrip("-•*→ ").strip()
            elements.append(Paragraph(f"• {bullet_text}", bullet_style))

        # Regular text
        else:
            elements.append(Paragraph(line, body_style))

    doc.build(elements)


def generate_cover_letter_pdf(content: str, output_path: str):
    """Generate a professional cover letter PDF."""
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=1 * inch,
        rightMargin=1 * inch,
        topMargin=1 * inch,
        bottomMargin=1 * inch,
    )

    styles = getSampleStyleSheet()

    body_style = ParagraphStyle(
        "CLBody",
        parent=styles["Normal"],
        fontSize=11,
        leading=16,
        spaceAfter=12,
    )

    elements = []
    paragraphs = content.strip().split("\n\n")

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # Handle single newlines within paragraphs
        para = para.replace("\n", "<br/>")
        elements.append(Paragraph(para, body_style))

    doc.build(elements)
