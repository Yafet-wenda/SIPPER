const fs = require('fs');
const docx = require('C:/Users/yafet/AppData/Roaming/npm/node_modules/docx');
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, AlignmentType, PageOrientation, LevelFormat, BorderStyle, WidthType, ShadingType, HeadingLevel, TableOfContents, PageBreak, PageNumber } = docx;

const content = fs.readFileSync('D:/SIPPER/docs/laporan-implementasi-ocr.md', 'utf8');
const lines = content.split('\n');
const children = [];

let inCodeBlock = false;
let codeText = '';
let codeLanguage = '';

for (let i = 0; i < lines.length; i++) {
  const line = lines[i];
  
  // Skip horizontal rules
  if (line.trim() === '---') continue;
  
  // Code blocks
  if (line.startsWith('```')) {
    if (inCodeBlock) {
      children.push(new Paragraph({ 
        shading: { fill: 'F5F5F5', type: ShadingType.CLEAR },
        children: [new TextRun({ text: codeText, font: 'Consolas', size: 20 })]
      }));
      codeText = '';
      inCodeBlock = false;
    } else {
      inCodeBlock = true;
      codeLanguage = line.substring(3).trim();
    }
    continue;
  }
  
  if (inCodeBlock) {
    codeText += (codeText ? '\n' : '') + line;
    continue;
  }
  
  // Headings
  if (line.startsWith('# ')) {
    children.push(new Paragraph({ 
      heading: HeadingLevel.HEADING_1, 
      children: [new TextRun({ text: line.substring(2), bold: true, size: 32 })] 
    }));
  } else if (line.startsWith('## ')) {
    children.push(new Paragraph({ 
      heading: HeadingLevel.HEADING_2, 
      children: [new TextRun({ text: line.substring(3), bold: true, size: 28 })] 
    }));
  } else if (line.startsWith('### ')) {
    children.push(new Paragraph({ 
      heading: HeadingLevel.HEADING_3, 
      children: [new TextRun({ text: line.substring(4), bold: true, size: 26 })] 
    }));
  } else if (line.startsWith('#### ')) {
    children.push(new Paragraph({ 
      heading: HeadingLevel.HEADING_4, 
      children: [new TextRun({ text: line.substring(5), bold: true, size: 24 })] 
    }));
  } else if (line.match(/^- \[[ x]\]/)) {
    // Checkbox items
    const match = line.match(/^- \[([ x])\] (.+)/);
    if (match) {
      const checked = match[1] === 'x';
      children.push(new Paragraph({ 
        numbering: { reference: 'bullets', level: 0 },
        children: [new TextRun(checked ? '☑ ' + match[2] : '☐ ' + match[2])]
      }));
    }
  } else if (line.startsWith('- ✅') || line.startsWith('- ❌')) {
    children.push(new Paragraph({ 
      numbering: { reference: 'bullets', level: 0 },
      children: [new TextRun(line.substring(2))]
    }));
  } else if (line.match(/^-\s/)) {
    children.push(new Paragraph({ 
      numbering: { reference: 'bullets', level: 0 },
      children: [new TextRun(line.substring(2))]
    }));
  } else if (line.match(/^\d+\.\s/)) {
    // Numbered list
    children.push(new Paragraph({ 
      numbering: { reference: 'numbers', level: 0 },
      children: [new TextRun(line.replace(/^\d+\.\s/, ''))]
    }));
  } else if (line.trim()) {
    // Regular paragraph - handle bold markers
    const parts = line.split(/\*\*(.+?)\*\*/g);
    const runs = [];
    for (let j = 0; j < parts.length; j++) {
      if (j % 2 === 1) {
        // Bold text
        runs.push(new TextRun({ text: parts[j], bold: true, size: 24 }));
      } else if (parts[j]) {
        runs.push(new TextRun({ text: parts[j], size: 24 }));
      }
    }
    if (runs.length > 0) {
      children.push(new Paragraph({ children: runs }));
    }
  }
}

const doc = new Document({
  styles: {
    default: { document: { run: { font: 'Arial', size: 24 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 32, bold: true, font: 'Arial', color: '2E75B6' },
        paragraph: { spacing: { before: 240, after: 240 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 28, bold: true, font: 'Arial', color: '2E75B6' },
        paragraph: { spacing: { before: 180, after: 180 }, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 26, bold: true, font: 'Arial' },
        paragraph: { spacing: { before: 140, after: 140 }, outlineLevel: 2 } },
      { id: 'Heading4', name: 'Heading 4', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 24, bold: true, font: 'Arial', italics: true },
        paragraph: { spacing: { before: 120, after: 120 }, outlineLevel: 3 } },
    ]
  },
  numbering: {
    config: [
      { reference: 'bullets',
        levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: 'numbers',
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    headers: {
      default: new docx.Header({ children: [new Paragraph({ children: [new TextRun('Laporan Implementasi OCR - SIPPER')] })] })
    },
    footers: {
      default: new docx.Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun('Page '), new TextRun({ children: [PageNumber.CURRENT] })] })] })
    },
    children: [
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: 'Laporan Implementasi OCR - SIPPER', bold: true, size: 36 })] }),
      new Paragraph({ children: [new TextRun('Tanggal: 2026-10-07'), new TextRun(' | '), new TextRun('Versi: 1.0')] }),
      new Paragraph({ spacing: { after: 200 } }),
      new TableOfContents('Daftar Isi', { hyperlink: true, headingStyleRange: '1-3' }),
      new Paragraph({ children: [new PageBreak()] }),
      ...children
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync('D:/SIPPER/docs/laporan-implementasi-ocr.docx', buffer);
  console.log('DOCX created successfully');
}).catch(err => {
  console.error('Error creating DOCX:', err.message);
  process.exit(1);
});
