#!/usr/bin/env python3
"""
Anki Vocabulary Extractor
=========================
Extracts vocabulary from textbook images using Azure AI Vision OCR
and creates Anki-compatible import files.

Usage:
    python scripts/create_anki_from_images.py input/<language>/<unit> [options]

Examples:
    python scripts/create_anki_from_images.py input/english/unit-1 -o output/english/unit-1 --raw
    python scripts/create_anki_from_images.py input/france/unit-2 -o output/france/unit-2 -l french --raw
    python scripts/create_anki_from_images.py input/english/unit-3 --deck "English Unit 3" --force

The script is idempotent: it will NOT overwrite existing output files unless --force is used.
This protects your validated vocabulary from accidental overwrites.

Authentication:
    Option 1 (Service Principal - recommended):
        Set AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID
        
    Option 2 (API Key):
        Set AZURE_VISION_ENDPOINT and AZURE_VISION_KEY
        
    Credentials can be stored in .env file (auto-loaded).
"""

import os
import sys
import re
import argparse
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, use system env vars

# Azure AI Vision imports
from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential

# Try to import Azure Identity for Service Principal auth
try:
    from azure.identity import ClientSecretCredential, DefaultAzureCredential
    AZURE_IDENTITY_AVAILABLE = True
except ImportError:
    AZURE_IDENTITY_AVAILABLE = False


def get_azure_client():
    """Create Azure Vision client using Service Principal or API Key."""
    # Default endpoint - use custom subdomain for token auth
    endpoint = os.environ.get("AZURE_VISION_ENDPOINT", "https://luna-vision.cognitiveservices.azure.com/")
    
    # Option 1: Service Principal authentication (recommended)
    client_id = os.environ.get("AZURE_CLIENT_ID")
    client_secret = os.environ.get("AZURE_CLIENT_SECRET")
    tenant_id = os.environ.get("AZURE_TENANT_ID")
    
    if client_id and client_secret and tenant_id and AZURE_IDENTITY_AVAILABLE:
        print("Using Service Principal authentication...")
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        return ImageAnalysisClient(endpoint=endpoint, credential=credential)
    
    # Option 2: DefaultAzureCredential (Azure CLI, etc.)
    if AZURE_IDENTITY_AVAILABLE and not os.environ.get("AZURE_VISION_KEY"):
        try:
            print("Using DefaultAzureCredential (Azure CLI)...")
            credential = DefaultAzureCredential()
            return ImageAnalysisClient(endpoint=endpoint, credential=credential)
        except Exception:
            pass
    
    # Option 3: API Key authentication (fallback)
    key = os.environ.get("AZURE_VISION_KEY")
    if key:
        print("Using API Key authentication...")
        return ImageAnalysisClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(key)
        )
    
    print("Error: No valid Azure credentials found.")
    print("\nOption 1 - Service Principal (recommended):")
    print("  Set AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID")
    print("\nOption 2 - API Key:")
    print("  Set AZURE_VISION_ENDPOINT and AZURE_VISION_KEY")
    print("\nOption 3 - Azure CLI:")
    print("  Run 'az login' to authenticate")
    sys.exit(1)


def extract_text_from_image(client, image_path):
    """Extract text from an image using Azure Computer Vision OCR."""
    with open(image_path, "rb") as image_file:
        image_data = image_file.read()
    
    result = client.analyze(
        image_data=image_data,
        visual_features=[VisualFeatures.READ]
    )
    
    extracted_text = []
    if result.read is not None:
        for block in result.read.blocks:
            for line in block.lines:
                extracted_text.append(line.text)
    
    return extracted_text


def extract_all_images(client, folder_path):
    """Extract text from all images in a folder."""
    image_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.gif')
    images = [f for f in os.listdir(folder_path) 
              if f.lower().endswith(image_extensions)]
    images.sort()
    
    if not images:
        print(f"Error: No images found in {folder_path}")
        sys.exit(1)
    
    print(f"Found {len(images)} images to process...")
    
    all_text = []
    for i, image_name in enumerate(images, 1):
        image_path = os.path.join(folder_path, image_name)
        print(f"Processing {i}/{len(images)}: {image_name}")
        
        try:
            text_lines = extract_text_from_image(client, image_path)
            all_text.extend(text_lines)
            print(f"  Extracted {len(text_lines)} lines")
        except Exception as e:
            print(f"  Error: {e}")
    
    return all_text


def parse_english_vocabulary(lines):
    """
    Parse English vocabulary from OCR-extracted text.
    English textbook format (2-column layout, OCR reads line by line):
    - English word/phrase [pronunciation]
    - German translation (may span multiple lines, interrupted by example sentences)
    - Example sentence (English)
    - Etymology notes (Fr., Lat., etc.)
    
    The OCR often interleaves German translations with English example sentences
    because of the 2-column layout. We need to handle this.
    """
    vocabulary = []
    
    # Skip patterns for English textbook
    skip_patterns = [
        r'^[\d]+$',  # Page numbers
        r'^one hundred',  # Page number words
        r'^two hundred', r'^three hundred',
        r'^Unit \d+', r'^Check-in$', r'^Vocabulary$', r'^Media collocations$',
        r'^Media$', r'^Verb$', r'^Collocations$', r'^Translation$',
        r'^print media$', r'^TV$', r'^radio$', r'^online media$', r'^social media$',
        r'^Describing developments$', r'^Adjective collocations$',
        r'^Nouns and adjectives$', r'^Nouns and verbs with the same form$',
        r'^Skills:', r'^Unit task:', r'^Story:', r'^Across cultures',
        r'^Focus \d+', r'^Station \d+',
    ]
    
    # Characters that indicate German text
    german_indicators = ['ä', 'ö', 'ü', 'ß', 'Ä', 'Ö', 'Ü']
    
    # German word starters (definite articles, common patterns)
    german_starters = [
        'der ', 'die ', 'das ', 'ein ', 'eine ', 'etw.', 'jdn.', 'jdm.', 'jmd.',
        'sich ', '(sich)', '(tun)', '(zu)', '(mit)', '(über)', '(auf)', '(an)',
        'anderen', 'anderer', 'Meinung', 'nicht', 'sein; ', 'haben; ',
    ]
    
    # Patterns to skip (not translations) - more comprehensive
    skip_line_patterns = [
        r'^Fr\.',  # French etymology
        r'^Lat\.',  # Latin etymology
        r'^!',  # Notes  
        r'^->',  # Word derivations starting with ->
        r'^\w+ ->',  # Word derivations like "imagination -> to imagine"
        r'^[a-z]+ = [a-z]+',  # English synonyms like "smart = clever"
        r'^[a-z]+ «',  # Antonym markers like "smart «> stupid"
        r'\d{3}$',  # Page numbers at end
        r'^\[',  # Pronunciation-only lines starting with [
        r'^one hundred', r'^two hundred',  # Page numbers in words
        r'\[[^\]]+\]',  # Contains pronunciation brackets like [selvz]
        r'^to me ', r'^to you ', r'^to him ', r'^to her ',  # Sentence fragments from examples
    ]
    
    # Substrings that indicate the line is NOT a translation
    skip_substrings = ['->', '«', '»', ' = ', '] (pl)', '(pl.)', '(sing.)']
    
    # English sentence starters (to detect example sentences)
    english_sentence_starters = [
        'I ', "I'm ", "I've ", "I'd ", "I'll ",
        'You ', "You're ", "You've ", "You'd ", "You'll ",
        'He ', "He's ", "He'd ", "He'll ", 'She ', "She's ", "She'd ", "She'll ",
        'We ', "We're ", "We've ", "We'd ", "We'll ",
        'They ', "They're ", "They've ", "They'd ", "They'll ",
        'It ', "It's ", "It'd ", "It'll ", 'Its ',
        'My ', 'Your ', 'His ', 'Her ', 'Our ', 'Their ',
        'The ', 'A ', 'An ', 'Some ', 'Any ', 'This ', 'That ', 'These ', 'Those ',
        'If ', 'When ', 'Where ', 'What ', 'Why ', 'How ', 'Who ',
        'Are ', 'Is ', 'Was ', 'Were ', 'Do ', 'Does ', 'Did ',
        'Have ', 'Has ', 'Had ', 'Can ', 'Could ', 'Will ', 'Would ', 'Should ',
        'Never ', 'Always ', 'Just ', 'With ', 'As ', 'To ', 'For ', 'From ',
        'Arms ', 'Sports ', 'There ',
    ]
    
    def should_skip_line(text):
        """Check if line should be skipped entirely."""
        if not text:
            return True
        # Check skip substrings
        if any(sub in text for sub in skip_substrings):
            return True
        # Check skip patterns
        for pattern in skip_line_patterns:
            if re.match(pattern, text):
                return True
        return False
    
    def is_likely_german(text):
        """Check if text is likely German translation."""
        if not text or len(text) < 2:
            return False
        
        # Skip lines with derivation/antonym markers
        if should_skip_line(text):
            return False
        
        # Contains German special characters
        if any(c in text for c in german_indicators):
            return True
        
        # Starts with German patterns
        if any(text.startswith(s) for s in german_starters):
            return True
        
        # Skip if starts with English verb pattern "to + word"
        if re.match(r'^to [a-z]+', text):
            return False
        
        # Short capitalized word that's not an English sentence
        if (text[0].isupper() and len(text) < 40 and 
            not any(text.startswith(s) for s in english_sentence_starters)):
            return True
        
        # Lowercase word with semicolons/slashes (German style)
        if text[0].islower() and len(text) < 50 and (';' in text or '/' in text):
            return True
        
        # Single lowercase word - could be German if short and looks like German
        # German past participles often use ss, ck, ch, sch, etc.
        # Also common German verbs/words
        if text[0].islower() and len(text) < 25 and len(text.split()) == 1:
            german_patterns = ['ss', 'ck', 'sch', 'tzt', 'ngen', 'ung', 'heit', 'keit', 'rden', 'eich']
            common_german_words = ['werden', 'haben', 'machen', 'gehen', 'kommen', 'nehmen', 
                                   'sehen', 'geben', 'wissen', 'können', 'müssen', 'wollen',
                                   'sollen', 'dürfen', 'lassen', 'bleiben', 'finden', 'denken',
                                   'vergleichbar', 'digital', 'blond']
            if any(p in text.lower() for p in german_patterns):
                return True
            if text.lower() in common_german_words:
                return True
        
        return False
    
    def is_english_sentence(text):
        """Check if text looks like an English example sentence."""
        if not text:
            return False
        return (
            len(text) > 30 and
            any(text.startswith(s) for s in english_sentence_starters)
        )
    
    def is_continuation(text):
        """Check if text looks like a German translation continuation."""
        if not text or len(text) < 2:
            return False
        if should_skip_line(text):
            return False
        # Skip English verb patterns "to X"
        if re.match(r'^to [a-z]+', text):
            return False
        return (
            (text[0].islower() or any(c in text for c in german_indicators)) and
            len(text) < 50 and
            not is_english_sentence(text)
        )
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines
        if not line:
            i += 1
            continue
        
        # Skip known section headers
        skip = False
        for pattern in skip_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                skip = True
                break
        if skip:
            i += 1
            continue
        
        # Pattern 1: English word with pronunciation on same line: word [pronunciation]
        # Also handles: self [self], selves [selvz] (pl) - plural markers at end
        # Also handles OCR errors like ]] at the end
        match = re.match(r'^[\*"\d\s]*([a-zA-Z][a-zA-Z\s\'\-\(\)\.\/\+\,\?!]+?)\s*\[([^\]]+)\]\]?(?:\s*\((?:pl|sing)\.\?\)?)?$', line)
        if not match:
            # Try alternate pattern: word [pron], word2 [pron2] (pl)
            match = re.match(r'^[\*"\d\s]*([a-zA-Z][a-zA-Z\s\'\-\,]+)\s*\[[^\]]+\]\]?(?:,\s*\w+\s*\[[^\]]+\]\]?)?\s*(?:\((?:pl|sing)\.?\))?$', line)
        if not match:
            # Pattern for lines like: digital ['did3it]] or successful [sok'sesf]]
            match = re.match(r'^[\*"\d\s]*([a-zA-Z][a-zA-Z\s\'\-]+)\s*\[[^\]]+\]\]$', line)
        
        # Pattern 7: Multiple words with pronunciations on same line
        # e.g., "active ['æktiv], angry, clear, difficult, extinct"
        # e.g., "celebrity [sa'lebrati] news, reviews [rr'vju:z]"
        # Extract each word with its pronunciation
        if not match:
            multi_word_match = re.findall(r'([a-zA-Z][a-zA-Z\-]+)\s*\[[^\]]+\]', line)
            if multi_word_match and len(multi_word_match) >= 1:
                # Get first word with pronunciation as main entry
                first_word = multi_word_match[0].strip()
                if len(first_word) >= 3:
                    # Look for German translation on next line
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if is_likely_german(next_line) and not should_skip_line(next_line):
                            vocabulary.append((first_word, next_line))
                            i += 1
                            continue
        
        # Pattern 3: Word with pronunciation and inline German translation
        # e.g., "indirect [,Indirekt; „indm'rekt] indirekt"
        inline_german = None
        if not match:
            inline_match = re.match(r'^[\*"\d\s]*([a-zA-Z][a-zA-Z\s\'\-]+)\s*\[[^\]]+\]\s+([a-zA-ZäöüßÄÖÜ][a-zA-ZäöüßÄÖÜ\-\/\s]+)$', line)
            if inline_match:
                english_word = inline_match.group(1).strip().lstrip('*"0123456789 ')
                inline_german = inline_match.group(2).strip()
                if english_word and inline_german and len(english_word) >= 2:
                    vocabulary.append((english_word, inline_german))
                    i += 1
                    continue
        
        # Pattern 4: Word with plural form: knife [naif], knives (pl)
        if not match:
            plural_match = re.match(r'^[\*"\d\s]*([a-zA-Z][a-zA-Z\s\'\-]+)\s*\[[^\]]+\],\s*\w+\s*\(pl\)$', line)
            if plural_match:
                match = plural_match
        
        # Pattern 2: English word on one line, pronunciation on next line (or within next few lines)
        # e.g., "to compromise" followed by "['kompremaız]"
        # Also handles cases where skip lines (like derivations) are between word and pronunciation
        if not match and i + 1 < len(lines):
            # Look for pronunciation in next 3 lines (may skip derivation lines)
            pron_line_idx = None
            for k in range(i + 1, min(i + 4, len(lines))):
                next_line = lines[k].strip()
                # Check if this line is pronunciation-only (starts with [)
                # Also handle OCR errors like "[b] fed 'Ap wid]" or broken brackets
                if re.match(r'^\[[^\]]*\]', next_line) or re.match(r'^\[\S+\].*\]$', next_line):
                    pron_line_idx = k
                    break
                # Skip derivation/skip lines but keep looking
                if should_skip_line(next_line) or not next_line:
                    continue
                # Stop if we hit another word that looks like vocabulary
                if re.match(r'^[\*"\d\s\']*[a-zA-Z][a-zA-Z\s\'\-]+\s*\[', next_line):
                    break
            
            if pron_line_idx is not None:
                # Check if current line looks like English word/phrase
                # Allow markers like (AE), (BE), (no pl) at end
                word_match = re.match(r'^[\*"\d\s\']*([a-zA-Z][a-zA-Z\s\'\-\(\)\.\/\+\,\?!]+?)(?:\s*\((?:AE|BE|no pl|pl)\))?$', line)
                if word_match:
                    english_word = word_match.group(1).strip().lstrip('*"\'0123456789 ')
                    # Also capture the marker if present
                    marker_match = re.search(r'\((AE|BE|no pl)\)$', line)
                    if marker_match:
                        english_word = english_word + ' (' + marker_match.group(1) + ')'
                    
                    if len(english_word) >= 2 and len(english_word) < 45:
                        # This is a valid word with pronunciation on next line
                        # First, collect German translation from lines BETWEEN word and pronunciation
                        german_parts = []
                        for k in range(i + 1, pron_line_idx):
                            between_line = lines[k].strip()
                            if not between_line or should_skip_line(between_line):
                                continue
                            if is_english_sentence(between_line):
                                continue
                            if is_likely_german(between_line):
                                cleaned = between_line.rstrip(';').strip()
                                if cleaned and len(cleaned) > 1:
                                    german_parts.append(cleaned)
                        
                        # Then collect from lines AFTER pronunciation
                        j = pron_line_idx + 1  # Start after pronunciation line
                        max_lines = min(pron_line_idx + 12, len(lines))
                        
                        while j < max_lines:
                            trans_line = lines[j].strip()
                            
                            # Stop if we hit another vocabulary entry
                            if re.match(r'^[\*"\d\s]*[a-zA-Z][a-zA-Z\s\'\-\(\)\.\/\+\,\?!]+?\s*\[[^\]]+\]', trans_line):
                                break
                            if re.match(r'^\[[^\]]+\]$', trans_line):  # Pronunciation-only line
                                break
                            
                            if not trans_line:
                                j += 1
                                continue
                            
                            if should_skip_line(trans_line):
                                j += 1
                                continue
                            
                            if is_english_sentence(trans_line):
                                j += 1
                                continue
                            
                            if is_likely_german(trans_line):
                                cleaned = trans_line.rstrip(';').strip()
                                if cleaned and len(cleaned) > 1:
                                    if german_parts and german_parts[-1].endswith('-'):
                                        german_parts[-1] = german_parts[-1][:-1] + cleaned
                                    else:
                                        german_parts.append(cleaned)
                                    
                                    incomplete_endings = ['nicht', 'und', 'oder', 'bei', 'von', 'für', 'das', 'der', 'die']
                                    last_word = cleaned.split()[-1].lower().rstrip(')') if cleaned.split() else ''
                                    looks_incomplete = last_word in incomplete_endings and not cleaned.endswith(')')
                                    
                                    if not cleaned.endswith('-') and not looks_incomplete:
                                        break
                            
                            elif is_continuation(trans_line):
                                cleaned = trans_line.rstrip(';').strip()
                                if cleaned and len(cleaned) > 1:
                                    if german_parts and german_parts[-1].endswith('-'):
                                        german_parts[-1] = german_parts[-1][:-1] + cleaned
                                    else:
                                        german_parts.append(cleaned)
                                    
                                    if cleaned.endswith(')') or (len(german_parts) >= 2 and not cleaned.endswith('-')):
                                        break
                            
                            j += 1
                        
                        if german_parts:
                            german = '; '.join(german_parts)
                            german = re.sub(r';\s*;', ';', german)
                            german = re.sub(r'\s+', ' ', german)
                            german = german.strip('; ')
                            
                            if english_word and german and len(german) > 1:
                                vocabulary.append((english_word, german))
                        
                        i += 2  # Skip word and pronunciation lines
                        continue
        
        # Pattern 5: "to X oneself" without pronunciation (reflexive verbs)
        # e.g., "to push oneself" followed by German translation
        if not match:
            reflexive_match = re.match(r'^(to \w+ (oneself|yourself|himself|herself|themselves|ourselves))$', line, re.IGNORECASE)
            if reflexive_match:
                english_word = reflexive_match.group(1).strip()
                # Look for German translation in next lines
                j = i + 1
                german_parts = []
                while j < min(i + 5, len(lines)):
                    next_line = lines[j].strip()
                    if not next_line or should_skip_line(next_line):
                        j += 1
                        continue
                    if is_likely_german(next_line) or is_continuation(next_line):
                        cleaned = next_line.rstrip(';').strip()
                        if cleaned and len(cleaned) > 1:
                            german_parts.append(cleaned)
                            if not cleaned.endswith('-'):
                                break
                    j += 1
                if german_parts:
                    german = '; '.join(german_parts)
                    german = re.sub(r'\s+', ' ', german).strip('; ')
                    vocabulary.append((english_word, german))
                    i += 1
                    continue
        
        # Pattern 6: Single English word followed by German translation (no pronunciation anywhere nearby)
        # e.g., "misunderstood" followed by "missverstanden"
        # Only for single words or compound words (no spaces)
        # Skip if there's a pronunciation in the next few lines (those are handled by Pattern 2)
        if not match:
            simple_word_match = re.match(r'^[\*"\d\s\']*([a-zA-Z][a-zA-Z\-]+)$', line)
            if simple_word_match:
                english_word = simple_word_match.group(1).strip()
                if len(english_word) >= 4 and len(english_word) < 25:  # Reasonable word length
                    # Check if there's a pronunciation in the next 4 lines - if so, skip (Pattern 2 handles it)
                    has_nearby_pron = False
                    for k in range(i + 1, min(i + 5, len(lines))):
                        if re.match(r'^\[', lines[k].strip()):
                            has_nearby_pron = True
                            break
                    
                    if not has_nearby_pron and i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        # Must be a clear German word (has umlauts or ß, or matches German patterns)
                        # More strict: require German special chars OR start with lowercase AND have semicolon/slash
                        is_german_like = (
                            any(c in next_line for c in german_indicators) or
                            (next_line[0:1].islower() and (';' in next_line or '/' in next_line) and len(next_line) < 30)
                        )
                        if is_german_like and len(next_line) < 40 and len(next_line) > 2:
                            # Skip if next line is an English example sentence
                            if not is_english_sentence(next_line) and not should_skip_line(next_line):
                                vocabulary.append((english_word, next_line))
                                i += 1
                                continue
        
        if match:
            english_word = match.group(1).strip().lstrip('*"0123456789 ')
            
            if len(english_word) < 2:
                i += 1
                continue
            
            # Collect German translation from next lines
            german_parts = []
            j = i + 1
            max_lines = min(i + 10, len(lines))
            
            while j < max_lines:
                next_line = lines[j].strip()
                
                # Stop if we hit another word with pronunciation
                if re.match(r'^[\*"\d\s]*[a-zA-Z][a-zA-Z\s\'\-\(\)\.\/\+\,\?!]+?\s*\[[^\]]+\]$', next_line):
                    break
                
                if not next_line:
                    j += 1
                    continue
                
                # Skip lines with derivations, antonyms, etymology
                if should_skip_line(next_line):
                    j += 1
                    continue
                
                # Skip English example sentences
                if is_english_sentence(next_line):
                    j += 1
                    continue
                
                # Check if this is German translation
                if is_likely_german(next_line):
                    cleaned = next_line.rstrip(';').strip()
                    if cleaned and len(cleaned) > 1:
                        if german_parts and german_parts[-1].endswith('-'):
                            german_parts[-1] = german_parts[-1][:-1] + cleaned
                        else:
                            german_parts.append(cleaned)
                        
                        # Check if translation looks incomplete
                        # (ends with 'nicht', 'und', 'oder', etc. without punctuation)
                        incomplete_endings = ['nicht', 'und', 'oder', 'bei', 'von', 'für', 'das', 'der', 'die']
                        last_word = cleaned.split()[-1].lower().rstrip(')') if cleaned.split() else ''
                        looks_incomplete = last_word in incomplete_endings and not cleaned.endswith(')')
                        
                        # Stop after finding a good translation that doesn't continue
                        if not cleaned.endswith('-') and not looks_incomplete:
                            break
                
                elif is_continuation(next_line):
                    cleaned = next_line.rstrip(';').strip()
                    if cleaned and len(cleaned) > 1:
                        if german_parts and german_parts[-1].endswith('-'):
                            german_parts[-1] = german_parts[-1][:-1] + cleaned
                        else:
                            german_parts.append(cleaned)
                        
                        # Also check if continuation is complete (ends with ) or is long enough)
                        if cleaned.endswith(')') or (len(german_parts) >= 2 and not cleaned.endswith('-')):
                            break
                
                j += 1
            
            # Combine German parts
            if german_parts:
                german = '; '.join(german_parts)
                german = re.sub(r';\s*;', ';', german)
                german = re.sub(r'\s+', ' ', german)
                german = german.strip('; ')
                
                if english_word and german and len(german) > 1:
                    vocabulary.append((english_word, german))
            
            i += 1
            continue
        
        i += 1
    
    # Filter out bad entries
    def looks_like_german(text):
        german_indicators = ['ä', 'ö', 'ü', 'ß', 'Ä', 'Ö', 'Ü']
        german_words = ['sein', 'haben', 'nicht', 'und', 'oder', 'mit', 'sich']
        text_lower = text.lower()
        if any(c in text for c in german_indicators):
            return True
        if any(w in text_lower.split() for w in german_words):
            return True
        return False
    
    def is_bad_entry(eng, ger):
        # English word contains German patterns
        if looks_like_german(eng):
            return True
        # German compound words as English (like Gastfamilie)
        if len(eng) > 8 and eng[0].isupper() and eng.isalpha() and ' ' not in eng:
            # Looks like a German compound word (long, capitalized, no spaces)
            german_compounds = ['familie', 'schule', 'haus', 'zeit', 'wort', 'tag', 'buch']
            if any(p in eng.lower() for p in german_compounds):
                return True
        # English and German are exactly the same AND not a valid word (like 'digital')
        # Allow same-word entries for common loanwords (same in both languages)
        loanwords = ['digital', 'cover', 'image', 'college', 'trainer', 'content', 'communication',
                     'blond', 'argument', 'international', 'normal', 'social', 'personal', 'original',
                     'formal', 'central', 'natural', 'total', 'final', 'global', 'local', 'legal',
                     'vital', 'mental', 'dental', 'fatal', 'brutal', 'neutral', 'tribal']
        if eng.lower().strip() == ger.lower().strip() and eng.lower() not in loanwords:
            return True
        # English looks like a sentence (starts with capital + has period)
        if eng[0].isupper() and '.' in eng and len(eng) > 30:
            return True
        # Translation contains an English sentence pattern (Nobody was, Jack was, etc.)
        if re.search(r'\b(Nobody|Jack|I|We|They|He|She)\s+(was|were|am|is|are)\b', ger):
            return True
        # Translation starts with "to " AND has " - " (like "to chill out - to relax")
        # But only if it's the main translation, not a note
        if ger.startswith('to ') and ' - ' in ger and ger.count('-') == 1:
            return True
        # Translation ends with English text (long sentence pattern)
        if re.search(r'[A-Z][a-z]+\s+[a-z]+\s+[a-z]+\.?$', ger) and len(ger) > 30:
            return True
        # Short problematic entries
        if eng.lower() == 'so' and 'gewöhnt' in ger:
            return True
        # English word with slash and wrong content
        if '/' in eng and ('books' in ger.lower() or 'comics' in ger.lower()):
            return True
        return False
    
    vocabulary = [(e, g) for e, g in vocabulary if not is_bad_entry(e, g)]
    
    # Deduplicate: keep first occurrence of each English word
    seen = set()
    unique_vocab = []
    for eng, ger in vocabulary:
        eng_lower = eng.lower().strip()
        if eng_lower not in seen:
            seen.add(eng_lower)
            unique_vocab.append((eng, ger))
    
    return unique_vocab


def parse_vocabulary_lines(lines, source_language="german"):
    """
    Parse vocabulary entries from extracted text lines.
    Handles English-German and French-German textbook formats.
    """
    vocabulary = []
    
    # Use specialized parser for English
    if source_language == "english":
        return parse_english_vocabulary(lines)
    
    # Skip patterns for French textbooks
    skip_patterns = [
        r'^[\d]+$',  # Page numbers
        r'^cent-',   # French page number words
        r'^Vocabulaire$', r'^AUF EINEN BLICK', r'^MON DICO PERSONNEL',
        r'^TIPP$', r'^TU TE RAPPELLES\?$', r'^Vis-à-vis$', r'^Atelier',
        r'^Unité \d+', r'^DE$', r'^A \d+$', r'^englisch:', r'^->',
        r'^Lerne ', r'^kannst du', r'^der rechten ', r'^Westen Frankreichs',
    ]
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines
        if not line:
            i += 1
            continue
        
        # Skip known patterns
        skip = False
        for pattern in skip_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                skip = True
                break
        if skip:
            i += 1
            continue
        
        # Pattern 1: word [pronunciation] - look for translation in next lines
        match = re.match(r'^[\*\d\s]*([a-zA-ZàâäéèêëïîôùûüçœæÀÂÄÉÈÊËÏÎÔÙÛÜÇŒÆ][a-zA-ZàâäéèêëïîôùûüçœæÀÂÄÉÈÊËÏÎÔÙÛÜÇŒÆ\s\'\-\(\)\.\/\+\,]+?)\s*\[([^\]]+)\]$', line)
        
        if match:
            foreign_word = match.group(1).strip().lstrip('*0123456789 ')
            
            # Look for German translation in next few lines
            for j in range(i+1, min(i+4, len(lines))):
                next_line = lines[j].strip()
                if not next_line:
                    continue
                # Skip etymology notes and references
                if next_line.startswith(('Fr.', 'Lat.', '!', '->', '«>')):
                    continue
                # Skip example sentences (sentences in French)
                if any(next_line.startswith(x) for x in ['Il ', 'Elle ', 'Je ', 'Tu ', 'On ', 'Nous ', 'Vous ', 'Les ', 'Le ', 'La ', 'C\'', 'Pour ']):
                    continue
                # Skip lines with pronunciation brackets
                if '[' in next_line:
                    break
                
                # Check if this looks like a German translation
                if (next_line.startswith(('der ', 'die ', 'das ', 'ein ', 'eine ', 'etw.', 'jdn.', 'jdm.', 'sich ')) or
                    any(c in next_line for c in 'äöüß') or
                    (next_line[0].isupper() and len(next_line) < 80 and not any(c in next_line for c in 'àâéèêëïîôùûçœæ'))):
                    translation = next_line.rstrip(';').strip()
                    if foreign_word and translation and len(translation) > 1:
                        vocabulary.append((foreign_word, translation))
                    break
            i += 1
            continue
        
        # Pattern 2: French noun with article (no pronunciation) followed by German
        # e.g., "un sweat-shirt imprimé" then "ein Sweatshirt mit Aufdruck"
        french_match = re.match(r'^((?:un|une|le|la|les|l\'|des|au|aux|du)\s+[a-zA-ZàâäéèêëïîôùûüçœæÀÂÄÉÈÊËÏÎÔÙÛÜÇŒÆ\'\-\s]+)$', line, re.IGNORECASE)
        if french_match and source_language == "french":
            french = french_match.group(1).strip()
            # Check if next line is German translation
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if (next_line.startswith(('ein', 'eine', 'der', 'die', 'das', 'am ')) or 
                    any(c in next_line for c in 'äöüß')):
                    vocabulary.append((french, next_line))
                    i += 2
                    continue
            i += 1
            continue
        
        # Pattern 3: Verb with qc/qn followed by German
        # e.g., "porter qc" then "etw. tragen"
        verb_match = re.match(r'^([a-zA-ZàâäéèêëïîôùûüçœæÀÂÄÉÈÊËÏÎÔÙÛÜÇŒÆ\'\-\s]+(?:qc|qn))$', line)
        if verb_match:
            french = verb_match.group(1).strip()
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line.startswith(('etw.', 'jdn.', 'jdm.')) or any(c in next_line for c in 'äöüß'):
                    vocabulary.append((french, next_line))
                    i += 2
                    continue
            i += 1
            continue
        
        # Pattern 4: French phrase patterns
        phrase_match = re.match(r'^((?:pendant|avoir|être|il n\'y a|ne pas|se|faire)\s+[a-zA-ZàâäéèêëïîôùûüçœæÀÂÄÉÈÊËÏÎÔÙÛÜÇŒÆ\'\-\s]+)$', line, re.IGNORECASE)
        if phrase_match:
            french = phrase_match.group(1).strip()
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if any(c in next_line for c in 'äöüß') or next_line.startswith(('während', 'Lust', 'schlecht', 'etw.', 'jdn.', 'jdm.')):
                    vocabulary.append((french, next_line))
                    i += 2
                    continue
            i += 1
            continue
        
        # Pattern 5: Simple French verb (infinitive)
        if re.match(r'^[a-zA-ZàâäéèêëïîôùûüçœæÀÂÄÉÈÊËÏÎÔÙÛÜÇŒÆ\'\-]+$', line):
            if re.match(r'.*(?:er|ir|re|oir)$', line.lower()) or line.lower() in ['hier', 'souvent']:
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if (any(c in next_line for c in 'äöüß') or 
                        any(next_line.endswith(x) for x in ['en', 'ung', 'heit', 'keit'])):
                        vocabulary.append((line, next_line))
                        i += 2
                        continue
            i += 1
            continue
        
        # Pattern 6: Adjective with m/f forms
        adj_match = re.match(r'^([a-zA-ZàâäéèêëïîôùûüçœæÀÂÄÉÈÊËÏÎÔÙÛÜÇŒÆ\'\-]+/[a-zA-ZàâäéèêëïîôùûüçœæÀÂÄÉÈÊËÏÎÔÙÛÜÇŒÆ\'\-]+)$', line)
        if adj_match:
            french = adj_match.group(1).strip()
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if any(c in next_line for c in 'äöüß') or re.match(r'^[a-z]+$', next_line):
                    vocabulary.append((french, next_line))
                    i += 2
                    continue
            i += 1
            continue
        
        i += 1
    
    return vocabulary


def create_anki_file(vocabulary, output_path, deck_name, notetype="Einfach (beide Richtungen)", language="german"):
    """Create an Anki-compatible import file."""
    # For English with curated vocabulary, skip aggressive filtering
    is_curated_english = language == "english"
    
    with open(output_path, "w", encoding="utf-8") as f:
        # Write Anki headers
        f.write("#separator:Tab\n")
        f.write("#html:false\n")
        f.write(f"#deck:{deck_name}\n")
        f.write(f"#notetype:{notetype}\n")
        
        # Write vocabulary entries with filtering
        written = 0
        seen = set()
        for front, back in vocabulary:
            front = front.strip()
            back = back.strip()
            
            # Skip duplicates
            key = (front.lower(), back.lower())
            if key in seen:
                continue
            seen.add(key)
            
            # Basic validation (always applied)
            if not front or not back or len(front) < 2 or len(back) < 2:
                continue
            
            # For curated English vocabulary, skip aggressive filtering
            if is_curated_english:
                f.write(f"{front}\t{back}\n")
                written += 1
                continue
            
            # Aggressive filtering for OCR-extracted vocabulary (French/German)
            # Skip if German is incomplete (ends with article)
            if back.endswith('-') or back.endswith(' eine') or back.endswith(' ein') or back.endswith(' im'):
                continue
            # Skip metadata
            if '(inv.)' in back or 'invariable' in back or 'bedeutet' in back:
                continue
            # Skip if front looks German instead of French
            if front.startswith(('ein ', 'eine ', 'der ', 'die ', 'das ')):
                continue
            # Skip if back is a sentence (too long)
            if len(back) > 50:
                continue
            # Skip if back contains a question mark (example sentence)
            if '?' in back:
                continue
            # Skip if back starts with typical German sentence starters or first-person
            sentence_starters = ['Ich ', 'Wir ', 'Du ', 'Er ', 'Sie ', 'Es ', 'Da ist', 'Auf geht', 
                                'Hast ', 'Wartest ', 'Was ', 'Wie ', 'Wann ', 'Wo ']
            if any(back.startswith(s) for s in sentence_starters):
                continue
            # Skip entries that look like example sentences (German or French)
            sentence_indicators = [
                'haben wir', 'gibt kein', 'gibt es', 'ist dunkel', 'man sieht', 
                'soir,', 'Souvent', 'Gestern', 'Internet', 'schreit', 'nicht allein',
                'Vampir', 'Das Gitter', 'gehen wir', 'interessant ist', 'Recht hast',
                'gegen moi', 'contre moi', 'qu\'est', 'Qu\'est'
            ]
            if any(ind.lower() in back.lower() for ind in sentence_indicators):
                continue
            # Skip very short translations that are incomplete
            if back in ['ang', 'der', 'die', 'das', 'ein', 'eine']:
                continue
            
            f.write(f"{front}\t{back}\n")
            written += 1
    
    return written


def main():
    parser = argparse.ArgumentParser(
        description="Extract vocabulary from textbook images and create Anki flashcards.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/create_anki_from_images.py input/english/unit-1 -o output/english/unit-1 --raw
    python scripts/create_anki_from_images.py input/france/unit-2 -o output/france/unit-2 -l french --raw
    python scripts/create_anki_from_images.py input/english/unit-3 --deck "My Custom Deck" --force
        """
    )
    
    parser.add_argument("folder", help="Path to folder containing textbook images (e.g., input/english/unit-1)")
    parser.add_argument("--language", "-l", choices=["german", "french", "english"], default="german",
                        help="Source language of the textbook (default: german)")
    parser.add_argument("--deck", "-d", default=None,
                        help="Anki deck name (default: auto-generated from folder name)")
    parser.add_argument("--notetype", "-n", default="Einfach (beide Richtungen)",
                        help="Anki note type (default: 'Einfach (beide Richtungen)')")
    parser.add_argument("--output", "-o", default=None,
                        help="Output folder for Anki file (default: ./output)")
    parser.add_argument("--raw", "-r", action="store_true",
                        help="Also save raw extracted text to file")
    parser.add_argument("--force", "-f", action="store_true",
                        help="Overwrite existing output files (default: skip if exists)")
    parser.add_argument("--reset", action="store_true",
                        help="Delete all files in output folder before processing (use with caution!)")
    
    args = parser.parse_args()
    
    # Validate folder exists
    folder_path = Path(args.folder)
    if not folder_path.exists():
        print(f"Error: Folder '{folder_path}' does not exist.")
        sys.exit(1)
    
    # Generate deck name from folder path if not specified
    if args.deck:
        deck_name = args.deck
    else:
        # Use folder structure as deck name, e.g., "france/unit-2" -> "France Unit-2"
        parts = folder_path.parts[-2:] if len(folder_path.parts) >= 2 else folder_path.parts
        deck_name = " ".join(p.capitalize() for p in parts)
    
    # Set output folder
    if args.output:
        output_folder = Path(args.output)
    else:
        output_folder = Path("./output")
    
    output_folder.mkdir(parents=True, exist_ok=True)
    
    # Generate output filename with language and unit in name
    # e.g., input/english/unit-1 -> anki_english_unit-1.txt, raw_english_unit-1.txt
    folder_parts = folder_path.parts[-2:] if len(folder_path.parts) >= 2 else [folder_path.name]
    file_suffix = "_".join(folder_parts)  # e.g., "english_unit-1" or "france_unit-2"
    output_file = output_folder / f"anki_{file_suffix}.txt"
    raw_file = output_folder / f"raw_{file_suffix}.txt"
    
    # Handle --reset: delete all files in output folder
    if args.reset:
        print(f"\n⚠️  RESET MODE: Deleting all files in {output_folder}")
        for file in output_folder.iterdir():
            if file.is_file():
                file.unlink()
                print(f"  Deleted: {file.name}")
        print()
    
    # Check if output files already exist (idempotency)
    if not args.force and not args.reset:
        if output_file.exists():
            print(f"\nOutput file already exists: {output_file}")
            print(f"Use --force to overwrite existing files.")
            print(f"Use --reset to delete all files and start fresh.")
            print(f"Skipping to prevent data loss.")
            sys.exit(0)
    
    print(f"\n{'='*60}")
    print(f"Anki Vocabulary Extractor")
    print(f"{'='*60}")
    print(f"Input folder: {folder_path}")
    print(f"Output file:  {output_file}")
    print(f"Deck name:    {deck_name}")
    print(f"Language:     {args.language}")
    print(f"{'='*60}\n")
    
    # Step 1: Create Azure client
    print("Connecting to Azure AI Vision...")
    client = get_azure_client()
    
    # Step 2: Extract text from all images
    print("\nExtracting text from images...")
    all_text = extract_all_images(client, str(folder_path))
    
    # Optionally save raw text
    if args.raw:
        with open(raw_file, "w", encoding="utf-8") as f:
            f.write("\n".join(all_text))
        print(f"\nRaw text saved to: {raw_file}")
    
    # Step 3: Parse vocabulary
    print("\nParsing vocabulary entries...")
    vocabulary = parse_vocabulary_lines(all_text, args.language)
    
    if not vocabulary:
        print("\nWarning: No vocabulary entries could be parsed automatically.")
        print("The raw text has been extracted. You may need to parse it manually.")
        # Save raw text anyway
        with open(raw_file, "w", encoding="utf-8") as f:
            f.write("\n".join(all_text))
        print(f"Raw text saved to: {raw_file}")
        sys.exit(0)
    
    # Step 4: Create Anki file
    print(f"\nCreating Anki file with {len(vocabulary)} vocabulary entries...")
    count = create_anki_file(vocabulary, output_file, deck_name, args.notetype, args.language)
    
    print(f"\n{'='*60}")
    print(f"SUCCESS!")
    print(f"{'='*60}")
    print(f"Created: {output_file}")
    print(f"Entries: {count} vocabulary cards ({count*2} with reverse)")
    print(f"\nTo import into Anki:")
    print(f"  1. Open Anki Desktop")
    print(f"  2. File -> Import")
    print(f"  3. Select: {output_file}")
    print(f"  4. Click Import")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
