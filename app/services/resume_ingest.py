from pathlib import Path
import shutil
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[2]

def extract_text(path):
    p=Path(path)
    if p.suffix.lower()=='.pdf': return '\n'.join((x.extract_text() or '') for x in PdfReader(str(p)).pages)
    if p.suffix.lower()=='.docx':
        from docx import Document
        return '\n'.join(x.text for x in Document(str(p)).paragraphs)
    if p.suffix.lower() in {'.txt','.md'}: return p.read_text(encoding='utf-8',errors='ignore')
    raise ValueError('Supported resume formats: PDF, DOCX, TXT, MD')

def import_resume(path):
    src=Path(path).resolve(); master=ROOT/'data/master'; master.mkdir(parents=True,exist_ok=True)
    dst=master/('uploaded_resume'+src.suffix.lower()); shutil.copy2(src,dst)
    text=extract_text(dst); (master/'uploaded_resume_extracted.txt').write_text(text,encoding='utf-8')
    return str(dst),str(master/'uploaded_resume_extracted.txt'),len(text)
