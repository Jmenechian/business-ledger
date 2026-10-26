"""Read-only statement rendering, matching the established compact green layout."""

from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from backend.models.report import Statement

GREEN = colors.Color(0.063, 0.486, 0.255)
PALE = colors.Color(0.973, 0.98, 0.973)
BLUE = colors.HexColor("#164dff")
MONTHS = ("Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic")
WIDTH = A4[0] - 2 * 28.35
COLUMNS = [39.69, 158.74, 56.69, 51.02, 62.36, 56.69, 56.69, WIDTH - 481.88]
FONT_DIRECTORY = Path(reportlab.__file__).parent / "fonts"
for font_name, font_file in (
    ("LedgerUnicode", "Vera.ttf"),
    ("LedgerUnicode-Bold", "VeraBd.ttf"),
    ("LedgerUnicode-Oblique", "VeraIt.ttf"),
):
    pdfmetrics.registerFont(TTFont(font_name, str(FONT_DIRECTORY / font_file)))


def display_text(text: str, font: str) -> tuple[str, str]:
    """Keep reference typography for Spanish; never silently print missing glyph boxes."""
    try:
        text.encode("cp1252")
        return text, font
    except UnicodeEncodeError:
        fallback = font.replace("Helvetica", "LedgerUnicode")
        supported = pdfmetrics.getFont(fallback).face.charWidths
        return "".join(
            char if char == "\n" or ord(char) in supported else f"[U+{ord(char):04X}]"
            for char in text
        ), fallback


def number(value: int | float) -> str:
    """Group decimal text without rounding preserved historical fractions."""
    decimal = Decimal(str(value))
    fixed = format(decimal, "f")
    integer, dot, fraction = fixed.partition(".")
    fraction = fraction.rstrip("0")
    grouped = format(int(integer), ",").replace(",", ".")
    if decimal < 0 and int(integer) == 0:
        grouped = "-" + grouped
    return grouped + ("," + fraction if dot and fraction else "")


def amount(value: int | float, *, dash_zero: bool = False) -> str:
    return "-" if dash_zero and value == 0 else "$ " + number(value)


def date_text(value: str | None) -> str:
    if not value:
        return "-"
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            return value
        return f"{parsed.day:02d}-{MONTHS[parsed.month - 1]}-{parsed.year:04d}"
    except ValueError:
        # Invalid historical text remains visible, never silently normalized.
        return value


def paragraph(text: str, *, align=TA_LEFT, font="Helvetica", size=8, color=colors.black):
    text, font = display_text(text, font)
    return Paragraph(
        escape(text).replace("\n", "<br/>"),
        ParagraphStyle(
            "statement",
            fontName=font,
            fontSize=size,
            leading=size + 2,
            alignment=align,
            textColor=color,
            splitLongWords=True,
        ),
    )


def render_statement(report: Statement) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=22.35,
        rightMargin=22.35,
        topMargin=22.35,
        bottomMargin=34,
        title="Resumen de cuenta corriente",
        author="Business Ledger",
        pageCompression=1,
    )
    banner = Table(
        [
            [
                paragraph(
                    report.client_name,
                    align=TA_CENTER,
                    font="Helvetica-Bold",
                    size=14,
                    color=colors.white,
                )
            ]
        ],
        colWidths=[WIDTH],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), GREEN),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 17.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 17.5),
            ]
        ),
    )
    local_day = report.generated_at.astimezone(ZoneInfo(report.timezone)).date().isoformat()
    story = [
        banner,
        Spacer(1, 12),
        paragraph(
            "Fecha de emisión: " + date_text(local_day),
            align=TA_RIGHT,
            font="Helvetica-Oblique",
            size=9,
            color=colors.HexColor("#555555"),
        ),
        Spacer(1, 5),
        paragraph(
            f"Movimientos {report.first_row_number} a {report.last_row_number}"
            f"  |  Saldo anterior: {amount(report.opening_balance)}",
            size=7,
            color=colors.HexColor("#555555"),
        ),
        Spacer(1, 5),
    ]
    headers = ("Cant", "Detalle", "P. Unit", "N° Rem", "Fecha", "Debe", "Haber", "Saldo")
    data = [
        [
            paragraph(text, align=TA_CENTER, font="Helvetica-Bold", color=colors.white)
            for text in headers
        ]
    ]
    for row in report.rows:
        price = "-" if row.precio_unitario is None else amount(row.precio_unitario)
        if row.price_is_derived:
            price += " *"
        values = [
            "-" if row.cant is None else number(row.cant),
            row.detalle,
            price,
            row.n_remito or "-",
            date_text(row.fecha),
            amount(row.debe, dash_zero=True),
            amount(row.haber, dash_zero=True),
            amount(row.saldo),
        ]
        payment = row.haber > 0 and row.debe == 0
        cells = []
        for column, text in enumerate(values):
            align = TA_LEFT if column == 1 else TA_CENTER if column in (0, 3, 4) else TA_RIGHT
            color = BLUE if payment and column != 7 else colors.HexColor("#111111")
            cell = paragraph(text, align=align, color=color)
            if column == 1:
                # Visible customer row numbering without adding an accounting column.
                cell = Paragraph(
                    f'<font size="6" color="#666666">#{row.number}</font>  '
                    + escape(display_text(text, "Helvetica")[0]).replace("\n", "<br/>"),
                    cell.style,
                )
            cells.append(cell)
        data.append(cells)
    table = Table(
        data,
        colWidths=COLUMNS,
        repeatRows=1,
        splitByRow=1,
        splitInRow=1,
        hAlign="LEFT",
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), GREEN),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#bfbfbf")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, 0), 5),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 5),
                ("TOPPADDING", (0, 1), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 3.5),
            ]
        ),
    )
    story.append(table)
    ending = [
        Spacer(1, 11),
        HRFlowable(width="100%", thickness=0.8, color=GREEN),
        Spacer(1, 12),
        paragraph(
            "SALDO FINAL: " + amount(report.final_balance),
            align=TA_RIGHT,
            font="Helvetica-Bold",
            size=11,
        ),
    ]
    if any(row.price_is_derived for row in report.rows):
        ending.extend(
            [
                Spacer(1, 7),
                paragraph(
                    "* Precio calculado desde Debe / Cant, redondeado a entero. "
                    "El historial se conserva.",
                    size=7,
                    color=colors.HexColor("#555555"),
                ),
            ]
        )
    source_texts = [report.client_name] + [
        text for row in report.rows for text in (row.detalle, row.n_remito or "", row.fecha or "")
    ]
    if any(display_text(text, "Helvetica")[0] != text for text in source_texts):
        ending.extend(
            [
                Spacer(1, 7),
                paragraph(
                    "Caracteres fuera de la fuente se indican por su código Unicode [U+...].",
                    size=7,
                    color=colors.HexColor("#555555"),
                ),
            ]
        )
    story.append(KeepTogether(ending))

    def page_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawRightString(A4[0] - 28.35, 18, f"Página {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=page_footer, onLaterPages=page_footer)
    return output.getvalue()
