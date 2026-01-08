#!/usr/bin/env python3
"""
Vocabulary Database Manager
============================
SQLite database for storing, validating, and correcting vocabulary entries.
Enables tracking of OCR extractions and manual corrections.

Database Schema:
- vocabulary: Main table with all vocabulary entries
- corrections: History of manual corrections
- validation_results: Translator validation results

Usage:
    python vocabulary_db.py import <anki_file> [--source <source_name>]
    python vocabulary_db.py list [--status <status>] [--source <source>]
    python vocabulary_db.py correct <id> --translation <new_translation>
    python vocabulary_db.py export [--status valid] [--output <file>]
    python vocabulary_db.py stats
    python vocabulary_db.py find-match <foreign_word> --raw <raw_file>
"""

import os
import sys
import sqlite3
import argparse
import re
from datetime import datetime
from pathlib import Path
from difflib import SequenceMatcher, get_close_matches

# Load environment variables from .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, use system env vars

DATABASE_PATH = Path(__file__).parent / "vocabulary.db"


def get_connection():
    """Get database connection with row factory."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initialize the database schema."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Main vocabulary table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vocabulary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            foreign_word TEXT NOT NULL,
            translation TEXT NOT NULL,
            corrected_translation TEXT,
            source_language TEXT DEFAULT 'fr',
            target_language TEXT DEFAULT 'de',
            source_file TEXT,
            source_unit TEXT,
            status TEXT DEFAULT 'pending',  -- pending, valid, suspicious, corrected, deleted
            similarity_score REAL,
            translator_result TEXT,
            ocr_context TEXT,  -- Raw OCR text around this entry for context
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Corrections history
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vocabulary_id INTEGER NOT NULL,
            old_translation TEXT,
            new_translation TEXT,
            correction_type TEXT,  -- manual, auto-matched, translator
            correction_source TEXT,  -- user, raw_ocr, translator
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vocabulary_id) REFERENCES vocabulary(id)
        )
    """)
    
    # Validation results
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS validation_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vocabulary_id INTEGER NOT NULL,
            translator_result TEXT,
            similarity_score REAL,
            validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vocabulary_id) REFERENCES vocabulary(id)
        )
    """)
    
    # Create indexes for common queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_status ON vocabulary(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_source ON vocabulary(source_file)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_foreign ON vocabulary(foreign_word)")
    
    conn.commit()
    conn.close()
    print(f"Database initialized: {DATABASE_PATH}")


def import_anki_file(anki_file, source_name=None, raw_file=None):
    """Import vocabulary from Anki file into database."""
    anki_path = Path(anki_file)
    if not anki_path.exists():
        print(f"Error: File not found: {anki_file}")
        return
    
    # Determine source info
    if source_name is None:
        source_name = anki_path.stem
    
    # Extract unit from filename (e.g., anki_france_unit-2.txt -> unit-2)
    unit_match = re.search(r'(unit-?\d+)', anki_path.stem, re.IGNORECASE)
    source_unit = unit_match.group(1) if unit_match else None
    
    # Load raw OCR text if available
    raw_text = ""
    if raw_file:
        raw_path = Path(raw_file)
        if raw_path.exists():
            raw_text = raw_path.read_text(encoding='utf-8')
    
    conn = get_connection()
    cursor = conn.cursor()
    
    imported = 0
    skipped = 0
    
    with open(anki_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or '\t' not in line:
                continue
            
            parts = line.split('\t')
            if len(parts) >= 2:
                foreign_word = parts[0].strip()
                translation = parts[1].strip()
                
                # Check if already exists
                cursor.execute(
                    "SELECT id FROM vocabulary WHERE foreign_word = ? AND source_file = ?",
                    (foreign_word, source_name)
                )
                if cursor.fetchone():
                    skipped += 1
                    continue
                
                # Find context in raw OCR text
                ocr_context = find_ocr_context(foreign_word, raw_text) if raw_text else None
                
                cursor.execute("""
                    INSERT INTO vocabulary (foreign_word, translation, source_file, source_unit, ocr_context)
                    VALUES (?, ?, ?, ?, ?)
                """, (foreign_word, translation, source_name, source_unit, ocr_context))
                imported += 1
    
    conn.commit()
    conn.close()
    
    print(f"Imported {imported} entries from {anki_file}")
    if skipped:
        print(f"Skipped {skipped} duplicates")


def find_ocr_context(word, raw_text, context_chars=200):
    """Find the word in raw OCR text and return surrounding context."""
    if not raw_text:
        return None
    
    # Simple search
    idx = raw_text.lower().find(word.lower())
    if idx >= 0:
        start = max(0, idx - context_chars)
        end = min(len(raw_text), idx + len(word) + context_chars)
        return raw_text[start:end]
    
    # Try fuzzy match on first word
    first_word = word.split()[0] if ' ' in word else word
    idx = raw_text.lower().find(first_word.lower())
    if idx >= 0:
        start = max(0, idx - context_chars)
        end = min(len(raw_text), idx + len(first_word) + context_chars)
        return raw_text[start:end]
    
    return None


def find_correct_translation(vocab_id, raw_file):
    """
    Try to find the correct translation for a vocabulary entry 
    by searching in the raw OCR text.
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM vocabulary WHERE id = ?", (vocab_id,))
    row = cursor.fetchone()
    
    if not row:
        print(f"Entry {vocab_id} not found")
        return
    
    foreign_word = row['foreign_word']
    current_translation = row['translation']
    
    print(f"\n{'='*60}")
    print(f"Looking for correct translation of: {foreign_word}")
    print(f"Current (possibly wrong): {current_translation}")
    print(f"{'='*60}")
    
    # Load raw OCR text
    raw_path = Path(raw_file)
    if not raw_path.exists():
        print(f"Error: Raw file not found: {raw_file}")
        return
    
    raw_text = raw_path.read_text(encoding='utf-8')
    lines = raw_text.split('\n')
    
    # Search for the foreign word in raw text
    matches = []
    for i, line in enumerate(lines):
        if foreign_word.lower() in line.lower():
            # Get context (surrounding lines)
            start = max(0, i - 2)
            end = min(len(lines), i + 3)
            context = '\n'.join(lines[start:end])
            matches.append((i, line, context))
    
    if not matches:
        # Try partial match
        first_word = foreign_word.split()[0]
        for i, line in enumerate(lines):
            if first_word.lower() in line.lower():
                start = max(0, i - 2)
                end = min(len(lines), i + 3)
                context = '\n'.join(lines[start:end])
                matches.append((i, line, context))
    
    if matches:
        print(f"\nFound {len(matches)} potential match(es) in raw OCR:\n")
        for idx, (line_num, line, context) in enumerate(matches[:5]):
            print(f"--- Match {idx+1} (Line {line_num}) ---")
            print(context)
            print()
        
        # Try to extract the German translation
        # Pattern: usually the translation follows the foreign word on the next line or after certain characters
        potential_translations = extract_potential_translations(foreign_word, raw_text)
        if potential_translations:
            print("\nPotential correct translations found:")
            for i, trans in enumerate(potential_translations[:5], 1):
                print(f"  {i}. {trans}")
    else:
        print("No matches found in raw OCR text")
    
    conn.close()


def extract_potential_translations(foreign_word, raw_text):
    """Extract potential German translations for a foreign word from raw OCR text."""
    translations = []
    lines = raw_text.split('\n')
    
    for i, line in enumerate(lines):
        if foreign_word.lower() in line.lower():
            # Check next few lines for German text
            for j in range(i, min(i + 5, len(lines))):
                next_line = lines[j].strip()
                # Look for German patterns (contains ä, ö, ü, ß or common German words)
                if re.search(r'[äöüßÄÖÜ]|etw\.|jdn\.|jdm\.', next_line):
                    if next_line != foreign_word:
                        translations.append(next_line)
    
    return translations


def correct_entry(vocab_id, new_translation, source="manual"):
    """Correct a vocabulary entry and store the correction history."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get current entry
    cursor.execute("SELECT * FROM vocabulary WHERE id = ?", (vocab_id,))
    row = cursor.fetchone()
    
    if not row:
        print(f"Entry {vocab_id} not found")
        return
    
    old_translation = row['translation']
    
    # Store correction history
    cursor.execute("""
        INSERT INTO corrections (vocabulary_id, old_translation, new_translation, correction_type, correction_source)
        VALUES (?, ?, ?, ?, ?)
    """, (vocab_id, old_translation, new_translation, 'manual', source))
    
    # Update vocabulary entry
    cursor.execute("""
        UPDATE vocabulary 
        SET corrected_translation = ?, status = 'corrected', updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (new_translation, vocab_id))
    
    conn.commit()
    conn.close()
    
    print(f"Corrected entry {vocab_id}:")
    print(f"  Foreign: {row['foreign_word']}")
    print(f"  Old: {old_translation}")
    print(f"  New: {new_translation}")


def update_validation(vocab_id, translator_result, similarity_score, status):
    """Update validation results for a vocabulary entry."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Store validation result
    cursor.execute("""
        INSERT INTO validation_results (vocabulary_id, translator_result, similarity_score)
        VALUES (?, ?, ?)
    """, (vocab_id, translator_result, similarity_score))
    
    # Update vocabulary entry
    cursor.execute("""
        UPDATE vocabulary 
        SET translator_result = ?, similarity_score = ?, status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (translator_result, similarity_score, status, vocab_id))
    
    conn.commit()
    conn.close()


def list_entries(status=None, source=None, limit=50):
    """List vocabulary entries with optional filters."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM vocabulary WHERE 1=1"
    params = []
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    if source:
        query += " AND source_file LIKE ?"
        params.append(f"%{source}%")
    
    query += f" ORDER BY id LIMIT {limit}"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    print(f"\n{'ID':<5} {'Status':<12} {'Foreign Word':<25} {'Translation':<30} {'Corrected':<20}")
    print("-" * 95)
    
    for row in rows:
        corrected = row['corrected_translation'] or '-'
        if len(corrected) > 18:
            corrected = corrected[:18] + '..'
        
        foreign = row['foreign_word']
        if len(foreign) > 23:
            foreign = foreign[:23] + '..'
            
        trans = row['translation']
        if len(trans) > 28:
            trans = trans[:28] + '..'
        
        print(f"{row['id']:<5} {row['status']:<12} {foreign:<25} {trans:<30} {corrected:<20}")
    
    conn.close()
    print(f"\nShowing {len(rows)} entries")


def show_stats():
    """Show database statistics."""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("\n" + "=" * 50)
    print("VOCABULARY DATABASE STATISTICS")
    print("=" * 50)
    
    # Total entries
    cursor.execute("SELECT COUNT(*) as cnt FROM vocabulary")
    total = cursor.fetchone()['cnt']
    print(f"\nTotal entries: {total}")
    
    # By status
    cursor.execute("SELECT status, COUNT(*) as cnt FROM vocabulary GROUP BY status ORDER BY cnt DESC")
    print("\nBy Status:")
    for row in cursor.fetchall():
        print(f"  {row['status']:<15} {row['cnt']:>5}")
    
    # By source
    cursor.execute("SELECT source_file, COUNT(*) as cnt FROM vocabulary GROUP BY source_file ORDER BY cnt DESC")
    print("\nBy Source:")
    for row in cursor.fetchall():
        print(f"  {row['source_file']:<25} {row['cnt']:>5}")
    
    # Corrections
    cursor.execute("SELECT COUNT(*) as cnt FROM corrections")
    corrections = cursor.fetchone()['cnt']
    print(f"\nTotal corrections made: {corrections}")
    
    conn.close()


def export_vocabulary(output_file, status=None, include_corrected=True):
    """Export vocabulary to Anki format."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM vocabulary WHERE 1=1"
    params = []
    
    if status:
        statuses = status.split(',')
        placeholders = ','.join(['?' for _ in statuses])
        query += f" AND status IN ({placeholders})"
        params.extend(statuses)
    
    query += " ORDER BY source_file, id"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    output_path = Path(output_file)
    with open(output_path, 'w', encoding='utf-8') as f:
        for row in rows:
            foreign = row['foreign_word']
            # Use corrected translation if available
            if include_corrected and row['corrected_translation']:
                translation = row['corrected_translation']
            else:
                translation = row['translation']
            f.write(f"{foreign}\t{translation}\n")
    
    print(f"Exported {len(rows)} entries to {output_file}")
    conn.close()


def interactive_correct(source=None):
    """Interactive mode to correct suspicious entries."""
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM vocabulary WHERE status = 'suspicious'"
    params = []
    
    if source:
        query += " AND source_file LIKE ?"
        params.append(f"%{source}%")
    
    query += " ORDER BY similarity_score ASC LIMIT 20"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    if not rows:
        print("No suspicious entries found!")
        return
    
    print(f"\n{'='*70}")
    print("INTERACTIVE CORRECTION MODE")
    print("Commands: [Enter]=skip, [c]=correct, [v]=mark valid, [d]=delete, [q]=quit")
    print(f"{'='*70}\n")
    
    for row in rows:
        print(f"\nID: {row['id']} | Similarity: {row['similarity_score']:.2f}")
        print(f"Foreign:    {row['foreign_word']}")
        print(f"OCR:        {row['translation']}")
        print(f"Translator: {row['translator_result']}")
        
        if row['ocr_context']:
            print(f"Context:    {row['ocr_context'][:100]}...")
        
        action = input("\nAction [Enter/c/v/d/q]: ").strip().lower()
        
        if action == 'q':
            break
        elif action == 'v':
            cursor.execute("UPDATE vocabulary SET status = 'valid' WHERE id = ?", (row['id'],))
            print("Marked as valid")
        elif action == 'd':
            cursor.execute("UPDATE vocabulary SET status = 'deleted' WHERE id = ?", (row['id'],))
            print("Marked as deleted")
        elif action == 'c':
            new_trans = input("Enter correct translation: ").strip()
            if new_trans:
                correct_entry(row['id'], new_trans)
        # Enter = skip
    
    conn.commit()
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Vocabulary Database Manager")
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Init command
    subparsers.add_parser('init', help='Initialize database')
    
    # Import command
    import_parser = subparsers.add_parser('import', help='Import Anki file')
    import_parser.add_argument('anki_file', help='Path to Anki file')
    import_parser.add_argument('--source', help='Source name')
    import_parser.add_argument('--raw', help='Raw OCR text file for context')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List entries')
    list_parser.add_argument('--status', help='Filter by status')
    list_parser.add_argument('--source', help='Filter by source')
    list_parser.add_argument('--limit', type=int, default=50, help='Max entries')
    
    # Correct command
    correct_parser = subparsers.add_parser('correct', help='Correct entry')
    correct_parser.add_argument('id', type=int, help='Entry ID')
    correct_parser.add_argument('--translation', required=True, help='New translation')
    
    # Find-match command
    find_parser = subparsers.add_parser('find-match', help='Find correct translation in raw OCR')
    find_parser.add_argument('id', type=int, help='Entry ID')
    find_parser.add_argument('--raw', required=True, help='Raw OCR text file')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export to Anki format')
    export_parser.add_argument('--output', default='output/exported_vocabulary.txt', help='Output file')
    export_parser.add_argument('--status', help='Filter by status (comma-separated)')
    
    # Stats command
    subparsers.add_parser('stats', help='Show statistics')
    
    # Interactive correct command
    interactive_parser = subparsers.add_parser('interactive', help='Interactive correction mode')
    interactive_parser.add_argument('--source', help='Filter by source')
    
    args = parser.parse_args()
    
    # Ensure database exists
    if args.command != 'init' and not DATABASE_PATH.exists():
        init_database()
    
    if args.command == 'init':
        init_database()
    elif args.command == 'import':
        import_anki_file(args.anki_file, args.source, args.raw)
    elif args.command == 'list':
        list_entries(args.status, args.source, args.limit)
    elif args.command == 'correct':
        correct_entry(args.id, args.translation)
    elif args.command == 'find-match':
        find_correct_translation(args.id, args.raw)
    elif args.command == 'export':
        export_vocabulary(args.output, args.status)
    elif args.command == 'stats':
        show_stats()
    elif args.command == 'interactive':
        interactive_correct(args.source)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
