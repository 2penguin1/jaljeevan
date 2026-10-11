from datetime import date

from scripts.fetch_gr_pdfs import parse_results

PAGE = """<table id="SitePH_dgvDocuments"><tr><th>क्र.</th></tr>
<tr><td>1</td><td>मदत व पुनर्वसन विभाग</td><td><span>राज्यातील २६५ तालुक्यांमध्ये दुष्काळ जाहीर करण्याबाबत</span></td>
<td>202609251512341234</td><td>25-09-2026</td><td>812</td>
<td><a href="../Site/Upload/Government%20Resolutions/Marathi/202609251512341234.pdf" id="x">pdf</a></td></tr>
<tr><td>2</td><td>मदत व पुनर्वसन विभाग</td><td>टंचाई उपाययोजना</td><td>202609101111111111</td><td>10-09-2026</td><td>120</td>
<td><a href="../Site/Upload/Government%20Resolutions/Marathi/202609101111111111.pdf">pdf</a></td></tr></table>"""


def test_results_page_rows_become_dated_absolute_pdf_links():
    rows = parse_results(PAGE)
    assert [(r.code, r.day) for r in rows] == [("202609251512341234", date(2026, 9, 25)), ("202609101111111111", date(2026, 9, 10))]
    assert rows[0].url == "https://gr.maharashtra.gov.in/Site/Upload/Government%20Resolutions/Marathi/202609251512341234.pdf"
    assert "दुष्काळ" in rows[0].title
