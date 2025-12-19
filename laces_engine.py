import streamlit as st
from SPARQLWrapper import SPARQLWrapper2, JSON
from fpdf import FPDF
import re

class LacesPDF(FPDF):
    """Custom FPDF class with automatic Unicode character cleaning and Markdown parsing."""
    def header(self):
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, 'Laces Requirements Report', 0, 0, 'R')
        self.ln(10)

    def sanitize_text(self, text):
        """Replaces problematic Unicode characters with Latin-1 equivalents."""
        if not text: return ""
        replacements = {
            '\ufb01': 'fi', '\ufb02': 'fl', '\u2013': '-', '\u2014': '-',
            '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"', '\u2022': '*',
        }
        for unicode_char, replacement in replacements.items():
            text = text.replace(unicode_char, replacement)
        return text.encode('latin-1', 'replace').decode('latin-1')

    def add_markdown(self, markdown_text):
        lines = markdown_text.split('\n')
        in_table = False
        table_data = []
        for line in lines:
            line = line.strip()
            if line.startswith('|'):
                if ':---' in line or '|---' in line: continue
                cells = [self.sanitize_text(c.strip()) for c in line.split('|') if c.strip()]
                if cells:
                    table_data.append(cells)
                    in_table = True
                continue
            else:
                if in_table:
                    self.draw_table(table_data)
                    table_data = []; in_table = False
            
            clean_line = self.sanitize_text(line)
            if clean_line.startswith('###'):
                self.ln(5); self.set_font('Arial', 'B', 12)
                self.multi_cell(0, 8, clean_line.replace('###', '').strip())
                self.set_font('Arial', '', 10)
            elif clean_line.startswith('##'):
                self.ln(7); self.set_font('Arial', 'B', 14)
                self.multi_cell(0, 10, clean_line.replace('##', '').strip())
                self.set_font('Arial', '', 10)
            elif clean_line.startswith('#'):
                self.ln(10); self.set_font('Arial', 'B', 18)
                self.multi_cell(0, 12, clean_line.replace('#', '').strip())
                self.ln(5); self.set_font('Arial', '', 10)
            elif clean_line == '---':
                self.line(10, self.get_y(), 200, self.get_y()); self.ln(5)
            elif clean_line:
                self.set_font('Arial', '', 10)
                if '**' in clean_line:
                    parts = re.split(r'(\*\*.*?\*\*)', clean_line)
                    for part in parts:
                        if part.startswith('**') and part.endswith('**'):
                            self.set_font('Arial', 'B', 10); self.write(6, part.replace('**', ''))
                        else:
                            self.set_font('Arial', '', 10); self.write(6, part)
                    self.ln(6)
                else: self.multi_cell(0, 6, clean_line)
        if in_table: self.draw_table(table_data)

    def draw_table(self, data):
        if not data: return
        self.set_font('Arial', 'B', 9)
        col_width = 190 / len(data[0])
        for col in data[0]: self.cell(col_width, 7, col, border=1)
        self.ln()
        self.set_font('Arial', '', 9)
        for row in data[1:]:
            for col in row: self.cell(col_width, 7, col, border=1)
            self.ln()
        self.ln(5)

class LacesEngine:
    @staticmethod
    def retrieve_objects(endpoint, user, password, query, keys: tuple):
        """Standard SPARQL retrieval logic."""
        sparql = SPARQLWrapper2(endpoint)
        if user and password: sparql.setCredentials(user, password)
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        try:
            response = sparql.query()
            objects = []
            if response and keys in response:
                bindings = response[list(keys)]
                for b in bindings:
                    objects.append({k: b[k].value for k in keys})
            return objects
        except Exception as e:
            st.error(f"SPARQL Error: {e}")
            return None