from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
NS_MC = "http://schemas.openxmlformats.org/markup-compatibility/2006"
NS_X14 = "http://schemas.microsoft.com/office/spreadsheetml/2009/9/main"
NS_X15 = "http://schemas.microsoft.com/office/spreadsheetml/2010/11/main"
NS_XR10 = "http://schemas.microsoft.com/office/spreadsheetml/2016/revision10"
NS_SLE = "http://schemas.microsoft.com/office/drawing/2010/slicer"
NS_SLE15 = "http://schemas.microsoft.com/office/drawing/2012/slicer"
NS_XDR = "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing"
NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"

URI_SLICER_CACHE_DEFINITION = "{2F2917AC-EB37-4324-AD4E-5DD8C200BD13}"
URI_SLICER_CACHES_X15 = "{46BE6895-7355-4A93-B00E-2C351335B9C9}"
URI_SLICER_LIST_X15 = "{3A4CF648-6AED-40F4-86FF-DC5316D8AED3}"
REL_DRAWING = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/drawing"
REL_SLICER_CACHE = (
    "http://schemas.microsoft.com/office/2007/relationships/slicerCache"
)
REL_SLICER = "http://schemas.microsoft.com/office/2007/relationships/slicer"
CONTENT_TYPE_DRAWING = (
    "application/vnd.openxmlformats-officedocument.drawing+xml"
)
CONTENT_TYPE_SLICER_CACHE = "application/vnd.ms-excel.slicerCache+xml"
CONTENT_TYPE_SLICER = "application/vnd.ms-excel.slicer+xml"

for prefix, uri in (
    ("", NS_MAIN),
    ("r", NS_REL),
    ("mc", NS_MC),
    ("x14", NS_X14),
    ("x15", NS_X15),
    ("xr10", NS_XR10),
    ("sle", NS_SLE),
    ("sle15", NS_SLE15),
    ("xdr", NS_XDR),
    ("a", NS_A),
):
    ET.register_namespace(prefix, uri)


def _q(namespace: str, tag: str) -> str:
    return f"{{{namespace}}}{tag}"


def _xml_bytes(root: ET.Element) -> bytes:
    return ET.tostring(
        root,
        encoding="utf-8",
        xml_declaration=True,
    )


def _append_ignorable_namespaces(
    root: ET.Element,
    *prefixes: str,
) -> None:
    current = root.get(_q(NS_MC, "Ignorable"), "").split()
    for prefix in prefixes:
        if prefix not in current:
            current.append(prefix)
    if current:
        root.set(_q(NS_MC, "Ignorable"), " ".join(current))


def _add_slicer_part_namespaces(
    xml: bytes,
    *,
    include_x15: bool = False,
) -> bytes:
    text = xml.decode("utf-8")
    marker = "?>"
    position = text.find(marker)
    if position < 0:
        raise ValueError("XML de slicer sin declaración XML.")
    root_start = text.find("<", position + len(marker))
    root_end = text.find(">", root_start)
    if root_start < 0 or root_end < 0:
        raise ValueError("XML de slicer sin elemento raíz.")

    root_open = text[root_start:root_end]
    root_open = root_open.replace(
        ' xmlns:x14="' + NS_X14 + '"',
        "",
    )
    root_open = root_open.replace(
        "<x14:",
        "<",
    )
    root_open = root_open.replace(
        "</x14:",
        "</",
    )
    root_open = root_open.replace(
        " xmlns='",
        " xmlns='",
    )
    if " xmlns=" not in root_open:
        root_open += f' xmlns="{NS_X14}"'
    if f' xmlns:mc="{NS_MC}"' not in root_open:
        root_open += f' xmlns:mc="{NS_MC}"'
    if ' mc:Ignorable="' not in root_open:
        root_open += ' mc:Ignorable="x xr10"'
    if f' xmlns:x="{NS_MAIN}"' not in root_open:
        root_open += f' xmlns:x="{NS_MAIN}"'
    if f' xmlns:xr10="{NS_XR10}"' not in root_open:
        root_open += f' xmlns:xr10="{NS_XR10}"'
    if include_x15 and f' xmlns:x15="{NS_X15}"' not in root_open:
        root_open += f' xmlns:x15="{NS_X15}"'

    if text[root_start:root_end] != root_open:
        text = text[:root_start] + root_open + text[root_end:]

    # The x14 serializer creates qualified child tags. Normalize the complete
    # x14 subtree to the default namespace used by the official examples.
    text = text.replace("<x14:", "<").replace("</x14:", "</")
    return text.encode("utf-8")


def _next_rid(rels: ET.Element) -> str:
    values: list[int] = []
    for rel in rels.findall(_q(NS_PKG_REL, "Relationship")):
        value = rel.get("Id", "")
        if value.startswith("rId") and value[3:].isdigit():
            values.append(int(value[3:]))
    return f"rId{max(values, default=0) + 1}"


def _normalize_target(source: str, target: str) -> str:
    base = Path(source).parent
    path = (base / target).as_posix()
    parts: list[str] = []
    for part in path.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def _load_xml(entries: dict[str, bytes], name: str) -> ET.Element:
    return ET.fromstring(entries[name])


def _sheet_context(
    entries: dict[str, bytes],
) -> tuple[str, ET.Element, ET.Element]:
    workbook = _load_xml(entries, "xl/workbook.xml")
    workbook_rels = _load_xml(
        entries,
        "xl/_rels/workbook.xml.rels",
    )
    sheet = next(
        sheet
        for sheet in workbook.findall(
            f"{_q(NS_MAIN, 'sheets')}/{_q(NS_MAIN, 'sheet')}",
        )
        if sheet.get("name") == "Productos"
    )
    sheet_rid = sheet.get(_q(NS_REL, "id"))
    target = next(
        rel.get("Target", "")
        for rel in workbook_rels.findall(
            _q(NS_PKG_REL, "Relationship"),
        )
        if rel.get("Id") == sheet_rid
    )
    sheet_path = _normalize_target("xl/workbook.xml", target)
    rels_path = (
        f"{Path(sheet_path).parent.as_posix()}/_rels/"
        f"{Path(sheet_path).name}.rels"
    )
    return (
        sheet_path,
        _load_xml(entries, sheet_path),
        _load_xml(entries, rels_path),
    )


def _table_info(
    entries: dict[str, bytes],
    table_name: str,
    field_name: str,
) -> tuple[int, int]:
    for name, payload in entries.items():
        if not name.startswith("xl/tables/") or not name.endswith(".xml"):
            continue
        table = ET.fromstring(payload)
        if table.get("name") != table_name:
            continue

        table_id = int(table.get("id", "1"))
        columns = table.find(_q(NS_MAIN, "tableColumns"))
        if columns is None:
            raise ValueError("La tabla del catálogo no contiene columnas.")

        for index, column in enumerate(
            columns.findall(_q(NS_MAIN, "tableColumn")),
            start=1,
        ):
            if column.get("name") == field_name:
                return table_id, index

        raise ValueError(
            f"Campo de segmentación no encontrado: {field_name}"
        )

    raise ValueError(f"Tabla no encontrada: {table_name}")


def _append_defined_name(
    workbook: ET.Element,
    cache_name: str,
) -> None:
    defined_names = workbook.find(_q(NS_MAIN, "definedNames"))
    if defined_names is None:
        defined_names = ET.Element(_q(NS_MAIN, "definedNames"))
        sheets = workbook.find(_q(NS_MAIN, "sheets"))
        if sheets is None:
            raise ValueError("El libro no contiene la colección de hojas.")
        workbook.insert(list(workbook).index(sheets) + 1, defined_names)

    for node in defined_names.findall(_q(NS_MAIN, "definedName")):
        if node.get("name") == cache_name:
            return

    node = ET.SubElement(
        defined_names,
        _q(NS_MAIN, "definedName"),
        {"name": cache_name},
    )
    node.text = "#N/A"


def _append_workbook_slicer_cache(
    entries: dict[str, bytes],
    cache_id: int,
    cache_name: str,
) -> None:
    workbook = _load_xml(entries, "xl/workbook.xml")
    _append_ignorable_namespaces(workbook, "x15")
    rels = _load_xml(entries, "xl/_rels/workbook.xml.rels")
    rid = _next_rid(rels)

    ET.SubElement(
        rels,
        _q(NS_PKG_REL, "Relationship"),
        {
            "Id": rid,
            "Type": REL_SLICER_CACHE,
            "Target": (
                f"/xl/slicerCaches/slicerCache{cache_id}.xml"
            ),
        },
    )

    ext_lst = workbook.find(_q(NS_MAIN, "extLst"))
    if ext_lst is None:
        ext_lst = ET.SubElement(workbook, _q(NS_MAIN, "extLst"))

    ext = ET.SubElement(
        ext_lst,
        _q(NS_MAIN, "ext"),
        {"uri": URI_SLICER_CACHES_X15},
    )
    slicer_caches = ET.SubElement(
        ext,
        _q(NS_X15, "slicerCaches"),
    )
    ET.SubElement(
        slicer_caches,
        _q(NS_X14, "slicerCache"),
        {_q(NS_REL, "id"): rid},
    )

    _append_defined_name(workbook, cache_name)
    workbook_xml = _xml_bytes(workbook).decode("utf-8")
    root_end = workbook_xml.find(">", workbook_xml.find("<workbook"))
    root_open = workbook_xml[:root_end]
    root_open = root_open.replace(
        ' xmlns:x14="' + NS_X14 + '"',
        "",
    )
    workbook_xml = root_open + workbook_xml[root_end:]
    workbook_xml = workbook_xml.replace(
        "<x15:slicerCaches>",
        f'<x15:slicerCaches xmlns:x14="{NS_X14}">',
        1,
    )
    entries["xl/workbook.xml"] = workbook_xml.encode("utf-8")
    entries["xl/_rels/workbook.xml.rels"] = _xml_bytes(rels)


def _append_sheet_slicer(
    entries: dict[str, bytes],
    sheet_path: str,
    sheet: ET.Element,
    sheet_rels: ET.Element,
    slicer_id: int,
) -> None:
    rid = _next_rid(sheet_rels)
    ET.SubElement(
        sheet_rels,
        _q(NS_PKG_REL, "Relationship"),
        {
            "Id": rid,
            "Type": REL_SLICER,
            "Target": f"../slicers/slicer{slicer_id}.xml",
        },
    )

    ext_lst = sheet.find(_q(NS_MAIN, "extLst"))
    if ext_lst is None:
        ext_lst = ET.SubElement(sheet, _q(NS_MAIN, "extLst"))

    ext = ET.SubElement(
        ext_lst,
        _q(NS_MAIN, "ext"),
        {"uri": URI_SLICER_LIST_X15},
    )
    slicer_list = ET.SubElement(
        ext,
        _q(NS_X14, "slicerList"),
    )
    ET.SubElement(
        slicer_list,
        _q(NS_X14, "slicer"),
        {_q(NS_REL, "id"): rid},
    )

    rels_path = (
        f"{Path(sheet_path).parent.as_posix()}/_rels/"
        f"{Path(sheet_path).name}.rels"
    )
    sheet_xml = _xml_bytes(sheet).decode("utf-8")
    sheet_xml = sheet_xml.replace(
        f'<ext uri="{URI_SLICER_LIST_X15}">',
        f'<ext xmlns:x15="{NS_X15}" uri="{URI_SLICER_LIST_X15}">',
        1,
    ).encode("utf-8")
    entries[sheet_path] = sheet_xml
    entries[rels_path] = _xml_bytes(sheet_rels)


def _drawing_path_and_root(
    entries: dict[str, bytes],
    sheet_path: str,
    sheet: ET.Element,
    sheet_rels: ET.Element,
) -> tuple[str, ET.Element]:
    drawing = sheet.find(_q(NS_MAIN, "drawing"))
    if drawing is not None:
        drawing_rid = drawing.get(_q(NS_REL, "id"))
        for rel in sheet_rels.findall(
            _q(NS_PKG_REL, "Relationship"),
        ):
            if rel.get("Id") == drawing_rid:
                drawing_path = _normalize_target(
                    sheet_path,
                    rel.get("Target", ""),
                )
                return drawing_path, _load_xml(entries, drawing_path)

    drawing_ids = [
        int(Path(name).stem.removeprefix("drawing"))
        for name in entries
        if name.startswith("xl/drawings/drawing")
        and name.endswith(".xml")
        and Path(name).stem.removeprefix("drawing").isdigit()
    ]
    drawing_id = max(drawing_ids, default=0) + 1
    drawing_path = f"xl/drawings/drawing{drawing_id}.xml"

    drawing_rid = _next_rid(sheet_rels)
    drawing = ET.Element(
        _q(NS_MAIN, "drawing"),
        {_q(NS_REL, "id"): drawing_rid},
    )
    ext_lst = sheet.find(_q(NS_MAIN, "extLst"))
    if ext_lst is None:
        sheet.append(drawing)
    else:
        sheet.insert(list(sheet).index(ext_lst), drawing)
    ET.SubElement(
        sheet_rels,
        _q(NS_PKG_REL, "Relationship"),
        {
            "Id": drawing_rid,
            "Type": REL_DRAWING,
            "Target": f"../drawings/drawing{drawing_id}.xml",
        },
    )
    return drawing_path, ET.Element(_q(NS_XDR, "wsDr"))


def _append_slicer_drawing(
    entries: dict[str, bytes],
    sheet_path: str,
    sheet: ET.Element,
    sheet_rels: ET.Element,
    slicer_name: str,
) -> None:
    drawing_path, drawing_root = _drawing_path_and_root(
        entries,
        sheet_path,
        sheet,
        sheet_rels,
    )

    ids: list[int] = []
    for node in drawing_root.iter(_q(NS_XDR, "cNvPr")):
        try:
            ids.append(int(node.get("id", "0")))
        except (TypeError, ValueError):
            continue
    nv_id = max(ids, default=0) + 1

    anchor = ET.SubElement(
        drawing_root,
        _q(NS_XDR, "oneCellAnchor"),
    )
    from_cell = ET.SubElement(anchor, _q(NS_XDR, "from"))
    for tag, value in (
        ("col", "0"),
        ("colOff", "0"),
        ("row", "0"),
        ("rowOff", "0"),
    ):
        ET.SubElement(from_cell, _q(NS_XDR, tag)).text = value
    ET.SubElement(
        anchor,
        _q(NS_XDR, "ext"),
        {"cx": "1905000", "cy": "3524250"},
    )

    alternate = ET.SubElement(
        anchor,
        _q(NS_MC, "AlternateContent"),
    )
    choice = ET.SubElement(
        alternate,
        _q(NS_MC, "Choice"),
        {"Requires": "sle15"},
    )
    graphic_frame = ET.SubElement(
        choice,
        _q(NS_XDR, "graphicFrame"),
    )
    non_visual = ET.SubElement(
        graphic_frame,
        _q(NS_XDR, "nvGraphicFramePr"),
    )
    ET.SubElement(
        non_visual,
        _q(NS_XDR, "cNvPr"),
        {"id": str(nv_id), "name": slicer_name},
    )
    ET.SubElement(
        non_visual,
        _q(NS_XDR, "cNvGraphicFramePr"),
    )

    xfrm = ET.SubElement(graphic_frame, _q(NS_XDR, "xfrm"))
    ET.SubElement(
        xfrm,
        _q(NS_A, "off"),
        {"x": "0", "y": "0"},
    )
    ET.SubElement(
        xfrm,
        _q(NS_A, "ext"),
        {"cx": "0", "cy": "0"},
    )

    graphic = ET.SubElement(graphic_frame, _q(NS_A, "graphic"))
    graphic_data = ET.SubElement(
        graphic,
        _q(NS_A, "graphicData"),
        {"uri": NS_SLE},
    )
    ET.SubElement(
        graphic_data,
        _q(NS_SLE, "slicer"),
        {"name": slicer_name},
    )

    fallback = ET.SubElement(
        alternate,
        _q(NS_MC, "Fallback"),
    )
    shape = ET.SubElement(fallback, _q(NS_XDR, "sp"))
    nv_shape = ET.SubElement(shape, _q(NS_XDR, "nvSpPr"))
    ET.SubElement(
        nv_shape,
        _q(NS_XDR, "cNvPr"),
        {"id": str(nv_id + 1), "name": ""},
    )
    ET.SubElement(
        nv_shape,
        _q(NS_XDR, "cNvSpPr"),
        {"txBox": "1"},
    )

    shape_properties = ET.SubElement(
        shape,
        _q(NS_XDR, "spPr"),
    )
    shape_xfrm = ET.SubElement(
        shape_properties,
        _q(NS_A, "xfrm"),
    )
    ET.SubElement(
        shape_xfrm,
        _q(NS_A, "off"),
        {"x": "2914650", "y": "152400"},
    )
    ET.SubElement(
        shape_xfrm,
        _q(NS_A, "ext"),
        {"cx": "1828800", "cy": "2238375"},
    )
    solid_fill = ET.SubElement(
        shape_properties,
        _q(NS_A, "solidFill"),
    )
    ET.SubElement(
        solid_fill,
        _q(NS_A, "srgbClr"),
        {"val": "FFFFFF"},
    )
    geometry = ET.SubElement(
        shape_properties,
        _q(NS_A, "prstGeom"),
        {"prst": "rect"},
    )
    ET.SubElement(geometry, _q(NS_A, "avLst"))
    line = ET.SubElement(
        shape_properties,
        _q(NS_A, "ln"),
        {"w": "1"},
    )
    line_fill = ET.SubElement(
        line,
        _q(NS_A, "solidFill"),
    )
    ET.SubElement(
        line_fill,
        _q(NS_A, "prstClr"),
        {"val": "black"},
    )

    tx_body = ET.SubElement(shape, _q(NS_XDR, "txBody"))
    ET.SubElement(
        tx_body,
        _q(NS_A, "bodyPr"),
        {"vertOverflow": "clip", "horzOverflow": "clip"},
    )
    ET.SubElement(tx_body, _q(NS_A, "lstStyle"))
    paragraph = ET.SubElement(tx_body, _q(NS_A, "p"))
    run = ET.SubElement(paragraph, _q(NS_A, "r"))
    ET.SubElement(run, _q(NS_A, "t")).text = (
        "Esta forma representa una segmentación de datos de tabla."
    )

    client_data = ET.SubElement(
        anchor,
        _q(NS_XDR, "clientData"),
    )
    client_data.set("fLocksWithSheet", "1")
    client_data.set("fPrintsWithSheet", "0")

    drawing_xml = _xml_bytes(drawing_root).decode("utf-8")
    drawing_xml = drawing_xml.replace(
        '<mc:Choice Requires="sle15">',
        f'<mc:Choice xmlns:sle15="{NS_SLE15}" Requires="sle15">',
        1,
    ).encode("utf-8")
    entries[drawing_path] = drawing_xml

    rels_path = (
        f"{Path(sheet_path).parent.as_posix()}/_rels/"
        f"{Path(sheet_path).name}.rels"
    )
    sheet_xml = _xml_bytes(sheet).decode("utf-8")
    sheet_xml = sheet_xml.replace(
        f'<ext uri="{URI_SLICER_LIST_X15}">',
        f'<ext xmlns:x15="{NS_X15}" uri="{URI_SLICER_LIST_X15}">',
        1,
    ).encode("utf-8")
    entries[sheet_path] = sheet_xml
    entries[rels_path] = _xml_bytes(sheet_rels)


def _ensure_content_types(
    entries: dict[str, bytes],
    cache_id: int,
    slicer_id: int,
    drawing_path: str,
) -> None:
    content_types = _load_xml(entries, "[Content_Types].xml")
    overrides = content_types.findall(_q(NS_CT, "Override"))
    existing = {node.get("PartName") for node in overrides}
    new_parts = (
        (
            f"/xl/slicerCaches/slicerCache{cache_id}.xml",
            CONTENT_TYPE_SLICER_CACHE,
        ),
        (
            f"/xl/slicers/slicer{slicer_id}.xml",
            CONTENT_TYPE_SLICER,
        ),
        (f"/{drawing_path}", CONTENT_TYPE_DRAWING),
    )
    for part_name, content_type in new_parts:
        if part_name in existing:
            continue
        ET.SubElement(
            content_types,
            _q(NS_CT, "Override"),
            {
                "PartName": part_name,
                "ContentType": content_type,
            },
        )
    entries["[Content_Types].xml"] = _xml_bytes(content_types)


def _add_category_slicer_ooxml(
    filename: str | Path,
    *,
    table_name: str,
    field_name: str,
) -> None:
    path = Path(filename)
    with ZipFile(path, "r") as archive:
        entries = {
            info.filename: archive.read(info.filename)
            for info in archive.infolist()
        }

    sheet_path, sheet, sheet_rels = _sheet_context(entries)
    _append_ignorable_namespaces(sheet, "x14")
    table_id, column_index = _table_info(
        entries,
        table_name,
        field_name,
    )

    cache_id = 1
    slicer_id = 1
    cache_name = "Slicer_Categoria"
    slicer_name = field_name

    cache_xml = ET.Element(
        _q(NS_X14, "slicerCacheDefinition"),
        {
            "name": cache_name,
            "sourceName": field_name,
        },
    )
    cache_ext_list = ET.SubElement(
        cache_xml,
        _q(NS_X14, "extLst"),
    )
    cache_ext = ET.SubElement(
        cache_ext_list,
        _q(NS_X14, "ext"),
        {"uri": URI_SLICER_CACHE_DEFINITION},
    )
    ET.SubElement(
        cache_ext,
        _q(NS_X15, "tableSlicerCache"),
        {
            "tableId": str(table_id),
            "column": str(column_index),
        },
    )

    slicer_xml = ET.Element(_q(NS_X14, "slicers"))
    ET.SubElement(
        slicer_xml,
        _q(NS_X14, "slicer"),
        {
            "name": slicer_name,
            "cache": cache_name,
            "caption": "Categorías",
            "showCaption": "1",
            "columnCount": "1",
            "style": "SlicerStyleLight1",
            "rowHeight": "251883",
        },
    )

    entries[
        f"xl/slicerCaches/slicerCache{cache_id}.xml"
    ] = _add_slicer_part_namespaces(
        _xml_bytes(cache_xml),
        include_x15=True,
    )
    entries[f"xl/slicers/slicer{slicer_id}.xml"] = _add_slicer_part_namespaces(
        _xml_bytes(slicer_xml),
    )

    _append_workbook_slicer_cache(
        entries,
        cache_id,
        cache_name,
    )
    _append_sheet_slicer(
        entries,
        sheet_path,
        sheet,
        sheet_rels,
        slicer_id,
    )
    _append_slicer_drawing(
        entries,
        sheet_path,
        sheet,
        sheet_rels,
        slicer_name,
    )

    drawing = sheet.find(_q(NS_MAIN, "drawing"))
    if drawing is None:
        raise ValueError("No se pudo crear el dibujo de la segmentación.")
    drawing_rid = drawing.get(_q(NS_REL, "id"))
    drawing_target = next(
        rel.get("Target", "")
        for rel in sheet_rels.findall(
            _q(NS_PKG_REL, "Relationship"),
        )
        if rel.get("Id") == drawing_rid
    )
    drawing_path = _normalize_target(sheet_path, drawing_target)

    _ensure_content_types(
        entries,
        cache_id,
        slicer_id,
        drawing_path,
    )

    temp = path.with_suffix(path.suffix + ".tmp")
    with ZipFile(temp, "w", ZIP_DEFLATED) as archive:
        for name, payload in entries.items():
            archive.writestr(name, payload)
    temp.replace(path)


def _add_category_slicer_with_excel(
    filename: str | Path,
    *,
    field_name: str,
) -> bool:
    if os.name != "nt":
        return False

    path = Path(filename).resolve()
    script = r"""
$ErrorActionPreference = "Stop"
$path = $env:FCM_EXCEL_SLICER_FILE
$excel = $null
$book = $null
$sheet = $null
$table = $null
$cache = $null
$slicer = $null
$items = $null

try {
    $excel = New-Object -ComObject Excel.Application
    $majorVersion = [int][double]$excel.Version
    if ($majorVersion -lt 15) {
        throw "La versión de Excel no admite segmentaciones de datos de tabla."
    }

    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.ScreenUpdating = $false

    [void]$excel.Workbooks.Open(
        [string]$path,
        0,
        $false
    )
    $book = $excel.ActiveWorkbook
    if ($book -eq $null) {
        throw "Excel no devolvió el libro abierto."
    }
    if ($book.ReadOnly) {
        throw "Excel abrió el libro como solo lectura."
    }

    $sheet = $book.Worksheets.Item("Productos")
    $table = $sheet.ListObjects.Item("CatalogoProductos")

    try {
        $cache = $book.SlicerCaches.Add2(
            $table,
            $env:FCM_EXCEL_SLICER_FIELD,
            "SegmentaciónDeDatos_Categoría",
            1
        )
    }
    catch {
        $cache = $book.SlicerCaches.Add(
            $table,
            $env:FCM_EXCEL_SLICER_FIELD,
            "SegmentaciónDeDatos_Categoría"
        )
    }

    $slicer = $cache.Slicers.Add(
        $sheet,
        $null,
        "Categoría",
        "Categoría",
        4,
        4,
        250,
        540
    )
    if ($cache -eq $null) {
        throw "Excel no creó la caché de la segmentación."
    }

    try {
        $cache.ClearAllFilters()
    }
    catch {
    }

    if ($cache.Slicers.Count -lt 1) {
        throw "Excel no creó ningún objeto Slicer."
    }

    $slicer.NumberOfColumns = 1
    $slicer.DisplayHeader = $true
    $slicer.Top = 4
    $slicer.Left = 4
    $slicer.Width = 250
    $slicer.Height = 540
    $slicer.Locked = $false
    $slicer.DisableMoveResizeUI = $false
    $slicer.Shape.Visible = $true

    try {
        $slicer.RowHeight = 18.5
    }
    catch {
    }

    try {
        $slicer.Style = "SlicerStyleLight5"
    }
    catch {
        try {
            $slicer.Style = "SlicerStyleLight2"
        }
        catch {
            $slicer.Style = "SlicerStyleLight1"
        }
    }

    try {
        $cache.SortItems = $true
    }
    catch {
    }

    $items = $cache.SlicerItems
    if ($items -eq $null -or $items.Count -lt 1) {
        throw "La segmentación fue creada, pero no contiene categorías."
    }

    $book.SaveCopyAs($env:FCM_EXCEL_SLICER_OUTPUT)
}
finally {
    foreach ($object in @($items, $slicer, $cache, $table, $sheet)) {
        if ($object -ne $null) {
            try {
                [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($object)
            }
            catch {
            }
        }
    }

    if ($book -ne $null) {
        try {
            $book.Close($false)
        }
        catch {
        }
        try {
            [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($book)
        }
        catch {
        }
    }

    if ($excel -ne $null) {
        try {
            $excel.Quit()
        }
        catch {
        }
        try {
            [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($excel)
        }
        catch {
        }
    }

    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
"""
    fd, temporary_output_name = tempfile.mkstemp(
        prefix=".fcm_excel_slicer_",
        suffix=".xlsx",
        dir=path.parent,
    )
    os.close(fd)
    temporary_output = Path(temporary_output_name)
    temporary_output.unlink(missing_ok=True)

    env = os.environ.copy()
    env["FCM_EXCEL_SLICER_FILE"] = str(path)
    env["FCM_EXCEL_SLICER_OUTPUT"] = str(temporary_output)
    env["FCM_EXCEL_SLICER_FIELD"] = field_name

    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(
            "No se pudo iniciar Excel para crear la segmentación nativa."
        ) from exc

    if result.returncode == 0:
        if not temporary_output.exists():
            raise RuntimeError(
                "Excel informó que creó la segmentación, "
                "pero no generó el archivo de salida."
            )
        try:
            os.replace(temporary_output, path)
            os.chmod(path, 0o666)
        finally:
            temporary_output.unlink(missing_ok=True)
        return True

    temporary_output.unlink(missing_ok=True)
    details = (result.stderr or result.stdout or "").strip()
    raise RuntimeError(
        "Excel no pudo crear la segmentación nativa. "
        f"Detalles: {details or 'sin detalles'}"
    )


def add_category_slicer(
    filename: str | Path,
    *,
    table_name: str,
    field_name: str,
) -> None:
    mode = os.environ.get("FCM_EXCEL_SLICER_MODE", "auto").casefold()
    if mode == "disabled":
        return

    if mode == "ooxml":
        raise RuntimeError(
            "La generación manual de segmentaciones OOXML está deshabilitada "
            "porque puede producir libros rechazados por Excel."
        )

    if os.name != "nt":
        return

    _add_category_slicer_with_excel(
        filename,
        field_name=field_name,
    )
