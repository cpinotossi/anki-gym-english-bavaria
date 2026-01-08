#!/usr/bin/env python3
"""
Vocabulary Validation Tool
===========================
Validates extracted vocabulary by comparing OCR translations with 
Azure Translator results. Flags suspicious entries for manual review.

Usage:
    python validate_vocabulary.py <anki_file> [options]

Examples:
    python validate_vocabulary.py output/anki_france_unit-2.txt
    python validate_vocabulary.py output/anki_france_unit-2.txt --from fr --to de
    python validate_vocabulary.py output/anki_france_unit-2.txt --threshold 0.3

Authentication:
    Option 1 (Service Principal - recommended):
        Set AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID
        
    Option 2 (Azure CLI):
        Run 'az login' to authenticate
        
    Credentials can be stored in .env file (auto-loaded).
"""

import os
import sys
import re
import argparse
import time
from pathlib import Path
from difflib import SequenceMatcher

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, use system env vars

import requests

# Azure Identity imports
try:
    from azure.identity import ClientSecretCredential, DefaultAzureCredential
    AZURE_IDENTITY_AVAILABLE = True
except ImportError:
    AZURE_IDENTITY_AVAILABLE = False
    print("Warning: azure-identity not installed. Run: pip install azure-identity")


def get_translator_credential():
    """Get Azure credential for Translator API."""
    client_id = os.environ.get("AZURE_CLIENT_ID")
    client_secret = os.environ.get("AZURE_CLIENT_SECRET")
    tenant_id = os.environ.get("AZURE_TENANT_ID")
    
    if client_id and client_secret and tenant_id:
        print("Using Service Principal authentication...")
        return ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
    else:
        print("Using DefaultAzureCredential (Azure CLI)...")
        return DefaultAzureCredential()


def get_translator_token(credential):
    """Get access token for Azure Translator."""
    token = credential.get_token("https://cognitiveservices.azure.com/.default")
    return token.token


def translate_text(text, from_lang, to_lang, access_token):
    """Translate text using Azure Translator API with bearer token auth."""
    # Use custom subdomain endpoint for token auth
    endpoint = "https://luna-translate-anki.cognitiveservices.azure.com"
    path = "/translator/text/v3.0/translate"
    
    params = {
        "api-version": "3.0",
        "from": from_lang,
        "to": to_lang
    }
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    body = [{"text": text}]
    
    try:
        response = requests.post(
            endpoint + path,
            params=params,
            headers=headers,
            json=body,
            timeout=15
        )
        response.raise_for_status()
        result = response.json()
        
        if result and len(result) > 0 and "translations" in result[0]:
            return result[0]["translations"][0]["text"]
        return None
    except Exception as e:
        print(f"  Translation error: {e}")
        return None


def similarity_score(text1, text2):
    """Calculate similarity between two texts (0.0 to 1.0)."""
    if not text1 or not text2:
        return 0.0
    
    # Normalize texts for comparison
    t1 = text1.lower().strip()
    t2 = text2.lower().strip()
    
    # Remove common prefixes like articles for better matching
    articles = ['der ', 'die ', 'das ', 'ein ', 'eine ', 'etw. ', 'jdn. ', 'jdm. ']
    for art in articles:
        if t1.startswith(art):
            t1 = t1[len(art):]
        if t2.startswith(art):
            t2 = t2[len(art):]
    
    # Use SequenceMatcher for similarity
    return SequenceMatcher(None, t1, t2).ratio()


def word_overlap_score(text1, text2):
    """Calculate word overlap between two texts."""
    if not text1 or not text2:
        return 0.0
    
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    # Remove common stop words
    stop_words = {'der', 'die', 'das', 'ein', 'eine', 'und', 'oder', 'zu', 'sich', 'etw.', 'jdn.', 'jdm.'}
    words1 = words1 - stop_words
    words2 = words2 - stop_words
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1 & words2
    union = words1 | words2
    
    return len(intersection) / len(union) if union else 0.0


def load_anki_file(filepath):
    """Load vocabulary entries from Anki file."""
    entries = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Skip headers and empty lines
            if not line or line.startswith("#"):
                continue
            
            parts = line.split("\t")
            if len(parts) >= 2:
                entries.append((parts[0], parts[1]))
    
    return entries


def load_raw_text(raw_file):
    """Load raw OCR text for reference."""
    if not raw_file.exists():
        return ""
    
    with open(raw_file, "r", encoding="utf-8") as f:
        return f.read()


def validate_vocabulary(entries, from_lang, to_lang, threshold, raw_text=""):
    """Validate vocabulary entries against translator."""
    print("\nGetting Azure credentials...")
    credential = get_translator_credential()
    access_token = get_translator_token(credential)
    
    results = {
        "valid": [],
        "suspicious": [],
        "errors": []
    }
    
    print(f"\nValidating {len(entries)} vocabulary entries...")
    print("-" * 70)
    
    for i, (foreign, ocr_translation) in enumerate(entries, 1):
        # Progress indicator
        print(f"\r[{i}/{len(entries)}] Checking: {foreign[:30]:<30}", end="", flush=True)
        
        # Skip very short entries
        if len(foreign) < 2 or len(ocr_translation) < 2:
            results["suspicious"].append({
                "foreign": foreign,
                "ocr": ocr_translation,
                "translator": None,
                "similarity": 0,
                "reason": "Entry too short"
            })
            continue
        
        # Translate
        translator_result = translate_text(foreign, from_lang, to_lang, access_token)
        
        if translator_result is None:
            results["errors"].append({
                "foreign": foreign,
                "ocr": ocr_translation,
                "reason": "Translation API error"
            })
            continue
        
        # Calculate similarity
        seq_similarity = similarity_score(ocr_translation, translator_result)
        word_sim = word_overlap_score(ocr_translation, translator_result)
        
        # Combined score (weighted average)
        combined_score = 0.6 * seq_similarity + 0.4 * word_sim
        
        # Also check if OCR translation appears in raw text (validates it came from OCR)
        in_raw = ocr_translation.lower() in raw_text.lower() if raw_text else True
        
        entry_result = {
            "foreign": foreign,
            "ocr": ocr_translation,
            "translator": translator_result,
            "similarity": combined_score,
            "seq_similarity": seq_similarity,
            "word_overlap": word_sim,
            "in_raw_text": in_raw
        }
        
        if combined_score >= threshold:
            results["valid"].append(entry_result)
        else:
            entry_result["reason"] = f"Low similarity ({combined_score:.2f})"
            results["suspicious"].append(entry_result)
        
        # Rate limiting - small delay to avoid API throttling
        time.sleep(0.1)
    
    print("\n" + "-" * 70)
    return results


def generate_report(results, output_path):
    """Generate validation report."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Vocabulary Validation Report\n\n")
        
        total = len(results["valid"]) + len(results["suspicious"]) + len(results["errors"])
        f.write(f"**Total entries:** {total}\n")
        f.write(f"**Valid:** {len(results['valid'])} ✅\n")
        f.write(f"**Suspicious:** {len(results['suspicious'])} ⚠️\n")
        f.write(f"**Errors:** {len(results['errors'])} ❌\n\n")
        
        # Suspicious entries - need review
        if results["suspicious"]:
            f.write("## ⚠️ Suspicious Entries (Manual Review Needed)\n\n")
            f.write("| # | Foreign Word | OCR Translation | Translator Result | Similarity |\n")
            f.write("|---|-------------|-----------------|-------------------|------------|\n")
            
            for i, entry in enumerate(results["suspicious"], 1):
                translator = entry.get("translator", "N/A") or "N/A"
                similarity = entry.get("similarity", 0)
                f.write(f"| {i} | {entry['foreign']} | {entry['ocr']} | {translator} | {similarity:.2f} |\n")
            
            f.write("\n")
        
        # Errors
        if results["errors"]:
            f.write("## ❌ Errors\n\n")
            for entry in results["errors"]:
                f.write(f"- **{entry['foreign']}**: {entry['reason']}\n")
            f.write("\n")
        
        # Valid entries (summary)
        f.write("## ✅ Valid Entries\n\n")
        f.write(f"{len(results['valid'])} entries passed validation.\n\n")
        
        # Show some valid examples
        if results["valid"]:
            f.write("### Sample Valid Entries\n\n")
            f.write("| Foreign Word | OCR Translation | Translator Result | Similarity |\n")
            f.write("|-------------|-----------------|-------------------|------------|\n")
            
            for entry in results["valid"][:10]:
                f.write(f"| {entry['foreign']} | {entry['ocr']} | {entry['translator']} | {entry['similarity']:.2f} |\n")
    
    return output_path


def create_enriched_anki_file(original_entries, results, output_path, deck_name="Vocabulary"):
    """Create an enriched Anki file with Azure alternatives for suspicious entries.
    
    Valid entries: Keep as-is
    Suspicious entries: Add [Azure: alternative] if translator result differs
    Errors: Keep original (no Azure data available)
    """
    # Build lookup dictionaries
    valid_pairs = {(e["foreign"], e["ocr"]): e for e in results["valid"]}
    suspicious_pairs = {(e["foreign"], e["ocr"]): e for e in results["suspicious"]}
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("#separator:Tab\n")
        f.write("#html:true\n")
        f.write(f"#deck:{deck_name}\n")
        f.write("#notetype:Einfach (beide Richtungen)\n")
        
        count = 0
        enriched_count = 0
        
        for foreign, translation in original_entries:
            key = (foreign, translation)
            
            if key in valid_pairs:
                # Valid entry - keep as-is
                f.write(f"{foreign}\t{translation}\n")
                count += 1
            elif key in suspicious_pairs:
                # Suspicious entry - add Azure alternative if available
                entry = suspicious_pairs[key]
                azure_translation = entry.get("translator")
                
                if azure_translation and azure_translation.lower().strip() != translation.lower().strip():
                    # Azure has a different translation - add as alternative
                    enriched_translation = f"{translation} [Azure: {azure_translation}]"
                    f.write(f"{foreign}\t{enriched_translation}\n")
                    enriched_count += 1
                else:
                    # No Azure alternative or same translation
                    f.write(f"{foreign}\t{translation}\n")
                count += 1
            else:
                # Error or not processed - keep original
                f.write(f"{foreign}\t{translation}\n")
                count += 1
    
    return count, enriched_count


def main():
    parser = argparse.ArgumentParser(
        description="Validate vocabulary entries by comparing OCR with Azure Translator.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("anki_file", help="Path to Anki vocabulary file to validate")
    parser.add_argument("--from", "-f", dest="from_lang", default="fr",
                        help="Source language code (default: fr)")
    parser.add_argument("--to", "-t", dest="to_lang", default="de",
                        help="Target language code (default: de)")
    parser.add_argument("--threshold", "-th", type=float, default=0.3,
                        help="Similarity threshold (0-1, default: 0.3)")
    parser.add_argument("--raw", "-r", default=None,
                        help="Path to raw OCR text file for cross-reference")
    parser.add_argument("--output", "-o", default=None,
                        help="Output folder for reports (default: same as input)")
    
    args = parser.parse_args()
    
    # Validate input file
    anki_file = Path(args.anki_file)
    if not anki_file.exists():
        print(f"Error: File '{anki_file}' not found.")
        sys.exit(1)
    
    # Set output paths
    if args.output:
        output_folder = Path(args.output)
    else:
        output_folder = anki_file.parent
    
    output_folder.mkdir(parents=True, exist_ok=True)
    
    report_file = output_folder / f"validation_report_{anki_file.stem}.md"
    
    # Generate deck name from folder structure (e.g., "English Unit-1" or "France Unit-2")
    folder_parts = anki_file.parent.parts[-2:] if len(anki_file.parent.parts) >= 2 else ["Vocabulary"]
    deck_name = " ".join(part.replace("-", " ").title() for part in folder_parts)
    
    # Final output file replaces original anki file name pattern
    final_file = output_folder / anki_file.name.replace("anki_", "final_")
    
    # Load raw text if available
    raw_text = ""
    if args.raw:
        raw_path = Path(args.raw)
        if raw_path.exists():
            raw_text = load_raw_text(raw_path)
            print(f"Loaded raw OCR text: {len(raw_text)} characters")
    else:
        # Try to find raw file automatically
        raw_path = anki_file.parent / f"raw_{anki_file.stem.replace('anki_', '')}.txt"
        if raw_path.exists():
            raw_text = load_raw_text(raw_path)
            print(f"Found raw OCR text: {raw_path}")
    
    print(f"\n{'='*70}")
    print("Vocabulary Validation Tool")
    print(f"{'='*70}")
    print(f"Input file:    {anki_file}")
    print(f"Languages:     {args.from_lang} → {args.to_lang}")
    print(f"Threshold:     {args.threshold}")
    print(f"{'='*70}")
    
    # Load entries
    entries = load_anki_file(anki_file)
    print(f"\nLoaded {len(entries)} vocabulary entries")
    
    # Validate
    results = validate_vocabulary(entries, args.from_lang, args.to_lang, args.threshold, raw_text)
    
    # Generate reports
    print("\nGenerating reports...")
    generate_report(results, report_file)
    
    # Create final enriched file with proper deck name
    final_count, alternatives_count = create_enriched_anki_file(entries, results, final_file, deck_name)
    
    # Summary
    print(f"\n{'='*70}")
    print("VALIDATION COMPLETE")
    print(f"{'='*70}")
    print(f"✅ Valid entries:      {len(results['valid'])}")
    print(f"⚠️  Suspicious entries: {len(results['suspicious'])} (with [Azure: ...] alternatives)")
    print(f"❌ Errors:             {len(results['errors'])}")
    print(f"\nDeck name: {deck_name}")
    print(f"\nFiles created:")
    print(f"  - Validation report: {report_file}")
    print(f"  - Final Anki file:   {final_file}")
    print(f"    → {final_count} entries total, {alternatives_count} with Azure alternatives")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
