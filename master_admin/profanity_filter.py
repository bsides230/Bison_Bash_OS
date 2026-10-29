import re
from typing import Tuple

# Common character substitution map for leetspeak bypass attempts
LEET_MAP = {
    '@': 'a', '4': 'a', '^': 'a',
    '8': 'b',
    '(': 'c', '<': 'c', '{': 'c', '[': 'c',
    '3': 'e', '€': 'e',
    '6': 'g', '9': 'g',
    '#': 'h',
    '!': 'i', '1': 'i', '|': 'i', ';': 'i', ':': 'i',
    '0': 'o',
    '$': 's', '5': 's', 'z': 's',
    '7': 't', '+': 't',
    'v': 'u',
    'w': 'vv',
    '%': 'x',
    '¥': 'y'
}

# Exact word matches (checked with word boundaries to avoid Scunthorpe problem like 'grass', 'bass', 'classic')
EXACT_PROFANITY_WORDS = {
    "ass", "asses", "asshole", "assholes", "arse", "bastard", "bastards",
    "bitch", "bitches", "bitching", "bitchy", "blowjob", "blowjobs", "bollocks", "boner",
    "bullshit", "cock", "cocks", "cocksucker", "crap", "cunt", "cunts",
    "dick", "dicks", "dickhead", "dildo", "douche", "douchebag",
    "fag", "faggot", "faggots", "fuck", "fucker", "fuckers", "fucking", "fucks",
    "goddamn", "hell", "homo", "jackass", "jerkoff", "jizz", "kike",
    "motherfucker", "nazi", "nigga", "nigger", "niggers", "orgasm",
    "penis", "piss", "pissed", "prick", "pussy", "pussies",
    "retard", "retarded", "scrotum", "shit", "shits", "shitty", "shitting",
    "slut", "sluts", "smegma", "spic", "tits", "titties", "twat",
    "vagina", "wank", "wanker", "whore", "whores"
}

# Substring matches for terms that should NEVER appear anywhere in a name, even embedded
SEVERE_SUBSTRINGS = [
    "nigger", "nigga", "faggot", "cunt", "motherfuck", "childporn", "pedophil"
]

def normalize_text(text: str) -> str:
    """Normalizes text by lowering case, translating leetspeak, and removing punctuation."""
    text = text.lower().strip()
    
    # Translate leet characters
    translated = []
    for char in text:
        translated.append(LEET_MAP.get(char, char))
    norm = "".join(translated)
    return norm

def is_profane(name: str) -> bool:
    """Returns True if the name contains profanity or offensive terms."""
    if not name:
        return False
        
    raw_lower = name.lower()
    norm = normalize_text(name)
    
    # 1. Check severe substrings in raw and normalized versions
    for sub in SEVERE_SUBSTRINGS:
        if sub in raw_lower or sub in norm:
            return True
        # Also check without spaces/punctuation (e.g. "n.i.g.g.a")
        stripped = re.sub(r'[^a-z0-9]', '', norm)
        if sub in stripped:
            return True

    # 2. Tokenize by splitting on non-alphanumeric characters AND underscores
    tokens_raw = set(re.split(r'[^a-z0-9]+', raw_lower))
    tokens_norm = set(re.split(r'[^a-z0-9]+', norm))
    
    all_tokens = {t for t in tokens_raw.union(tokens_norm) if t}
    for token in all_tokens:
        # Check direct token
        if token in EXACT_PROFANITY_WORDS:
            return True
        # Collapse multiple consecutive identical characters (e.g., 'fuuuuck' -> 'fuck')
        collapsed = re.sub(r'(.)\1+', r'\1', token)
        if collapsed in EXACT_PROFANITY_WORDS:
            return True
        # Also try collapsing to 2 characters (e.g., 'asss' -> 'ass')
        collapsed2 = re.sub(r'(.)\1{2,}', r'\1\1', token)
        if collapsed2 in EXACT_PROFANITY_WORDS:
            return True

    # 3. Check for spaced-out or punctuation-separated swearwords (e.g. "f-u-c-k", "f u c k", "b_i_t_c_h")
    # For obfuscated words, we compare stripped string against swearwords
    # To prevent 'hello' matching 'hell' or 'grass' matching 'ass', we require boundary or exact token match
    stripped_alphanumeric = re.sub(r'[^a-z0-9]', '', norm)
    stripped_collapsed = re.sub(r'(.)\1+', r'\1', stripped_alphanumeric)
    
    # Check if any profane word was obfuscated with spaces/punctuation
    for word in EXACT_PROFANITY_WORDS:
        # Word boundary search in normalized text (e.g. "hello" won't match "\bhell\b")
        if re.search(r'\b' + re.escape(word) + r'\b', norm):
            return True
            
        # Obfuscation check: if the user typed "f u c k" or "s.h.i.t", the stripped version matches
        if len(word) >= 4:
            # If word is an exact match to the stripped string or separated by spaces originally
            if stripped_alphanumeric == word or stripped_collapsed == word:
                return True
            # For severe words of length 4+, check if contained in stripped
            if word in ["fuck", "cunt", "shit", "bitch", "nigger", "faggot", "dick", "pussy"]:
                if word in stripped_alphanumeric or word in stripped_collapsed:
                    return True

    return False

def validate_player_name(name: str) -> Tuple[bool, str]:
    """
    Validates a player's screen name for the event.
    Returns (True, "OK") if valid, or (False, reason) if invalid.
    """
    if not name or not name.strip():
        return False, "Player name cannot be empty."
        
    trimmed = name.strip()
    
    if len(trimmed) < 2:
        return False, "Player name must be at least 2 characters long."
        
    if len(trimmed) > 24:
        return False, "Player name cannot exceed 24 characters."
        
    # Check for allowable characters (alphanumeric, spaces, dashes, underscores, periods)
    if not re.match(r'^[a-zA-Z0-9\s_\-\.]+$', trimmed):
        return False, "Player name contains invalid characters. Use letters, numbers, spaces, or simple punctuation."
        
    # Check for profanity
    if is_profane(trimmed):
        return False, "Please choose a family-friendly player name without profanity or inappropriate words."
        
    return True, "OK"
