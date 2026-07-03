import pytest
import os
import shutil
import tempfile
from pathlib import Path
from fpdf import FPDF


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmp:
        orig = os.getcwd()
        os.chdir(tmp)
        yield Path(tmp)
        os.chdir(orig)


def make_pdf(path: Path, text: str):
    pdf = FPDF()
    pdf.add_page()
    pdf.add_font("Noto", "", "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf")
    pdf.set_font("Noto", size=12)
    pdf.multi_cell(w=0, text=text)
    pdf.output(str(path))
    return path


@pytest.fixture
def pdf_factory():
    created = []

    def _make(dir_path: Path, text: str, name: str = "test.pdf"):
        path = dir_path / name
        make_pdf(path, text)
        created.append(path)
        return path

    yield _make
    for p in created:
        if p.exists():
            p.unlink()


@pytest.fixture
def sample_pdfs(pdf_factory, temp_dir):
    src = temp_dir / "pdfs"
    src.mkdir()
    pdf_factory(src, "Apple banana fruit are delicious and healthy.", "doc1.pdf")
    pdf_factory(src, "Dog cat animal are popular pets in households.", "doc2.pdf")
    pdf_factory(src, "Machine learning artificial intelligence is transforming technology.", "doc3.pdf")
    return src
