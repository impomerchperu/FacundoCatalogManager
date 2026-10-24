from models.scraping.detail_description_policy import (
    has_multiple_technical_detail_fields,
    has_technical_detail,
    is_complete_detail,
    is_valid_detail_content,
    normalize_detail_text,
    remove_incomplete_trailing_dimension_field,
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
    assert normalize_detail_text(
        "Color: Blanco. Descripción: Elegante. Contiene: Tapa."
    ) == "Descripción: Elegante. Contiene: Tapa."


def test_detail_policy_detects_clipped_words_and_ellipsis():
    assert not is_complete_detail("Material: ABS. Peso brut")
    assert not is_complete_detail("Material: ABS. Peso bruto…")
    assert not is_complete_detail("Material: ABS. Dimens")
    assert not is_complete_detail("Material: ABS. Cantidad por caj...")


def test_detail_policy_removes_only_incomplete_trailing_dimension_field():
    incomplete = (
        "Marca: Bright Office. Modelo: 230.\n"
        "Dimensiones del producto: 410 \u00d7 208 \u00d7"
    )
    cleaned = "Marca: Bright Office. Modelo: 230."
    complete = (
        "Marca: Bright Office. Modelo: 230. "
        "Dimensiones del producto: 410 x 208 x 110 mm."
    )
    only_incomplete = "Dimensiones del producto: 410 x 208 x"

    assert remove_incomplete_trailing_dimension_field(incomplete) == cleaned
    assert remove_incomplete_trailing_dimension_field(complete) == complete
    assert (
        remove_incomplete_trailing_dimension_field(only_incomplete)
        == only_incomplete
    )


def test_detail_policy_rejects_incomplete_trailing_product_dimensions():
    incomplete = (
        "Marca: Bright Office. Modelo: 230. "
        "Dimensiones del producto: 410 \u00d7 208 \u00d7"
    )
    complete = (
        "Marca: Bright Office. Modelo: 230. "
        "Dimensiones del producto: 410 x 208 x 110 mm."
    )

    assert has_technical_detail(incomplete)
    assert not is_complete_detail(incomplete)
    assert not is_valid_detail_content(incomplete)
    assert is_complete_detail(complete)
    assert is_valid_detail_content(complete)
    assert not is_complete_detail("Dimensiones del producto:")


def test_detail_policy_recognizes_product_dimensions_and_box_weight_labels():
    source = (
        "Dimensiones del producto: 500 x 240 x 105 mm\n"
        "Peso bruto / caja: 18 kg / Peso neto / caja: 16 kg\n"
        "Medidas de la caja máster: 56.5 x 30 x 32.5 cm"
    )

    assert has_technical_detail(source)
    assert is_complete_detail(source)
    assert is_valid_detail_content(source)
    assert has_multiple_technical_detail_fields(source)


def test_detail_policy_normalizes_nonbreaking_space_indentation():
    source = (
        "\u00a0Dimensiones del producto: 500 x 240 x 105 mm\n"
        "\u00a0Peso bruto / caja: 18 kg\n"
        "\u00a0Medidas de la caja máster: 56.5 x 30 x 32.5 cm"
    )

    assert normalize_detail_text(source, preserve_boundaries=True).splitlines() == [
        "Dimensiones del producto: 500 x 240 x 105 mm",
        "Peso bruto / caja: 18 kg",
        "Medidas de la caja máster: 56.5 x 30 x 32.5 cm",
    ]


def test_detail_policy_recognizes_printing_technique():
    source = (
        "Medida: 20 x 20 cm. Material: Neopreno para sublimación. "
        "Técnica de impresión: Sublimación "
        "(área de impresión recomendada: 21 x 21 cm)"
    )

    assert has_technical_detail(source)
    assert is_complete_detail(source)
    assert is_valid_detail_content(source)


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


def test_detail_policy_preserves_summary_description_and_labeled_attributes():
    source = (
        "Descripción: Elegante y funcional. Color: Blanco. "
        "Contiene: Tapa. Presentación: Caja. "
        "Medidas del Estuche: 15 x 17 cm."
    )
    cleaned = (
        "Descripción: Elegante y funcional. Contiene: Tapa. "
        "Presentación: Caja. Medidas del Estuche: 15 x 17 cm."
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
        "Medida y capacidad: 10.5 cm x 8.5 cm \u2013 444 ml. "
        "Medida de impresión: 21 x 11 cm. "
        "Calidad: AAA, alta calidad. Material: Cerámica blanca."
    )
    assert has_multiple_technical_detail_fields(sublimation_fields)
    assert has_technical_detail(sublimation_fields)
    assert is_complete_detail(sublimation_fields)

    incomplete_box = "Medida: A4. Paquete: 20 Unidades. Caja:"
    assert normalize_detail_text(incomplete_box) == (
        "Medida: A4. Paquete: 20 Unidades. Caja:"
    )
    assert is_complete_detail(incomplete_box)
    assert is_valid_detail_content(incomplete_box)
    assert not is_complete_detail("Caja:")
    assert not is_valid_detail_content("Caja:")
    assert normalize_detail_text(
        "Medida: A4. Paquete: 20 Unidades. Caja: 100 unidades."
    ) == "Medida: A4. Paquete: 20 Unidades. Caja: 100 unidades."

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


def test_detail_policy_does_not_truncate_color_list_inside_description_value():
    source = (
        "Descripción: Resaltadores en 5 colores: Fucsia, Naranja, "
        "Amarillo, Verde y Celeste. Dentro de un pote. "
        "Material: Plástico. Presentación: Bolsa plástica."
    )

    assert normalize_detail_text(source) == source
    assert normalize_detail_text(
        "Material: Plástico. Colores disponibles: Fucsia, Verde. "
        "Presentación: Bolsa plástica."
    ) == "Material: Plástico. Presentación: Bolsa plástica."

def test_detail_policy_preserves_summary_description_while_removing_only_color():
    source = (
        "Descripción: Elegante y funcional set. "
        "Color: Blanco. Contiene: Sacacorchos. "
        "Presentación: Caja de cartón Blanca. "
        "Medidas del Estuche: 15 cm x 17 cm x 4.5 cm."
    )
    assert normalize_detail_text(source) == (
        "Descripción: Elegante y funcional set. "
        "Contiene: Sacacorchos. "
        "Presentación: Caja de cartón Blanca. "
        "Medidas del Estuche: 15 cm x 17 cm x 4.5 cm."
    )


def test_detail_policy_accepts_visible_summary_prose_but_rejects_color_only_text():
    assert is_valid_detail_content(
        "Nuestra cinta térmica se adhiere de manera segura y resiste el calor."
    )
    assert is_valid_detail_content(
        "Descripción: Elegante y funcional set. Contiene: Sacacorchos."
    )
    assert not is_valid_detail_content("Colores: Blanco, Rojo.")
    assert not is_valid_detail_content("Precio muestra: S/ 6.00")


def test_size_label_is_valid_technical_detail():
    from models.scraping.detail_description_policy import (
        has_technical_detail,
        is_complete_detail,
        is_valid_detail_content,
    )

    detail = (
        "Tamaño: 15 x 20 cm "
        "Medida de impresión: 30 x 20cm "
        "Material: Piedra"
    )

    assert has_technical_detail(detail)
    assert is_complete_detail(detail)
    assert is_valid_detail_content(detail)


def test_detail_policy_repairs_double_period_without_hiding_truncation():
    source = (
        "Descripción: Llavero circular de metal sublimable. "
        "Material: Metal con placa sublimable.. "
        "Medida: Aprox. 4 cm de diámetro. "
        "Presentación: Bolsa plástica transparente."
    )
    expected = (
        "Descripción: Llavero circular de metal sublimable. "
        "Material: Metal con placa sublimable. "
        "Medida: Aprox. 4 cm de diámetro. "
        "Presentación: Bolsa plástica transparente."
    )

    assert normalize_detail_text(source) == expected
    assert is_complete_detail(source)
    assert is_valid_detail_content(source)
    assert not is_complete_detail("Material: ABS...")
    assert not is_complete_detail("Material: ABS. Peso bruto…")



def test_detail_policy_keeps_usage_ideal_after_removing_available_colors():
    source = (
        "Colores disponibles: Azul, Negro. "
        "Uso ideal: Escritorio y oficina. "
        "Presentación: Individual, bolsa plástica."
    )

    assert normalize_detail_text(source) == (
        "Uso ideal: Escritorio y oficina. "
        "Presentación: Individual, bolsa plástica."
    )


def test_detail_policy_preserves_color_enumeration_inside_highlighter_description():
    source = (
        "Descripción: Resaltador con 5 puntas. "
        "Colores anaranjado, Verde, Amarillo, Turqueza y Rosado. "
        "Presentación: Individual, en bolsa de plástico transparente."
    )

    assert normalize_detail_text(source) == source
    assert is_complete_detail(source)


def test_detail_policy_preserves_color_of_ink_and_strips_only_variant_colors():
    source = (
        "Colores: Rojo, Negro, Azul. "
        "Color de tinta: Líquida color negro. "
        "Presentación: Bolsa plástica transparente."
    )

    assert normalize_detail_text(source) == (
        "Color de tinta: Líquida color negro. "
        "Presentación: Bolsa plástica transparente."
    )


def test_detail_policy_recognizes_application_shape_date_cutting_and_binding_fields():
    source = (
        "Técnica de aplicación: Serigrafía. Forma: Rectángulo. "
        "Fecha: 2026 \u2013 2027. Tipo de corte: Manual. "
        "Capacidad de corte: 12 hojas. "
        "Tamaño de corte máximo: A3. "
        "Tipo de encuadernado: Espiral simple. "
        "Capacidad de encuadernado: 450 hojas. "
        "Color de tinta: Líquida color negro. Uso ideal: Oficina."
    )

    assert has_technical_detail(source)
    assert is_complete_detail(source)
    assert is_valid_detail_content(source)



def test_detail_policy_removes_price_includes_igv_for_every_product():
    assert normalize_detail_text(
        "Material: Metal. Precio incluye IGV. Presentación: Bolsa plástica."
    ) == "Material: Metal. Presentación: Bolsa plástica."
    assert normalize_detail_text(
        "Presentación: Bolsa plástica, precio incluye IGV."
    ) == "Presentación: Bolsa plástica"
    assert normalize_detail_text("Precio incluye IGV.") == ""


def test_detail_policy_can_preserve_source_field_boundaries_for_alignment():
    source = (
        "Tipo de encuadernado: Espiral simple (tipo coil) \u241e "
        "Hasta 12 hojas (70 g/m²) por pasada \u241e "
        "Capacidad de encuadernado: Hasta 450 hojas"
    )
    assert normalize_detail_text(source) == (
        "Tipo de encuadernado: Espiral simple (tipo coil) "
        "Hasta 12 hojas (70 g/m²) por pasada "
        "Capacidad de encuadernado: Hasta 450 hojas"
    )
    assert normalize_detail_text(
        source,
        preserve_boundaries=True,
    ).splitlines() == [
        "Tipo de encuadernado: Espiral simple (tipo coil)",
        "Hasta 12 hojas (70 g/m²) por pasada",
        "Capacidad de encuadernado: Hasta 450 hojas",
    ]



def test_detail_policy_removes_invisible_direction_marks_from_field_values():
    assert normalize_detail_text("Forma: \u200eRectángulo") == "Forma: Rectángulo"
    assert normalize_detail_text(
        "Forma: \u200eRectángulo",
        preserve_boundaries=True,
    ) == "Forma: Rectángulo"
