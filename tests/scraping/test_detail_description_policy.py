from models.scraping.detail_description_policy import (
    has_multiple_technical_detail_fields,
    has_technical_detail,
    is_complete_detail,
    normalize_detail_text,
    strip_leading_color_field,
)

FB_4047_DETAIL = (
    "Material: Poliuretano. Dimensiones: 55*55*100mm. "
    "Peso Unitario: 24 G. Uso Recomendado: Antiestrés, Promocional. "
    "Empaque Individual: Bolsa de polietileno. Cantidad Por Caja: 250 Pza. "
    "Dimensiones Caja: 60*33*32cm. Cubicaje por Caja: 0.0634 m³/CBM "
    "Peso neto por caja: 7.5 Kg. Peso bruto por caja: 8.5 Kg. "
    "Leer Menos Certificado SGS"
)


def test_detail_policy_removes_color_line_and_preserves_technical_attributes():
    source = (
        "Color: Amarillo, Blanco. Material: Poliuretano. "
        "Dimensiones: 55*55*100mm."
    )
    expected = "Material: Poliuretano. Dimensiones: 55*55*100mm."

    assert normalize_detail_text(source) == expected
    assert strip_leading_color_field(source) == expected


def test_detail_policy_removes_color_lines_without_dropping_neighboring_fields():
    color_values = (
        "Colores Blanco",
        "Color Blanco.",
        "Colores disponibles: Amarillo, Blanco",
    )
    for value in color_values:
        normalized = normalize_detail_text(value)
        assert normalized == ""
        assert not has_technical_detail(normalized)
        assert not is_complete_detail(normalized)

    assert normalize_detail_text("Colores Blanco. Material: ABS.") == (
        "Material: ABS."
    )
    assert normalize_detail_text(
        "Material: ABS. Colores disponibles: Azul, Rojo. Presentación: Caja."
    ) == "Material: ABS. Presentación: Caja."
    assert normalize_detail_text(
        "Color de impresión: Una cara. Material: PVC."
    ) == "Color de impresión: Una cara. Material: PVC."


def test_detail_policy_detects_clipped_words_and_ellipsis():
    assert not is_complete_detail("Material: ABS. Peso brut")
    assert not is_complete_detail("Material: ABS. Peso bruto…")
    assert not is_complete_detail("Material: ABS. Dimens")
    assert not is_complete_detail("Material: ABS. Cantidad por caj...")


def test_detail_policy_accepts_complete_fb4047_technical_detail():
    assert has_technical_detail(FB_4047_DETAIL)
    assert is_complete_detail(FB_4047_DETAIL)
    assert normalize_detail_text(FB_4047_DETAIL) == FB_4047_DETAIL
    assert has_technical_detail("Certificado SGS")


def test_detail_policy_recognizes_laminator_fields_and_removes_bullets():
    source = (
        "• Función: Caliente / Frío • "
        "Rango de espesor Polaseal: 75 micras (005) / 125 micras (007) / "
        "250 micras (010) • Velocidad: 30 mm/min • "
        "Tiempo de calentamiento: 3-5 min • Consumo de energía: 400W • "
        "Voltaje: 220v"
    )
    expected = (
        "Función: Caliente / Frío "
        "Rango de espesor Polaseal: 75 micras (005) / 125 micras (007) / "
        "250 micras (010) Velocidad: 30 mm/min "
        "Tiempo de calentamiento: 3-5 min Consumo de energía: 400W "
        "Voltaje: 220v"
    )

    assert normalize_detail_text(source) == expected
    assert has_technical_detail(source)
    assert is_complete_detail(source)
    assert not is_complete_detail(
        "Función: Caliente / Frío. Tiempo de calentamiento"
    )


def test_detail_policy_strips_marketing_intro_but_keeps_labeled_attributes():
    source = (
        "Descripción comercial: Producto ideal para regalo. "
        "Contiene: Tapa. Presentación: Caja. "
        "Medidas del Estuche: 15 x 17 cm."
    )
    cleaned = (
        "Contiene: Tapa. Presentación: Caja. "
        "Medidas del Estuche: 15 x 17 cm."
    )

    assert normalize_detail_text(source) == cleaned
    assert has_technical_detail(cleaned)
    assert is_complete_detail(cleaned)
    assert not has_technical_detail(
        "Descripción comercial: ideal para regalo. "
        "Consulta las condiciones comerciales."
    )
    assert not has_technical_detail(
        "Información adicional: Material: acero. Potencia: 20 W."
    )
    assert has_multiple_technical_detail_fields(
        "Levantamiento de materiales: retirar vinilo. "
        "Proyectos de manualidades: uso general. "
        "Aplicaciones de vinilo: levantar y posicionar. "
        "Trabajo en scrapbooking: manipular adhesivos."
    )
    assert has_multiple_technical_detail_fields(
        "Calidad Superior: tinta de calidad. "
        "Compatibilidad Confiable: uso con impresoras. "
        "Procedencia Coreana: fabricación coreana. "
        "Facilidad de Uso: botella fácil de usar."
    )
    assert has_multiple_technical_detail_fields(
        "Ancho de Corte: 38 cm. Longitud de Corte: 3 m. "
        "Fuerza de Corte: 210 gf. Sistema de Motor: doble."
    )


def test_detail_policy_does_not_treat_general_prose_as_technical_detail():
    prose = (
        "Descripción comercial: ideal para regalo. "
        "Consulta las condiciones comerciales."
    )

    assert not has_technical_detail(prose)
