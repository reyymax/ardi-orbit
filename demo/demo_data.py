"""Realistic multilingual riddle corpus + canned LLM responses for the demo.

These are NOT live riddles from the Ardi WorkNet — they are well-known
folk / classical riddles from each language's tradition, used purely to
demonstrate the solver/strategy pipeline in a recording-friendly way.
"""

from __future__ import annotations

from dataclasses import dataclass

from ardi_orbit.models import Language


@dataclass(frozen=True)
class DemoRiddle:
    word_id: int
    language: Language
    prompt: str
    # Canned solver output:
    mock_answer: str
    mock_confidence: float
    mock_reasoning: str
    mock_alternates: tuple[str, ...] = ()


DEMO_EPOCH = 142


DEMO_RIDDLES: tuple[DemoRiddle, ...] = (
    DemoRiddle(
        word_id=0,
        language=Language.EN,
        prompt="I have cities, but no houses. I have mountains, but no trees. I have water, but no fish. What am I?",
        mock_answer="map",
        mock_confidence=0.96,
        mock_reasoning="Classic English enumeration riddle: subject contains representations of places without the actual objects. Canonical answer is 'map'.",
        mock_alternates=("atlas", "globe"),
    ),
    DemoRiddle(
        word_id=1,
        language=Language.ZH,
        prompt="什么东西越洗越脏？",
        mock_answer="水",
        mock_confidence=0.92,
        mock_reasoning="经典中文谜语。字面：什么东西越洗它越脏。洗东西时，脏东西进入水中，所以水越用越脏。答案：水。",
        mock_alternates=("抹布",),
    ),
    DemoRiddle(
        word_id=2,
        language=Language.ID,
        prompt="Apa yang selalu datang, tapi tidak pernah tiba?",
        mock_answer="besok",
        mock_confidence=0.88,
        mock_reasoning="Teka-teki klasik Indonesia. 'Besok' selalu dalam perjalanan tetapi setelah tiba jadi 'hari ini'.",
        mock_alternates=("hari esok",),
    ),
    DemoRiddle(
        word_id=3,
        language=Language.JA,
        prompt="食べれば食べるほど増えるものは？",
        mock_answer="年",
        mock_confidence=0.81,
        mock_reasoning="日本のなぞなぞ。『食べる』が『歳を取る』の比喩になっている。答え：年（とし）。",
        mock_alternates=("歳",),
    ),
    DemoRiddle(
        word_id=4,
        language=Language.KO,
        prompt="눈이 두 개 있지만 볼 수 없는 것은?",
        mock_answer="단추",
        mock_confidence=0.72,
        mock_reasoning="한국 전통 수수께끼. '눈'은 단추 구멍을 가리키는 은유. 답: 단추.",
        mock_alternates=("주사위",),
    ),
    DemoRiddle(
        word_id=5,
        language=Language.AR,
        prompt="ما الشيء الذي كلما زاد نقص؟",
        mock_answer="العمر",
        mock_confidence=0.87,
        mock_reasoning="لغز عربي كلاسيكي. كلما زاد عمر الإنسان نقص ما تبقى من حياته. الإجابة: العمر.",
    ),
    DemoRiddle(
        word_id=6,
        language=Language.ES,
        prompt="Oro parece, plata no es. El que no lo adivine bien tonto es. ¿Qué es?",
        mock_answer="plátano",
        mock_confidence=0.97,
        mock_reasoning="Adivinanza clásica española. Juego de palabras: 'plata no es' suena como 'plátano es'. Respuesta: plátano.",
        mock_alternates=("banana",),
    ),
    DemoRiddle(
        word_id=7,
        language=Language.FR,
        prompt="Plus on en prend, plus on en laisse. Qu'est-ce que c'est?",
        mock_answer="empreintes",
        mock_confidence=0.83,
        mock_reasoning="Devinette française. Plus on fait de pas, plus on laisse de traces derrière soi. Réponse canonique: empreintes (pas).",
        mock_alternates=("pas", "traces"),
    ),
    DemoRiddle(
        word_id=8,
        language=Language.DE,
        prompt="Was hat Städte ohne Häuser, Wälder ohne Bäume und Flüsse ohne Wasser?",
        mock_answer="landkarte",
        mock_confidence=0.94,
        mock_reasoning="Klassisches deutsches Rätsel, strukturell identisch zum englischen 'map'-Rätsel. Antwort: Landkarte.",
        mock_alternates=("karte",),
    ),
    DemoRiddle(
        word_id=9,
        language=Language.RU,
        prompt="Что становится больше, если его перевернуть вверх ногами?",
        mock_answer="6",
        mock_confidence=0.65,
        mock_reasoning="Русская загадка. Число 6 при перевороте становится 9, которое больше. Ответ: цифра 6.",
        mock_alternates=("шесть", "цифра"),
    ),
    DemoRiddle(
        word_id=10,
        language=Language.PT,
        prompt="O que é, o que é: tem dentes mas não morde?",
        mock_answer="pente",
        mock_confidence=0.90,
        mock_reasoning="Adivinha portuguesa/brasileira clássica. Objeto com 'dentes' que não morde = pente.",
        mock_alternates=("engrenagem",),
    ),
    DemoRiddle(
        word_id=11,
        language=Language.HI,
        prompt="ऐसी कौन सी चीज़ है जो सूखी रहने पर भारी और गीली होने पर हल्की हो जाती है?",
        mock_answer="स्पंज",
        mock_confidence=0.42,
        mock_reasoning="Hindi riddle. Typical answer is 'sponge' but the weight relation in this variant is inverted from the usual phrasing — low confidence.",
        mock_alternates=("कपास", "रुई"),
    ),
    DemoRiddle(
        word_id=12,
        language=Language.EN,
        prompt="The more you take, the more you leave behind. What are they?",
        mock_answer="footsteps",
        mock_confidence=0.95,
        mock_reasoning="Tolkien / folk English riddle. Each step 'taken' leaves a footstep behind.",
        mock_alternates=("steps", "memories"),
    ),
    DemoRiddle(
        word_id=13,
        language=Language.ZH,
        prompt="一个人有两个爸爸，这是为什么？",
        mock_answer="继父",
        mock_confidence=0.55,
        mock_reasoning="现代中文脑筋急转弯，答案可能是：生父和继父。但也可能指同性父母，歧义较大。",
        mock_alternates=("养父", "岳父"),
    ),
    DemoRiddle(
        word_id=14,
        language=Language.EN,
        prompt="What has keys but no locks, space but no room, and you can enter but not go inside?",
        mock_answer="keyboard",
        mock_confidence=0.98,
        mock_reasoning="Modern English riddle — keyboard has 'keys', a 'space' bar, and an 'enter' key.",
        mock_alternates=("piano",),
    ),
)


# ---- Mocked `ardi-agent` CLI output ---------------------------------------

def build_context_json() -> str:
    import json

    payload = {
        "epoch": DEMO_EPOCH,
        "riddles": [
            {
                "word_id": r.word_id,
                "prompt": r.prompt,
                "language": r.language.value,
            }
            for r in DEMO_RIDDLES
        ],
    }
    return json.dumps(payload)


PREFLIGHT_STDOUT = (
    "ardi-agent preflight\n"
    "  wallet:       ok   (0xA1b2...C3d4)\n"
    "  registered:   ok   (AWP worknet: ardi)\n"
    "  coordinator:  reachable  (api.ardinals.com)\n"
    "  gas:          balance: 0.0482 ETH\n"
    "  stake:        ok   (10000 AWP allocated)\n"
    "READY\n"
)
