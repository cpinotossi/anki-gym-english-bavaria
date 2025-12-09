# Anki Gym English Bavaria 🧗‍♀️📚

Extract vocabulary from textbook images using Azure AI Vision OCR and create Anki flashcards for language learning.

## Overview

This project helps students digitize vocabulary from textbook pages into [Anki](https://apps.ankiweb.net/) flashcards. It uses Azure Computer Vision to extract text via OCR and creates import-ready files for Anki.

### Features

- 🔍 **OCR Extraction**: Extract vocabulary from textbook images using Azure AI Vision
- 🔄 **Bidirectional Cards**: Creates cards in both directions (e.g., English→German & German→English)
- 🏷️ **Tag Support**: Add custom tags (e.g., sports, climbing, Olympics) to organize vocabulary
- 📱 **Anki Compatible**: Output files ready for import into Anki Desktop or AnkiWeb

## Quick Start

### Prerequisites

- Python 3.8+
- Azure Account with Computer Vision resource
- Anki Desktop (for importing flashcards)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/cpinotossi/anki-gym-english-bavaria.git
cd anki-gym-english-bavaria
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
pip install azure-ai-vision-imageanalysis pillow
```

4. Configure Azure credentials:
```bash
cp .env.example .env
# Edit .env with your Azure Vision endpoint and key
```

### Usage

1. **Place your images** in the `images/` folder

2. **Run OCR extraction**:
```bash
python extract_vocabulary.py
```

3. **Create Anki file** (customize `create_anki_file.py` for your vocabulary format):
```bash
python create_anki_file.py
```

4. **Import into Anki**:
   - Open Anki Desktop
   - File → Import
   - Select the generated `.txt` file
   - Import!

## Anki File Format

The generated files use Anki's text import format with headers:

```
#separator:Tab
#html:false
#deck:English Unit 1
#notetype:Einfach (beide Richtungen)
#tags column:3
personality	Persönlichkeit	Klettern::Mentaltraining
to compete	konkurrieren	Klettern::Wettkampf Olympia::Wettkampf
```

### Headers Explained

| Header | Description |
|--------|-------------|
| `#separator:Tab` | Fields are separated by tabs |
| `#html:false` | Plain text, no HTML |
| `#deck:Name` | Target deck name |
| `#notetype:Name` | Note type (German: "Einfach (beide Richtungen)") |
| `#tags column:3` | Column 3 contains tags |

### Note Types

| English | German |
|---------|--------|
| Basic | Einfach |
| Basic (and reversed card) | Einfach (beide Richtungen) |

## Sample Vocabulary

See `samples/` folder for example vocabulary files:

- `sample_vocabulary.txt` - Basic vocabulary sample
- `sample_vocabulary_with_tags.txt` - Vocabulary with climbing/sports tags

## Project Structure

```
anki-gym-english-bavaria/
├── extract_vocabulary.py   # OCR extraction script
├── create_anki_file.py     # Anki file generator
├── .env.example            # Environment variables template
├── .gitignore              # Git ignore rules
├── samples/                # Sample vocabulary files
│   ├── sample_vocabulary.txt
│   └── sample_vocabulary_with_tags.txt
├── images/                 # Your textbook images (gitignored)
├── output/                 # Generated output files
└── README.md
```

## Azure Setup

1. Go to [Azure Portal](https://portal.azure.com)
2. Create a **Computer Vision** resource (F0 = Free tier)
3. Copy the **Endpoint** and **Key** to your `.env` file

### Free Tier Limits
- 20 calls per minute
- 5,000 calls per month

## Tags for Sports Context

The project supports hierarchical tags for organizing vocabulary by context:

```
Klettern::Training
Klettern::Wettkampf
Klettern::Mentaltraining
Olympia::Sportklettern
Olympia::Ernährung
```

This allows filtering cards in Anki by topic, e.g., for competition preparation.

## Blog Post

For a detailed tutorial, see the included blog post: [blog-post-anki-vocabulary-extraction.md](blog-post-anki-vocabulary-extraction.md)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Anki](https://apps.ankiweb.net/) - Spaced repetition flashcard software
- [Azure AI Vision](https://azure.microsoft.com/services/cognitive-services/computer-vision/) - OCR capabilities
- Bavaria's English curriculum for inspiration 🏔️

---

Made with ❤️ for language learners and climbers 🧗‍♀️
