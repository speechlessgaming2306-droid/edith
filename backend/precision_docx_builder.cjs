const fs = require("fs");
const path = require("path");
const {
  Document,
  Packer,
  Paragraph,
  TextRun,
  HeadingLevel,
  AlignmentType,
  WidthType,
  LevelFormat,
} = require("docx");

function requireArg(index, label) {
  const value = process.argv[index];
  if (!value) {
    throw new Error(`Missing required argument: ${label}`);
  }
  return value;
}

function buildBulletParagraph(text, level = 0) {
  return new Paragraph({
    text,
    numbering: {
      reference: "edith-bullets",
      level,
    },
    spacing: {
      after: 90,
      line: 300,
    },
  });
}

function buildNumberedParagraph(text, index) {
  return new Paragraph({
    children: [new TextRun(`${index}. ${text}`)],
    spacing: {
      after: 90,
      line: 300,
    },
    indent: {
      left: 360,
      hanging: 240,
    },
  });
}

function paragraphFromBlock(block) {
  const type = block.type;
  if (type === "heading") {
    return new Paragraph({
      text: block.text || "",
      heading: HeadingLevel.HEADING_1,
      spacing: {
        before: 280,
        after: 100,
      },
    });
  }

  if (type === "paragraph") {
    return new Paragraph({
      children: [new TextRun(block.text || "")],
      spacing: {
        after: 120,
        line: 320,
      },
    });
  }

  if (type === "meta_lines") {
    return (block.items || []).map((item) => new Paragraph({
      children: [
        new TextRun({
          text: item,
          italics: true,
          color: "5B6472",
        }),
      ],
      spacing: {
        after: 60,
      },
    }));
  }

  if (type === "bullet_list") {
    return (block.items || []).map((item) => buildBulletParagraph(item));
  }

  if (type === "numbered_list") {
    return (block.items || []).map((item, index) => buildNumberedParagraph(item, index + 1));
  }

  if (type === "signature") {
    const paragraphs = [
      new Paragraph({
        spacing: {
          before: 240,
          after: 60,
        },
      }),
    ];
    if (block.name) {
      paragraphs.push(new Paragraph({
        children: [new TextRun(block.name)],
        spacing: { after: 40 },
      }));
    }
    for (const line of block.lines || []) {
      paragraphs.push(new Paragraph({
        children: [new TextRun(line)],
        spacing: { after: 40 },
      }));
    }
    return paragraphs;
  }

  return [];
}

async function main() {
  const inputPath = requireArg(2, "input json");
  const outputPath = requireArg(3, "output docx");
  const payload = JSON.parse(fs.readFileSync(inputPath, "utf8"));
  const title = payload.title || "Document";
  const blocks = Array.isArray(payload.blocks) ? payload.blocks : [];

  const children = [
    new Paragraph({
      children: [
        new TextRun({
          text: title,
          bold: true,
          size: 44,
          color: "1E293B",
        }),
      ],
      alignment: AlignmentType.CENTER,
      spacing: {
        after: 220,
      },
    }),
  ];

  for (const block of blocks) {
    const result = paragraphFromBlock(block);
    if (Array.isArray(result)) {
      children.push(...result);
    } else if (result) {
      children.push(result);
    }
  }

  const doc = new Document({
    numbering: {
      config: [
        {
          reference: "edith-bullets",
          levels: [
            {
              level: 0,
              format: LevelFormat.BULLET,
              text: "\u2022",
              alignment: AlignmentType.LEFT,
              style: {
                paragraph: {
                  indent: {
                    left: 720,
                    hanging: 240,
                  },
                },
              },
            },
          ],
        },
      ],
    },
    styles: {
      paragraphStyles: [
        {
          id: "Heading1",
          name: "Heading 1",
          basedOn: "Normal",
          next: "Normal",
          quickFormat: true,
          run: {
            bold: true,
            size: 28,
            color: "1F2937",
          },
          paragraph: {
            spacing: {
              before: 280,
              after: 100,
            },
          },
        },
      ],
    },
    sections: [
      {
        properties: {
          page: {
            size: {
              width: 11906,
              height: 16838,
            },
            margin: {
              top: 900,
              right: 900,
              bottom: 1080,
              left: 900,
            },
          },
        },
        children,
      },
    ],
  });

  const buffer = await Packer.toBuffer(doc);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, buffer);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
