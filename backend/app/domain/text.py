import hashlib
import html
import re
import unicodedata


class TextFingerprinter:
    """Normalises text and computes exact (sha256) and near-duplicate (simhash) fingerprints."""

    _WS = re.compile(r"\s+")
    _TAG = re.compile(r"<[^>]+>")
    _TOKEN = re.compile(r"\w+", re.UNICODE)
    _PUNCT = re.compile(r"[^\w\s]", re.UNICODE)

    def __init__(self, near_dup_max_hamming: int = 8):
        # >10 starts merging unrelated stories; 8 catches re-headlined wire copies.
        self.near_dup_max_hamming = near_dup_max_hamming

    def clean(self, text: str) -> str:
        return self._WS.sub(" ", self._TAG.sub(" ", html.unescape(text or ""))).strip()

    @staticmethod
    def fold(text: str) -> str:
        return unicodedata.normalize("NFC", text or "").casefold()

    def content_hash(self, text: str) -> str:
        return hashlib.sha256(self.fold(self.clean(text)).encode("utf-8")).hexdigest()

    def norm_name(self, name: str) -> str:
        return self._WS.sub(" ", self._PUNCT.sub(" ", self.fold(name))).strip()

    def simhash(self, text: str) -> int:
        """64-bit simhash over word 3-grams, returned signed so it fits Postgres BIGINT."""
        tokens = self._TOKEN.findall(self.fold(text))
        shingles = [" ".join(tokens[i:i + 3]) for i in range(max(1, len(tokens) - 2))] or [""]
        weights = [0] * 64
        for shingle in shingles:
            h = int.from_bytes(hashlib.blake2b(shingle.encode("utf-8"), digest_size=8).digest(), "big")
            for bit in range(64):
                weights[bit] += 1 if (h >> bit) & 1 else -1
        value = 0
        for bit in range(64):
            if weights[bit] > 0:
                value |= 1 << bit
        return value - (1 << 64) if value >= (1 << 63) else value

    @staticmethod
    def hamming(a: int, b: int) -> int:
        return bin((a ^ b) & ((1 << 64) - 1)).count("1")

    def is_near_duplicate(self, a: int, b: int) -> bool:
        return self.hamming(a, b) <= self.near_dup_max_hamming

    _STOPWORDS = frozenset({"a", "an", "the", "of", "in", "on", "at", "for", "to", "and", "as", "is", "are",
                            "amid", "with", "by", "from", "over", "after", "says", "say"})

    def headline_tokens(self, title: str) -> frozenset[str]:
        """Content words of a headline, without the trailing ' - Publisher' that news aggregators append."""
        head, sep, tail = (title or "").rpartition(" - ")
        if sep and len(tail.split()) <= 5:
            title = head
        return frozenset(t for t in self._TOKEN.findall(self.fold(title)) if t not in self._STOPWORDS)

    def headline_similarity(self, a: str, b: str) -> float:
        """Jaccard overlap of headline content words: catches reordered/re-worded wire headlines."""
        ta, tb = self.headline_tokens(a), self.headline_tokens(b)
        return len(ta & tb) / len(ta | tb) if ta and tb else 0.0
