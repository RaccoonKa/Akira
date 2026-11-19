import sys

# 1. Прямые импорты из новых вложенных пакетов
from core.nlp.parser import command_parser
from core.nlp.parser import nlu
from core.nlp.parser import title_normalizer

from core.nlp.generative import llm_provider
from core.nlp.generative import lore_rag
from core.nlp.generative import memory
from core.nlp.generative import document_parser

from core.nlp.speech import speaker_verifier
from core.nlp.speech import asr_corrector
from core.nlp.emotion import text_emotion_classifier

# 2. Мост в sys.modules для поддержки старых путей (from core.nlp.command_parser import ...)
sys.modules['core.nlp.command_parser'] = command_parser
sys.modules['core.nlp.nlu'] = nlu
sys.modules['core.nlp.title_normalizer'] = title_normalizer

sys.modules['core.nlp.llm_provider'] = llm_provider
sys.modules['core.nlp.lore_rag'] = lore_rag
sys.modules['core.nlp.memory'] = memory
sys.modules['core.nlp.document_parser'] = document_parser

sys.modules['core.nlp.speaker_verifier'] = speaker_verifier
sys.modules['core.nlp.asr_corrector'] = asr_corrector
sys.modules['core.nlp.text_emotion_classifier'] = text_emotion_classifier

def __getattr__(name):
    if name == "slot_filler":
        from core.nlp.parser import slot_filler
        sys.modules['core.nlp.slot_filler'] = slot_filler
        return slot_filler
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

# 3. Прямой экспорт ключевых классов для импорта из core.nlp
from core.nlp.parser.command_parser import CommandParser
from core.nlp.speech.asr_corrector import ASRCorrector
from core.nlp.generative.llm_provider import OpenRouterProvider, GigaChatProvider
from core.nlp.generative.lore_rag import LoreRAG
from core.nlp.generative.memory import MemoryManager