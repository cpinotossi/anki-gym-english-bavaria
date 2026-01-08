# Luna - Anki Vocabulary Extractor 🧗‍♀️📚

Extract vocabulary from textbook images using Azure AI Vision OCR and create Anki flashcards for language learning.

## Overview

This project helps students digitize vocabulary from textbook pages into [Anki](https://apps.ankiweb.net/) flashcards. It uses Azure Computer Vision to extract text via OCR and creates import-ready files for Anki.

### Features

- 🔍 **OCR Extraction**: Extract vocabulary from textbook images using Azure AI Vision
- ✅ **Azure Translator Validation**: Validate OCR translations with Azure Translator
- 🔄 **Bidirectional Cards**: Creates cards in both directions (e.g., English→German & German→English)
- 🛡️ **Idempotent**: Won't overwrite existing data unless explicitly requested
- 📱 **Anki Compatible**: Output files ready for import into Anki Desktop or AnkiWeb

## Project Structure

```
luna/
├── input/                          # Textbook screenshots (not in git)
│   ├── english/
│   │   └── unit-1/                 # English Unit 1 images
│   └── france/
│       └── unit-2/                 # French Unit 2 images
│
├── output/                         # Generated files (not in git)
│   ├── english/
│   │   └── unit-1/
│   │       ├── anki_english_unit-1.txt   # OCR extracted vocabulary
│   │       ├── raw_english_unit-1.txt    # Raw OCR text
│   │       ├── final_english_unit-1.txt  # Validated with Azure alternatives
│   │       └── validation_report_*.md    # Validation report
│   └── france/
│       └── unit-2/
│           └── ...
│
├── scripts/                        # Main scripts
│   ├── create_anki_from_images.py  # Main extraction script
│   ├── validate_vocabulary.py      # Azure Translator validation
│   └── vocabulary_db.py            # Database utilities
│
├── .env                            # Azure credentials (not in git)
├── .env.example                    # Example credentials file
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.8+
- Azure Account with Computer Vision resource
- Anki Desktop (for importing flashcards)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/cpinotossi/luna.git
cd luna
```

2. Create virtual environment:
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
# or
source .venv/bin/activate  # Linux/Mac
```

3. Install dependencies:
```bash
pip install azure-ai-vision-imageanalysis azure-identity python-dotenv requests
```

4. Configure Azure credentials:
```bash
cp .env.example .env
# Edit .env with your Azure Vision credentials
```

### Usage

1. **Add images** to the appropriate input folder:
   ```
   input/english/unit-1/   # For English textbook screenshots
   input/france/unit-2/    # For French textbook screenshots
   ```

2. **Run extraction**:
   ```bash
   # English vocabulary
   python scripts/create_anki_from_images.py input/english/unit-1 -o output/english/unit-1 -l english --raw

   # French vocabulary
   python scripts/create_anki_from_images.py input/france/unit-2 -o output/france/unit-2 -l french --raw
   ```

3. **Import into Anki**:
   - Open Anki Desktop
   - File → Import
   - Select `output/<language>/<unit>/anki_vocabulary.txt`
   - Import!

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--output` | `-o` | Output folder (default: ./output) |
| `--language` | `-l` | Source language: english, french, german |
| `--deck` | `-d` | Custom deck name |
| `--raw` | `-r` | Also save raw OCR text |
| `--force` | `-f` | Overwrite existing files |
| `--reset` | | Delete all files in output folder before processing |

### Validation with Azure Translator

After extraction, validate translations with Azure Translator:

```bash
# Validate English vocabulary
python scripts/validate_vocabulary.py output/english/unit-1/anki_english_unit-1.txt --from en --to de

# Validate French vocabulary  
python scripts/validate_vocabulary.py output/france/unit-2/anki_france_unit-2.txt --from fr --to de
```

This creates:
- `final_*.txt` - All vocabulary with `[Azure: alternative]` for suspicious translations
- `validation_report_*.md` - Detailed validation report

### Idempotency

The script is **idempotent** - it will NOT overwrite existing output files:

```bash
# First run - creates files
python scripts/create_anki_from_images.py input/english/unit-1 -o output/english/unit-1 -l english --raw

# Second run - skips (existing files protected)
python scripts/create_anki_from_images.py input/english/unit-1 -o output/english/unit-1 -l english --raw
# Output: "Output file already exists... Skipping to prevent data loss."

# Force overwrite when needed
python scripts/create_anki_from_images.py input/english/unit-1 -o output/english/unit-1 -l english --raw --force
```

This protects your validated vocabulary from accidental overwrites when adding new images.

## Adding New Units

1. Create the input folder:
   ```bash
   mkdir -p input/english/unit-2
   ```

2. Add textbook screenshots to the folder

3. Create the output folder:
   ```bash
   mkdir -p output/english/unit-2
   ```

4. Run extraction:
   ```bash
   python scripts/create_anki_from_images.py input/english/unit-2 -o output/english/unit-2 -l english --raw
   ```

## Anki File Format

The generated files use Anki's text import format:

```
#separator:Tab
#html:true
#deck:English Unit 1
#notetype:Einfach (beide Richtungen)
personality	Persönlichkeit
to disagree (with)	anderer Meinung sein [Azure: zu widersprechen]
```

The `[Azure: ...]` notation shows alternative translations from Azure Translator for manual review.

## Azure Services Used

| Service | Purpose |
|---------|---------|
| Azure AI Vision | OCR text extraction from images |
| Azure Translator | Translation validation |

Both services use Service Principal authentication (recommended) or Azure CLI.

## License

MIT License - See [LICENSE](LICENSE) file.
