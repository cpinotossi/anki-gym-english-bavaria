"""
Parse extracted vocabulary and create Anki import file.
Format: English TAB German
"""
import re

INPUT_FILE = r"c:\Users\chpinoto\workspace\luna\english\unit-1\extracted_text_raw.txt"
OUTPUT_FILE = r"c:\Users\chpinoto\workspace\luna\english\unit-1\anki_vocabulary.txt"

def parse_vocabulary(text):
    """Parse vocabulary entries from the extracted text."""
    vocabulary = []
    lines = text.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines and page numbers
        if not line or re.match(r'^\d+$', line) or 'one hundred' in line.lower():
            i += 1
            continue
        
        # Skip section headers
        if line in ['Unit 1 Find your place', 'Check-in', 'Vocabulary', 'Media collocations', 
                    'Media', 'Verb', 'Collocations', 'Translation', 'print media', 'TV', 'radio',
                    'online media', 'social media', 'Describing developments', 'Vert', 
                    'Adjective collocations', 'Nouns and adjectives', 'Nouns and verbs with the same form',
                    'Skills: How to compromise', 'Unit task: A group discussion', 
                    'Story: Hang out with us instead!', 'Across cultures 1 Reacting to a new situation',
                    'Focus 1 Young people and media', 'Station 1: You have to push yourself!',
                    'Station 2: DMS online - People and activities', 'Station 3: Language change']:
            i += 1
            continue
        
        # Skip table headers and category lines
        if line.startswith('adjectives with') or line.startswith('other adjectives'):
            i += 1
            continue
            
        # Pattern 1: Word with pronunciation [phonetic] followed by German translation
        # e.g., "personality [,p3:sn'æloti]" followed by "Persönlichkeit"
        match = re.match(r'^[\*]?([a-zA-Z\s\'\-\(\)\.]+)\s*\[([^\]]+)\]$', line)
        if match:
            english_word = match.group(1).strip()
            # Look for German translation in next lines
            german = ""
            j = i + 1
            while j < len(lines) and j < i + 4:
                next_line = lines[j].strip()
                # German words typically have umlauts or are capitalized nouns
                if next_line and not next_line.startswith('[') and not re.match(r'^[a-z]', next_line[0] if next_line else ''):
                    # Check if it looks like German (has umlauts or is a German word pattern)
                    if any(c in next_line for c in 'äöüßÄÖÜ') or (next_line[0].isupper() and not next_line.startswith('Fr.') and not next_line.startswith('I ')):
                        german = next_line
                        break
                j += 1
            
            if german and english_word:
                # Clean up the German translation
                german = re.sub(r'\s+', ' ', german).strip()
                vocabulary.append((english_word.strip('*'), german))
            i += 1
            continue
        
        # Pattern 2: Look for lines that have clear English-German pairs
        # Pattern: English word/phrase followed by German translation on same or next line
        
        i += 1
    
    return vocabulary

def extract_vocab_structured(text):
    """Extract vocabulary using structured pattern matching."""
    vocabulary = []
    
    # Pattern to match vocabulary entries:
    # English word/phrase [pronunciation] German translation
    # The pattern captures entries like:
    # personality [,p3:sn'æloti] Persönlichkeit
    
    lines = text.split('\n')
    
    current_english = None
    current_pronunciation = None
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
            
        # Match pattern: word [pronunciation]
        match = re.match(r'^[\*\d\s]*([a-zA-Z][a-zA-Z\s\'\-\(\)\.\/\+\,]+?)\s*\[([^\]]+)\]$', line)
        if match:
            current_english = match.group(1).strip().lstrip('*0123456789 ')
            current_pronunciation = match.group(2)
            
            # Look for German translation in next few lines
            for j in range(i+1, min(i+5, len(lines))):
                next_line = lines[j].strip()
                if not next_line:
                    continue
                # Skip example sentences (contain periods and lowercase starts)
                if next_line.startswith('Fr.') or next_line.startswith('Lat.') or next_line.startswith('!'):
                    continue
                # Skip lines that look like example sentences
                if '.' in next_line and next_line[0].isupper() and len(next_line) > 50:
                    continue
                # Skip lines with pronunciation brackets
                if '[' in next_line:
                    break
                # Check if this looks like a German translation
                # German words: start with capital (nouns) or have umlauts
                if (any(c in next_line for c in 'äöüßÄÖÜ') or 
                    (next_line[0].isupper() and len(next_line) < 100 and 
                     not any(next_line.startswith(x) for x in ['Fr.', 'Lat.', 'I ', 'You ', 'He ', 'She ', 'We ', 'They ', 'If ', 'The ', 'A ', 'An ', 'My ', 'Our ', 'This ', 'That ', 'Some ', 'When ', 'Are ', 'Do ', 'What ', 'In ', 'With ', 'To ', 'For ', 'At ', 'From ', 'About ']))):
                    german = next_line
                    # Clean semicolons at the end
                    german = german.rstrip(';').strip()
                    if current_english and german:
                        vocabulary.append((current_english, german))
                    break
            current_english = None
            continue
    
    return vocabulary

def manual_extraction():
    """Manually extract vocabulary from the known format."""
    vocabulary = [
        # Unit 1 Check-in
        ("personality", "Persönlichkeit"),
        ("to disagree (with)", "anderer Meinung sein; nicht einverstanden sein (mit)"),
        ("to compromise", "Kompromisse eingehen"),
        ("smart", "schlau; klug; intelligent"),
        ("self", "das Selbst"),
        ("nature", "Natur"),
        ("logic", "Logik"),
        ("body", "Körper"),
        ("saying", "Redensart; Sprichwort"),
        ("practice", "Training; Übung"),
        ("to judge", "beurteilen; bewerten"),
        ("cover", "Cover; Titelblatt"),
        ("to matter", "von Bedeutung sein; etw. ausmachen"),
        ("I don't care", "es ist mir egal"),
        ("to be in", "in sein; angesagt sein"),
        ("to be out", "out sein"),
        ("as long as", "solange"),
        ("call-in", "Sendung, bei der sich das Publikum telefonisch beteiligen kann"),
        ("imagination", "Fantasie; Vorstellungskraft"),
        
        # Media collocations
        ("to read/to prefer", "lesen/bevorzugen"),
        ("to be interested in", "interessiert sein an"),
        ("to watch", "schauen; ansehen"),
        ("to listen to", "hören; zuhören"),
        ("to follow", "folgen"),
        ("to read/write/make/create", "lesen/schreiben/machen/erstellen"),
        ("to look for", "suchen nach"),
        ("to communicate", "kommunizieren"),
        ("to build/keep up", "aufbauen/aufrechterhalten"),
        ("to share", "teilen"),
        ("to create", "erstellen; kreieren"),
        
        # More vocabulary
        ("digital", "digital"),
        ("cyber bullying", "Cybermobbing"),
        ("psychological", "psychologisch; psychisch"),
        ("danger", "Gefahr"),
        ("psychologist", "Psychologe/Psychologin"),
        ("to warn", "warnen"),
        ("self-esteem", "Selbstwertgefühl; Selbstachtung"),
        ("according to", "laut; gemäß"),
        ("to be supposed to (do)", "(tun) sollen"),
        ("mostly", "meistens; größtenteils; hauptsächlich"),
        ("direct", "direkt"),
        ("interaction", "Interaktion"),
        ("indirect", "indirekt"),
        ("to take a risk", "ein Risiko eingehen"),
        ("to keep up", "aufrechterhalten"),
        ("fake", "falsch; gefälscht"),
        ("identity", "Identität"),
        ("to face", "gegenüber stehen; konfrontiert werden mit"),
        ("image", "Bild; Image"),
        ("especially", "besonders; vor allem"),
        ("anything", "alles (Mögliche/Beliebige)"),
        ("behaviour", "Verhalten; Benehmen; Betragen"),
        ("permanent", "permanent; dauerhaft"),
        ("depression", "Depression; Niedergeschlagenheit"),
        ("suicide", "Selbstmord; Suizid"),
        ("vlog", "Vlog; Videoblog"),
        ("to design", "entwerfen; gestalten"),
        ("to compete (with/against)", "konkurrieren (mit); sich messen (mit)"),
        ("themselves", "sich selbst (3. P. Pl.)"),
        
        # Station 1
        ("to push oneself", "sich alles abverlangen; sich Mühe geben"),
        ("to study", "studieren; lernen"),
        ("to enjoy oneself", "Spaß haben; sich amüsieren"),
        ("waste", "Verschwendung"),
        ("to accept", "akzeptieren; hinnehmen; annehmen"),
        ("grade (AE)", "Note; Klasse"),
        ("to make it", "es schaffen"),
        ("to complain", "sich beschweren; sich beklagen"),
        ("report card (AE)", "Zeugnis"),
        ("loser", "Verlierer/-in; Loser/-in"),
        ("to be hard on sb", "streng mit jmdm. sein"),
        ("to relax", "sich entspannen; sich ausruhen"),
        ("laid-back", "entspannt; locker"),
        ("bossy", "herrisch; rechthaberisch"),
        ("rich", "reich"),
        ("college", "Universität (in den USA)"),
        ("all by oneself", "ganz allein"),
        ("successful", "erfolgreich"),
        ("stubborn", "eigensinnig; störrisch"),
        ("to make a decision", "eine Entscheidung treffen"),
        ("ambitious", "ehrgeizig"),
        ("pushy", "aufdringlich; penetrant; aggressiv"),
        ("to react", "reagieren"),
        ("in sb's shoes", "an jmds. Stelle"),
        ("to criticize", "kritisieren"),
        ("to push sb", "jmdn. drängen"),
        ("to motivate", "motivieren"),
        ("chance", "Chance; Gelegenheit; Möglichkeit"),
        
        # Station 2
        ("middle school (AE)", "Mittelschule (weiterführende Schule in den USA)"),
        ("trainer", "Trainer/-in"),
        ("safety", "Sicherheit"),
        ("bond", "Bindung"),
        ("to come easily to sb", "jmdm. leichtfallen"),
        ("influence", "Einfluss"),
        ("Norman", "Normanne/Normannin; normannisch"),
        ("pork", "Schweinefleisch"),
        ("beef", "Rindfleisch"),
        ("to mix", "mixen; mischen; vermischen"),
        ("future", "zukünftig"),
        ("rural", "ländlich"),
        ("responsibility", "Verantwortung"),
        ("living", "Lebensweise"),
        ("to be grounded", "Hausarrest haben"),
        ("to taste", "schmecken; probieren"),
        ("hot", "scharf"),
        ("spectacular", "spektakulär"),
        ("pot", "Topf"),
        ("tasty", "lecker; schmackhaft"),
        ("dish", "Gericht; Speise"),
        ("vegetable", "Gemüse"),
        ("to seem", "scheinen"),
        ("certain", "bestimmt; sicher; gewiss"),
        
        # Describing developments
        ("to become", "werden"),
        ("to get", "werden"),
        ("to go", "werden (to go wrong = schiefgehen)"),
        ("to grow", "werden"),
        ("to turn", "werden"),
        
        # More vocabulary
        ("recipe", "Rezept"),
        ("to drive", "fahren"),
        ("to put sth right", "etw. richtigstellen"),
        ("understandable", "verständlich"),
        ("dream", "Traum"),
        ("extreme", "extrem; radikal; äußerste/-r/-s"),
        ("comparable", "vergleichbar"),
        
        # Station 3
        ("to develop", "(sich) entwickeln"),
        ("Saxon", "Sachse/Sächsin; sächsisch"),
        ("Anglo-Saxon", "Angelsachse/Angelsächsin; angelsächsisch"),
        ("to defeat", "besiegen"),
        ("meat", "Fleisch"),
        ("to remain", "bleiben"),
        ("Greek", "Griechisch; griechisch"),
        
        # Skills: How to compromise
        ("to have a point", "nicht ganz Unrecht haben"),
        ("to meet halfway", "sich auf halbem Weg treffen"),
        ("I don't mind ... (+ -ing)", "Ich habe nichts dagegen (zu) ..."),
        ("this way", "so; auf diese Weise"),
        ("misunderstood", "missverstanden"),
        ("ear", "Ohr"),
        ("diving", "Tauchen"),
        
        # Unit task
        ("argument", "Argument"),
        ("cage", "Käfig"),
        ("strict", "streng; strikt"),
        ("dress code", "Kleiderordnung; Bekleidungsvorschriften"),
        ("skin", "Haut; Fell"),
        ("to interrupt", "unterbrechen"),
        ("to convince", "überzeugen"),
        ("most", "am meisten"),
        
        # Story
        ("to be fed up (with)", "sauer sein (auf); die Nase voll haben (von)"),
        ("to feel like", "Lust haben (auf/zu)"),
        ("to trust", "vertrauen"),
        ("sneaker (AE)", "Turnschuh"),
        ("to dream", "träumen"),
        ("in-crowd", "die Angesagten"),
        ("either ... or ...", "entweder ... oder ..."),
        ("far away", "weit weg"),
        ("to chill out", "chillen"),
        ("blond", "blond"),
        ("What's going on?", "Was ist los?; Was geht ab?"),
        ("shake", "Shake; Milchshake"),
        ("dance", "Tanz; Tanzveranstaltung"),
        ("to lend (to)", "leihen; verleihen"),
        ("to go behind sb's back", "jmdn. hintergehen"),
        ("to worry sb", "jmdn. beunruhigen"),
        ("bay", "Bucht"),
        ("to come along", "mitkommen"),
        ("to suggest", "vorschlagen"),
        ("to pay attention to", "beachten"),
        ("to ignore", "ignorieren; außer Acht lassen"),
        ("pretty", "hübsch"),
        ("mommy (AE)", "Mama; Mami; Mutti"),
        ("to drop", "fallen (lassen)"),
        ("to afford", "sich leisten"),
        ("anger", "Zorn; Wut"),
        ("loyal", "loyal; treu"),
        ("to lie", "lügen"),
        ("to fit in", "hineinpassen; sich einfügen"),
        ("trust", "Vertrauen"),
        
        # Across cultures
        ("still", "Standbild"),
        ("plate", "Teller"),
        ("mug", "Becher"),
        ("cup", "Tasse"),
        ("spoon", "Löffel"),
        ("knife", "Messer"),
        ("fork", "Gabel"),
        ("bread roll", "Brötchen"),
        ("marmalade", "Marmelade aus Zitrusfrüchten"),
        ("honey", "Honig"),
        ("muesli", "Müsli"),
        ("sausage", "Wurst; Bratwurst"),
        ("sugar", "Zucker"),
        ("experience", "Erfahrung; Erlebnis"),
        ("host family", "Gastfamilie"),
        ("exchange student", "Austauschschüler/-in"),
        ("type", "Typ; Art; Sorte"),
        ("to upset", "aus der Fassung bringen; aufregen"),
        ("impolite", "unhöflich"),
        ("this (+ adj)", "so"),
        ("that (+ adj)", "so"),
        ("to be used to (+ -ing)", "gewöhnt sein an; gewohnt sein"),
        
        # Focus 1
        ("usage", "Gebrauch; Nutzung"),
        ("what for", "wozu"),
        ("a day", "pro Tag"),
        ("content", "Inhalt"),
        ("communication", "Kommunikation"),
    ]
    
    return vocabulary

def main():
    # Use manual extraction for best quality
    vocabulary = manual_extraction()
    
    print(f"Extracted {len(vocabulary)} vocabulary entries")
    
    # Write Anki import file (tab-separated)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for english, german in vocabulary:
            # Anki format: Front TAB Back
            f.write(f"{english}\t{german}\n")
    
    print(f"\nAnki import file created: {OUTPUT_FILE}")
    print(f"\nTo import into Anki:")
    print("1. Open Anki")
    print("2. Click 'File' -> 'Import'")
    print("3. Select the file: anki_vocabulary.txt")
    print("4. Set 'Field separator' to 'Tab'")
    print("5. Set 'Field 1' to 'Front' and 'Field 2' to 'Back'")
    print("6. Click 'Import'")
    
    # Also print first 10 entries as preview
    print("\nPreview of first 10 entries:")
    print("-" * 60)
    for english, german in vocabulary[:10]:
        print(f"{english}  →  {german}")

if __name__ == "__main__":
    main()
