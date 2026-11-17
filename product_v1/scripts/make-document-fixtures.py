"""Generate synthetic document fixtures; run with the isolated parser Python."""
from pathlib import Path
import sys
from reportlab.pdfgen import canvas
from docx import Document
from openpyxl import Workbook
root=Path(sys.argv[1]);root.mkdir(parents=True,exist_ok=True)
c=canvas.Canvas(str(root/'paper.pdf'))
for i in range(7):
    c.drawString(72,740,'Source page '+str(i+1)+': industrial sample amount '+str(520+i)+' CNY')
    c.drawString(72,710,'Measured data; verify against the original.')
    c.showPage()
c.save()
d=Document();d.add_heading('Research notes',0);d.add_paragraph('Office source value: 520 CNY.');d.save(root/'notes.docx')
w=Workbook();w.active.append(['Material','Amount']);w.active.append(['Sample',520]);w.save(root/'table.xlsx')

from pptx import Presentation
p=Presentation();s=p.slides.add_slide(p.slide_layouts[1]);s.shapes.title.text="Industrial notes";s.placeholders[1].text="Measured amount: 520 CNY";p.save(root/"slides.pptx")
(root/"data.csv").write_text("Material,Amount\nSample,520\n",encoding="utf-8")
