from scrapers.parser import Parser


def test_parser_html():

    html = """
    <html>
        <body>
            <h1>
                Producto prueba
            </h1>
        </body>
    </html>
    """

    parser = Parser()

    soup = parser.parse(html)

    assert soup.h1.text.strip() == "Producto prueba"