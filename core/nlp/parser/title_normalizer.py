import re

try:
    import pymorphy3
    morph = pymorphy3.MorphAnalyzer()
except Exception:
    try:
        import pymorphy2
        morph = pymorphy2.MorphAnalyzer()
    except Exception:
        morph = None


def normalize_media_title(query: str) -> str:
    if not query:
        return ""

    words = query.strip().split()
    if not words:
        return ""

    if morph is not None:
        result_words = []
        for word in words:
            clean_word = re.sub(r'[^\w\-]', '', word).lower()
            if not clean_word:
                result_words.append(word)
                continue

            parses = morph.parse(clean_word)

            accs_candidate = None
            for p in parses:
                if 'accs' in p.tag:
                    accs_candidate = p
                    break

            if accs_candidate:
                inflected = accs_candidate.inflect({'nomn'})
                if inflected:
                    result_words.append(inflected.word)
                else:
                    result_words.append(accs_candidate.normal_form)
            else:
                result_words.append(clean_word)

        return " ".join(result_words)

    fallback_words = []
    for w in words:
        low = w.lower()
        if len(low) > 3 and low.endswith(('а', 'я')) and not low.endswith(('ия', 'ка')):
            fallback_words.append(low[:-1])
        elif len(low) > 3 and low.endswith('у'):
            fallback_words.append(low[:-1] + 'а')
        elif len(low) > 4 and low.endswith('ую'):
            fallback_words.append(low[:-2] + 'ая')
        else:
            fallback_words.append(low)

    return " ".join(fallback_words)