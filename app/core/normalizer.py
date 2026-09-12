"""
Normalizer module for cleaning and grouping merchant descriptions.
"""
import re
from collections import Counter, defaultdict
from typing import List, Dict
from rapidfuzz import fuzz

# Why: below 80 -> false merges like AMAZON/AMAZON MUSIC;
# above 90 -> misses real variants like 'NETFLIX.COM 8X4F2' vs 'NETFLIX INC'.
# 85 is the documented midpoint validated by tests.
FUZZY_THRESHOLD: int = 85

# Ordered, explainable aliases for common statement variants. These are merchant
# identities, not a subscription allow-list: recurrence is still required later.
MERCHANT_ALIASES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bNETFLIX\b"), "NETFLIX"),
    (re.compile(r"\bSPOTIFY\b"), "SPOTIFY"),
    (re.compile(r"\b(?:AMAZON|AMZN)\b.*\bPRIME\b|\bPRIME\b.*\b(?:AMAZON|AMZN)\b|^PRIME$"), "AMAZON PRIME"),
    (re.compile(r"\bICLOUD\b"), "ICLOUD"),
    (re.compile(r"\bYOUTUBE\b|\bYOUTUBEPREMIUM\b|\bYT\s*PREMIUM\b"), "YOUTUBE PREMIUM"),
    (re.compile(r"\bLINKEDIN\b"), "LINKEDIN"),
    (re.compile(r"\bDROPBOX\b"), "DROPBOX"),
    (re.compile(r"\bHOTSTAR\b"), "HOTSTAR"),
)

def clean_description(raw: str) -> str:
    """
    Cleans a raw merchant description using a rule-based approach.

    Order matters — step 4 (.com suffixes) must run before step 5 (filler words):
      'NETFLIX.COM' → strip '.COM' suffix → 'NETFLIX'  ✓
      If step 5 ran first: 'COM' removed as word → 'NETFLIX.' → suffix regex
      finds no match (dot not followed by COM) → stray dot remains.

    Transaction-ID regex (step 3) only strips tokens that contain at least one
    digit — this avoids stripping real merchant names that happen to be ≥6 chars
    (NETFLIX, SPOTIFY, DROPBOX etc. are pure-alpha and are left alone).
    """
    cleaned = raw.upper().strip()

    # 1. Payment-processor prefixes (anchored at start)
    cleaned = re.sub(r'^(SQ\s*\*|TST\*|PAYPAL\s*\*|AMZN\s*MKTP\s*|SP\s*\*)', '', cleaned)

    # 2. Store numbers (#4471 etc.)
    cleaned = re.sub(r'#\d+', '', cleaned)

    # 3. Transaction-ID noise: tokens that contain at least one digit
    #    e.g. '8X4F2', 'AB1234', '4471' — but NOT 'NETFLIX', 'SPOTIFY'
    cleaned = re.sub(r'\b[A-Z0-9]*\d[A-Z0-9]*\b', '', cleaned)

    # 4. Domain suffixes — MUST run before filler-word removal (see docstring)
    cleaned = re.sub(r'\.(COM|NET|IO|CO)\b', '', cleaned)

    # 5. Filler corporate suffixes (whole-word only)
    cleaned = re.sub(r'\b(INC|LLC|LTD|PVT|CO|CORP|COM)\b', '', cleaned)

    # 6. Strip stray trailing/leading punctuation left by earlier passes
    cleaned = cleaned.strip('.*-_/\\')

    # 7. Collapse interior whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    for pattern, canonical in MERCHANT_ALIASES:
        if pattern.search(cleaned):
            return canonical
    return cleaned

class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))
    
    def find(self, i):
        if self.parent[i] == i:
            return i
        self.parent[i] = self.find(self.parent[i])
        return self.parent[i]
    
    def union(self, i, j):
        root_i = self.find(i)
        root_j = self.find(j)
        if root_i != root_j:
            self.parent[root_i] = root_j

def group_merchants(descriptions: List[str]) -> Dict[str, List[int]]:
    """
    Groups merchants using exact normalization plus blocked fuzzy matching.

    Comparisons are made only between unique normalized names that share a
    blocking key (first token or leading trigram). This avoids the previous
    all-transaction O(n²) scan while retaining transitive Union-Find grouping.
    Why token_sort_ratio: handles word-order variants like 'NETFLIX INC' vs 'INC NETFLIX'
    """
    n = len(descriptions)
    cleaned_desc = [clean_description(d) for d in descriptions]
    
    uf = UnionFind(n)
    
    by_name: dict[str, list[int]] = defaultdict(list)
    for index, name in enumerate(cleaned_desc):
        by_name[name].append(index)

    representatives: dict[str, int] = {}
    for name, indices in by_name.items():
        representatives[name] = indices[0]
        for index in indices[1:]:
            uf.union(indices[0], index)

    blocks: dict[str, set[str]] = defaultdict(set)
    for name in by_name:
        tokens = name.split()
        if tokens:
            blocks[f"token:{tokens[0]}"].add(name)
        compact = re.sub(r"\W", "", name)
        if compact:
            blocks[f"prefix:{compact[:3]}"].add(name)

    candidate_pairs: set[tuple[str, str]] = set()
    for names in blocks.values():
        ordered = sorted(names)
        for i, left in enumerate(ordered):
            for right in ordered[i + 1:]:
                candidate_pairs.add((left, right))

    for left, right in candidate_pairs:
        if fuzz.token_sort_ratio(left, right) >= FUZZY_THRESHOLD:
            uf.union(representatives[left], representatives[right])
                
    groups = {}
    for i in range(n):
        root = uf.find(i)
        if root not in groups:
            groups[root] = []
        groups[root].append(i)
        
    result = {}
    for root, indices in groups.items():
        # Canonical name = shortest cleaned name in the group
        canonical_name = min([cleaned_desc[idx] for idx in indices], key=len)
        result[canonical_name] = indices
        
    return result

def compute_merchant_strength(group_descriptions: List[str]) -> float:
    """
    Computes the frequency-weighted mean similarity over unique cleaned names.
    Each unique pair is fuzzed once, so repeated transactions add O(1) weight
    rather than another fuzzy comparison.
    Returns 1.0 for single-member groups.
    """
    n = len(group_descriptions)
    if n <= 1:
        return 1.0
        
    counts = Counter(clean_description(d) for d in group_descriptions)
    total_score = 0.0
    pairs = 0

    names = sorted(counts)
    for name, count in counts.items():
        identical_pairs = count * (count - 1) // 2
        total_score += 100 * identical_pairs
        pairs += identical_pairs
    for i, left in enumerate(names):
        for right in names[i + 1:]:
            weight = counts[left] * counts[right]
            total_score += fuzz.token_sort_ratio(left, right) * weight
            pairs += weight
            
    mean_score = (total_score / pairs) / 100.0 if pairs else 1.0
    return max(0.0, min(1.0, mean_score))
