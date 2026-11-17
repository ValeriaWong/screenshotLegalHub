"""Table text and cell geometry; HTML is never executed."""
from html.parser import HTMLParser
class TableRows(HTMLParser):
    def __init__(self):
        super().__init__();self.rows=[];self.cells=[];self.row=None;self.cell=None;self.occupied={};self.column=0;self.attrs={}
    def handle_starttag(self,tag,attrs):
        if tag=='tr': self.row=[];self.column=0
        elif tag in {'td','th'} and self.row is not None:
            while self.occupied.get((len(self.rows),self.column)): self.column+=1
            attributes=dict(attrs)
            def span(name):
                try:return max(1,min(1000,int(attributes.get(name) or 1)))
                except ValueError:return 1
            self.attrs=dict(row=len(self.rows),column=self.column,row_span=span('rowspan'),column_span=span('colspan'),header=tag=='th')
            self.cell=[]
        elif tag in {'br','p'} and self.cell is not None:self.cell.append(' ')
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in {'td','th'} and self.cell is not None and self.row is not None:
            text=''.join(self.cell).strip();self.row.append(text);self.cells.append(dict(self.attrs,text=text))
            for r in range(self.attrs['row'],self.attrs['row']+self.attrs['row_span']):
                for c in range(self.column,self.column+self.attrs['column_span']):self.occupied[(r,c)]=True
            self.column+=self.attrs['column_span'];self.cell=None
        elif tag=='tr' and self.row is not None:
            self.rows.append(self.row);self.row=None
def table_rows(html):
    parser=TableRows();parser.feed(html);return parser.rows
