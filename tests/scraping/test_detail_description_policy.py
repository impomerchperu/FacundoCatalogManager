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


def test_detail_policy_recognizes_laminator_and_printer_specific_labels():
    laminator = (
        "Número de rodillos: 2. Ancho de entrada: 330 mm. "
        "Espesor máximo de laminación: 0.5 mm. Soporta: 80 a 125 micrones. "
        "Tiempo de calentamiento: 3 a 5 minutos. "
        "Velocidad de laminación: 250 mm/min. "
        "Cortadora con 3 tipos de corte: Recto, Ondulado y Perforado."
    )
    printer = (
        "Tamaño de impresión (cm): 10 x 15. "
        "Rollos por caja: 2. Impresiones por rollo: 300. "
        "Válido para impresoras: CP-D90DW-P, CP-D80DW. "
        "Opciones de acabado: Brillante y mate."
    )

    assert has_multiple_technical_detail_fields(laminator)
    assert has_multiple_technical_detail_fields(printer)
    assert has_technical_detail(laminator)
    assert has_technical_detail(printer)

    legacy_fields = (
        "Medidas mochila: 30 x 25 cm. "
        "Tamaño cinta: 1 metro. "
        "Forro: Biocuero. "
        "Presentación del Estuche: Caja de cartón."
    )
    assert has_multiple_technical_detail_fields(legacy_fields)

    sublimation_fields = (
        "Medida y capacidad: 10.5 cm x 8.5 cm – 444 ml. "
        "Medida de impresión: 21 x 11 cm. "
        "Calidad: AAA, alta calidad. Material: Cerámica blanca."
    )
    assert has_multiple_technical_detail_fields(sublimation_fields)
    assert has_technical_detail(sublimation_fields)
    assert is_complete_detail(sublimation_fields)

    incomplete_box = "Medida: A4. Paquete: 20 Unidades. Caja:"
    assert normalize_detail_text(incomplete_box) == (
        "Medida: A4. Paquete: 20 Unidades"
    )
    assert is_complete_detail(incomplete_box)

def test_detail_policy_removes_inline_color_labels_from_flattened_card_text():
    assert normalize_detail_text(
        "Material: Poliuretano Color: Blanco. Presentación: Caja."
    ) == "Material: Poliuretano. Presentación: Caja."

    assert normalize_detail_text(
        "Material: PVC. Disponible en colores: Rojo, Azul. Presentación: Caja."
    ) == "Material: PVC. Presentación: Caja."


def test_detail_policy_preserves_color_of_printing_attribute():
    source = "Color de impresión: Una cara. Material: PVC."

    assert normalize_detail_text(source) == source

