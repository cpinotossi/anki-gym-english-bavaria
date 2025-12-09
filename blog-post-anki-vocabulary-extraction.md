# How I Used Azure AI Vision to Extract Vocabulary from Textbook Images for Anki

*December 8, 2025*

As a language learner, I wanted to digitize vocabulary from my English textbook (Unit 1) to study with [Anki](https://apps.ankiweb.net/), the popular spaced repetition flashcard app. Instead of manually typing hundreds of words, I used **Azure AI Vision OCR** to automatically extract all the vocabulary from 11 scanned textbook pages.

## The Challenge

I had 11 images of vocabulary pages from my English-German textbook. Each page contained:
- English words with phonetic pronunciation
- German translations
- Example sentences
- Etymology notes (French, Latin origins)

Manually typing 200+ vocabulary entries would take hours and be error-prone. There had to be a better way!

## The Solution: Azure Computer Vision OCR

### Step 1: Set Up Azure Computer Vision

First, I created an Azure Computer Vision resource (free tier F0):

```bash
# Create resource group
az group create --name "rg-luna-ocr" --location "westeurope"

# Create Computer Vision service
az cognitiveservices account create \
  --name "luna-vision-ocr" \
  --resource-group "rg-luna-ocr" \
  --kind "ComputerVision" \
  --sku "F0" \
  --location "westeurope"
```

### Step 2: Extract Text with Python

Using the Azure AI Vision SDK, I wrote a Python script to process all images:

```python
from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential

client = ImageAnalysisClient(
    endpoint="https://westeurope.api.cognitive.microsoft.com/",
    credential=AzureKeyCredential(KEY)
)

# Extract text from each image
with open(image_path, "rb") as image_file:
    result = client.analyze(
        image_data=image_file.read(),
        visual_features=[VisualFeatures.READ]
    )
```

The OCR accurately extracted all text, including:
- Special characters (ä, ö, ü, ß)
- Phonetic symbols ([,p3:sn'æloti])
- Multi-column layouts

### Step 3: Create Anki Import File

I parsed the extracted text and created a tab-separated file with Anki headers:

```
#separator:Tab
#html:false
#deck:English Unit 1
#notetype:Basic (and reversed card)
#columns:Front	Back
personality	Persönlichkeit
to disagree (with)	anderer Meinung sein; nicht einverstanden sein (mit)
to compromise	Kompromisse eingehen
...
```

The `Basic (and reversed card)` note type creates **two cards per entry**:
- English → German
- German → English

## Results

| Metric | Value |
|--------|-------|
| Images processed | 11 |
| Vocabulary entries extracted | 202 |
| Flashcards created | 404 (bidirectional) |
| Time saved | ~2-3 hours of manual typing |

## Sample Vocabulary Extracted

Here are some examples from the extracted vocabulary:

| English | German |
|---------|--------|
| personality | Persönlichkeit |
| to compromise | Kompromisse eingehen |
| imagination | Fantasie; Vorstellungskraft |
| self-esteem | Selbstwertgefühl; Selbstachtung |
| to be fed up (with) | sauer sein (auf); die Nase voll haben (von) |
| stubborn | eigensinnig; störrisch |
| ambitious | ehrgeizig |
| to convince | überzeugen |

## How to Import into Anki

1. Open **Anki Desktop**
2. Click **File** → **Import**
3. Select your `.txt` file
4. Anki automatically detects the headers and settings
5. Click **Import**
6. Sync to **AnkiWeb** to access on mobile devices

## Key Takeaways

1. **Azure AI Vision OCR is remarkably accurate** - It correctly recognized German umlauts, phonetic symbols, and complex layouts.

2. **Anki file headers save time** - Using `#notetype`, `#deck`, and `#separator` headers means Anki auto-configures the import.

3. **Bidirectional cards double your learning** - The "Basic (and reversed card)" type tests you in both directions.

4. **Automation beats manual entry** - What would have taken hours was done in minutes with better accuracy.

## Tools Used

- **[Azure Computer Vision](https://azure.microsoft.com/services/cognitive-services/computer-vision/)** - OCR and image analysis
- **[Anki](https://apps.ankiweb.net/)** - Spaced repetition flashcard app
- **Python** - For scripting and text processing
- **VS Code** - Development environment

## Try It Yourself

The free tier of Azure Computer Vision (F0) includes:
- 20 calls per minute
- 5,000 calls per month

That's plenty for digitizing textbook vocabulary!

---

*Have you used OCR to digitize study materials? Share your experience in the comments!*

## Tags

`#Azure` `#OCR` `#Anki` `#LanguageLearning` `#Python` `#Automation` `#StudyHacks`
