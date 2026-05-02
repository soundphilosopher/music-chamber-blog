"""
Genre normalization utilities.
"""

import re


_SPELLING_MAP = {
    "lofi": "LoFi", "rock'n'roll": "Rock'n'Roll", "uk": "UK", "edm": "EDM", "idm": "IDM",
    "ebm": "EBM", "ibm": "IBM", "dsbm": "DSBM", "rabm": "RABM", "nwobhm": "NWOBHM", "nwoahm": "NWOAHM",
    "j-pop": "J-Pop", "j-rock": "J-Rock", "j-folk": "J-Folk", "d-beat": "D-Beat", "r&b": "R&B", "avant-garde": "Avant-Garde",
    "avantgarde": "Avant-Garde", "scifi": "SciFi", "sci-fi": "SciFi", "ndw": "Neue Deutsche Welle", "avant": "Avant-Garde",
    "prog": "Progressive", "alt": "Alternative", "psych": "Psychedelic", "atmo": "Atmospheric", "melo": "Melodic",
    "mellow": "Melodramatic", "cine": "Cinematic", "tech": "Technical", "osdm": "Old School Death Metal",
    "medi": "Mediterranean", "ndh": "Neue Deutsche Härte", "k-pop": "K-Pop", "digi": "Digital", "black'n'roll": "Black'n'Roll",
    "d&b": "Drum & Bass", "g-funk": "G-Funk", "goth": "Gothic", "nwothm": "NWOTHM"
}
GENRE_TAG_PREFIX = "::genre::"
GENRE_TAG_PATTERN = re.compile(rf"^{re.escape(GENRE_TAG_PREFIX)}")


def normalize_genre_names(genre_names: list[str]) -> list[str]:
    """Normalize the capitalization of a list of genre names.

    Each word in a genre name is capitalized (title case) unless it
    matches a key in ``_SPELLING_MAP``, in which case the mapped
    spelling is used instead (e.g. "lofi" → "LoFi", "dsbm" → "DSBM").

    Args:
        genre_names: Lowercased genre name strings
            (e.g. ``["lofi hip hop", "death metal", "uk garage"]``).

    Returns:
        Genre names with corrected capitalization
            (e.g. ``["LoFi Hip Hop", "Death Metal", "UK Garage"]``).
    """
    result = []

    for genre in genre_names:
        words = genre.split(" ")
        normalized_words = [
            # Use the SPELLING_MAP override if the word has one,
            # otherwise just capitalize the first letter.
            _SPELLING_MAP[word] if word in _SPELLING_MAP else word.capitalize()
            for word in words
        ]
        result.append(" ".join(normalized_words))

    return result
