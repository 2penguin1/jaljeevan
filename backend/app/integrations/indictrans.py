"""Local Marathi/Hindi/... -> English translation with AI4Bharat IndicTrans2 (runs on this machine's CPU).

Used only by the offline declaration extractor, to read order titles and severity words. Taluka names are
transliterated instead (app/domain/declarations.py), because a translation model can change proper nouns.

Needs the optional install `uv sync --extra indic` (torch, transformers<5, IndicTransToolkit) and, because the
model is gated on Hugging Face, an accepted licence plus HF_TOKEN in backend/.env. ~1 GB downloads once.
"""
from functools import cached_property

from app.core.exceptions import ExternalServiceError

LANGS = {"mr": "mar_Deva", "hi": "hin_Deva", "kn": "kan_Knda", "ta": "tam_Taml", "te": "tel_Telu", "gu": "guj_Gujr",
         "bn": "ben_Beng"}


class IndicTranslator:
    SERVICE = "indictrans2"
    MODEL = "ai4bharat/indictrans2-indic-en-dist-200M"

    def __init__(self, token: str | None, model: str = MODEL, batch_size: int = 8):
        self.token = token
        self.model_name = model
        self.batch_size = batch_size

    @cached_property
    def _parts(self):
        try:
            import torch  # noqa: F401
            from IndicTransToolkit.processor import IndicProcessor
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError:
            raise ExternalServiceError(self.SERVICE, "not installed: run `uv sync --extra indic`", retryable=False) from None
        try:
            tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True, token=self.token)
            model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name, trust_remote_code=True, token=self.token)
        except OSError as exc:
            gated = "gated" in str(exc).lower() or "401" in str(exc) or "403" in str(exc)
            reason = ("model is gated: accept the licence on huggingface.co and set HF_TOKEN in backend/.env"
                      if gated else f"model could not be loaded ({type(exc).__name__})")
            raise ExternalServiceError(self.SERVICE, reason, retryable=False) from None
        model.eval()
        return tokenizer, model, IndicProcessor(inference=True)

    def translate(self, texts: list[str], src_lang: str = "mr") -> list[str]:
        if not texts:
            return []
        import torch

        tokenizer, model, processor = self._parts
        src = LANGS.get(src_lang, src_lang)
        out: list[str] = []
        for i in range(0, len(texts), self.batch_size):
            batch = processor.preprocess_batch(texts[i:i + self.batch_size], src_lang=src, tgt_lang="eng_Latn")
            inputs = tokenizer(batch, truncation=True, padding="longest", return_tensors="pt")
            with torch.no_grad():
                generated = model.generate(**inputs, max_length=256, num_beams=4)
            decoded = tokenizer.batch_decode(generated, skip_special_tokens=True, clean_up_tokenization_spaces=True)
            out += processor.postprocess_batch(decoded, lang="eng_Latn")
        return out
