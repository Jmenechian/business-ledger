from dataclasses import replace
from datetime import UTC, datetime
from io import BytesIO

from pypdf import PdfReader

from backend.models.report import Statement, StatementRow
from backend.services.statement_pdf import date_text, number, render_statement


def synthetic_statement():
    rows = tuple(
        StatementRow(
            number=index + 2,
            movement_id=index + 800,
            origin="imported",
            detalle="Pago de ejemplo" if index == 0 else "Prendas de algodón · confección",
            cant=None if index == 0 else 16 + index,
            precio_unitario=None if index == 0 else 1300,
            price_is_derived=index == 2,
            n_remito=None,
            fecha="2026-10-13" if index == 0 else None,
            debe=0 if index == 0 else 20800,
            haber=44300 if index == 0 else 0,
            saldo=0 if index == 0 else index * 20800,
        )
        for index in range(6)
    )
    return Statement(
        client_id=123,
        client_name="CUENTA DE EJEMPLO",
        generated_at=datetime(2026, 10, 26, tzinfo=UTC),
        timezone="America/Buenos_Aires",
        first_row_number=2,
        last_row_number=7,
        opening_balance=44300,
        final_balance=104000,
        rows=rows,
    )


def test_statement_pdf_has_spanish_columns_preserved_context_and_escaped_text():
    report = synthetic_statement()
    report = replace(
        report,
        rows=(replace(report.rows[0], detalle="Texto <b>literal</b> & ñandú", saldo=-7.5),)
        + report.rows[1:],
    )
    content = render_statement(report)
    reader = PdfReader(BytesIO(content))
    assert len(reader.pages) == 1
    page = reader.pages[0]
    assert abs(float(page.mediabox.width) - 595.28) < 0.1
    assert abs(float(page.mediabox.height) - 841.89) < 0.1
    text = page.extract_text()
    for expected in [
        "CUENTA DE EJEMPLO",
        "Cant",
        "Detalle",
        "P. Unit",
        "N° Rem",
        "Fecha",
        "Debe",
        "Haber",
        "Saldo",
        "SALDO FINAL: $ 104.000",
        "$ -7,5",
        "Texto <b>literal</b> & ñandú",
        "13-Oct-2026",
        "Fecha de emisión: 25-Oct-2026",
    ]:
        assert expected in text
    for annotation in [
        "#2",
        "#800",
        "Movimientos",
        "Saldo anterior",
        "Precio calculado",
        "El historial se conserva",
        "Página",
        "*",
    ]:
        assert annotation not in text
    assert text.strip().endswith("SALDO FINAL: $ 104.000")


def test_long_statement_and_oversize_description_split_across_pages_without_truncation():
    report = synthetic_statement()
    huge_detail = "DESCRIPCIÓN LARGA ñ " * 550 + "FIN DEL DETALLE"
    rows = tuple(
        replace(
            report.rows[index % 6],
            number=index + 1,
            detalle=huge_detail if index == 0 else f"Producto sintético {index}",
        )
        for index in range(85)
    )
    report = replace(report, rows=rows, first_row_number=1, last_row_number=85)
    reader = PdfReader(BytesIO(render_statement(report)))
    assert len(reader.pages) > 3
    pages = [page.extract_text() for page in reader.pages]
    full_text = " ".join("\n".join(pages).split())
    assert "FIN DEL DETALLE" in full_text
    assert "Producto sintético 84" in full_text
    assert "SALDO FINAL: $ 104.000" in pages[-1]
    for text in pages:
        assert "Página" not in text
        # Each page containing table content repeats all eight column headers.
        if "Producto sintético" in text or "DESCRIPCIÓN" in text:
            assert "Cant" in text and "Haber" in text and "Saldo" in text


def test_historical_numbers_and_dates_are_not_rounded_or_normalized():
    assert number(9223372036854775807) == "9.223.372.036.854.775.807"
    assert number(-0.125) == "-0,125"
    assert number(8.25) == "8,25"
    assert date_text(None) == "-"
    assert date_text("2026-02-30") == "2026-02-30"
    assert date_text("sin fecha fiable") == "sin fecha fiable"
    assert date_text("2026-01-03") == "03-Ene-2026"


def test_unsupported_unicode_is_represented_explicitly_instead_of_missing_glyphs():
    report = synthetic_statement()
    report = replace(report, client_name="Cuenta \u4e2d \U0001f600")
    text = "\n".join(
        page.extract_text() for page in PdfReader(BytesIO(render_statement(report))).pages
    )
    assert "[U+4E2D]" in text
    assert "[U+1F600]" in text
    assert "código Unicode" not in text
