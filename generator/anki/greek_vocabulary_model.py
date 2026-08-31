from generator.anki import anki_operations


MODEL_BASE_NAME = "Greek Vocabulary"
MODEL_VERSION = 1
FIELD_NAMES = [
    "Word",
    "Article",
    "Transcription",
    "Translation",
    "Image",
    "Audio",
    "ContextGreek",
    "ContextTranscription",
    "ContextRussian",
    "ContextCloze",
    "ContextClozeTranscription",
    "ContextAnswer",
    "ContextAudio",
    "Distractor1",
    "Distractor1Transcription",
    "Distractor2",
    "Distractor2Transcription",
    "Distractor3",
    "Distractor3Transcription",
]

MULTIPLE_CHOICE_NAME = "01 · Recognition Boost · Multiple Choice"
RECOGNITION_NAME = "02 · Recognition · Comprehension"
CONTEXT_NAME = "03 · Context Recall · Usage"
PRODUCTION_NAME = "04 · Active Recall · Production"
TEMPLATE_NAMES = [MULTIPLE_CHOICE_NAME, RECOGNITION_NAME, CONTEXT_NAME, PRODUCTION_NAME]


WORD_BLOCK = """
<div class="gv-transcription">{{Transcription}}</div>
<div class="gv-word"><span class="gv-article">{{Article}}</span> {{Word}}</div>
"""

CONTEXT_BLOCK = """
{{#ContextGreek}}
<section class="gv-context">
  {{#ContextTranscription}}<div class="gv-context-transcription">{{ContextTranscription}}</div>{{/ContextTranscription}}
  <div class="gv-context-greek">{{ContextGreek}}</div>
  {{#ContextRussian}}<div class="gv-context-russian">{{ContextRussian}}</div>{{/ContextRussian}}
  {{#ContextAudio}}<div class="gv-audio gv-context-audio">{{ContextAudio}}</div>{{/ContextAudio}}
</section>
{{/ContextGreek}}
"""

PRODUCTION_FRONT = """
<main class="gv-shell gv-production">
  <div class="gv-skill-badge">ACTIVE RECALL · PRODUCTION</div>
  {{#Image}}<div class="gv-image">{{Image}}</div>{{/Image}}
  <div class="gv-translation gv-primary">{{Translation}}</div>
  <div class="gv-prompt">Как по-гречески?</div>
</main>
"""

PRODUCTION_BACK = f"""
<main class="gv-shell gv-production">
  <div class="gv-skill-badge">ACTIVE RECALL · PRODUCTION</div>
  <section class="gv-answer">
    {WORD_BLOCK}
    {{{{#Audio}}}}<div class="gv-audio">{{{{Audio}}}}</div>{{{{/Audio}}}}
  </section>
  {CONTEXT_BLOCK}
</main>
"""

RECOGNITION_FRONT = f"""
<main class="gv-shell gv-recognition">
  <div class="gv-skill-badge">RECOGNITION · COMPREHENSION</div>
  <section class="gv-answer">
    {WORD_BLOCK}
    {{{{#Audio}}}}<div class="gv-audio">{{{{Audio}}}}</div>{{{{/Audio}}}}
  </section>
  <div class="gv-prompt">Что это значит?</div>
</main>
"""

RECOGNITION_BACK = f"""
<main class="gv-shell gv-recognition">
  <div class="gv-skill-badge">RECOGNITION · COMPREHENSION</div>
  <div class="gv-translation gv-primary">{{{{Translation}}}}</div>
  {{{{#Image}}}}<div class="gv-image">{{{{Image}}}}</div>{{{{/Image}}}}
  {CONTEXT_BLOCK}
</main>
"""

CONTEXT_FRONT = """
{{#ContextCloze}}
<main class="gv-shell gv-usage">
  <div class="gv-skill-badge">CONTEXT RECALL · USAGE</div>
  {{#ContextClozeTranscription}}<div class="gv-context-transcription gv-cloze-transcription">{{ContextClozeTranscription}}</div>{{/ContextClozeTranscription}}
  <div class="gv-context-greek gv-cloze">{{ContextCloze}}</div>
  <div class="gv-translation gv-context-hint">{{Translation}}</div>
  <div class="gv-prompt">Введите пропущенное слово</div>
  <div class="gv-type-answer">{{type:ContextAnswer}}</div>
</main>
{{/ContextCloze}}
"""

CONTEXT_BACK = f"""
{{{{#ContextCloze}}}}
<main class="gv-shell gv-usage">
  <section class="gv-front-on-back">{{{{FrontSide}}}}</section>
  <section class="gv-answer">
    <div class="gv-transcription">{{{{Transcription}}}}</div>
    <div class="gv-word">{{{{ContextAnswer}}}}</div>
    {{{{#Audio}}}}<div class="gv-audio">{{{{Audio}}}}</div>{{{{/Audio}}}}
  </section>
  {CONTEXT_BLOCK}
</main>
{{{{/ContextCloze}}}}
"""

MULTIPLE_CHOICE_FRONT = """
{{#Distractor1}}
{{#Distractor2}}
{{#Distractor3}}
<main class="gv-shell gv-multiple-choice" data-gv-multiple-choice>
  <div class="gv-skill-badge">RECOGNITION BOOST · MULTIPLE CHOICE</div>
  {{#Image}}<div class="gv-image">{{Image}}</div>{{/Image}}
  <div class="gv-translation gv-primary">{{Translation}}</div>
  <div class="gv-prompt">Как это по-гречески?</div>
  <div class="gv-choices" data-gv-choices>
    <button class="gv-choice" type="button" data-correct="true">
      <span class="gv-choice-transcription">{{Transcription}}</span>
      <span class="gv-choice-word"><span class="gv-article">{{Article}}</span> {{Word}}</span>
    </button>
    <button class="gv-choice" type="button" data-correct="false">
      <span class="gv-choice-transcription">{{Distractor1Transcription}}</span>
      <span class="gv-choice-word">{{Distractor1}}</span>
    </button>
    <button class="gv-choice" type="button" data-correct="false">
      <span class="gv-choice-transcription">{{Distractor2Transcription}}</span>
      <span class="gv-choice-word">{{Distractor2}}</span>
    </button>
    <button class="gv-choice" type="button" data-correct="false">
      <span class="gv-choice-transcription">{{Distractor3Transcription}}</span>
      <span class="gv-choice-word">{{Distractor3}}</span>
    </button>
  </div>
</main>
<script>
(function () {
  var root = document.querySelector("[data-gv-multiple-choice]");
  if (!root) return;
  var choices = Array.prototype.slice.call(root.querySelectorAll(".gv-choice"));
  var container = root.querySelector("[data-gv-choices]");
  for (var index = choices.length - 1; index > 0; index -= 1) {
    var randomIndex = Math.floor(Math.random() * (index + 1));
    var temporary = choices[index];
    choices[index] = choices[randomIndex];
    choices[randomIndex] = temporary;
  }
  choices.forEach(function (choice) { container.appendChild(choice); });

  var answered = false;
  var correctChoice = root.querySelector('[data-correct="true"]');
  choices.forEach(function (choice) {
    choice.addEventListener("click", function () {
      if (answered) return;
      answered = true;
      var isCorrect = choice.getAttribute("data-correct") === "true";
      choice.classList.add(isCorrect ? "is-correct" : "is-wrong");
      if (!isCorrect) correctChoice.classList.add("is-correct");
      choices.forEach(function (item) {
        item.disabled = true;
        item.setAttribute("aria-disabled", "true");
      });
    });
  });
})();
</script>
{{/Distractor3}}
{{/Distractor2}}
{{/Distractor1}}
"""

MULTIPLE_CHOICE_BACK = """
{{#Distractor1}}
{{#Distractor2}}
{{#Distractor3}}
<main class="gv-shell gv-multiple-choice">
  <div class="gv-skill-badge">RECOGNITION BOOST · MULTIPLE CHOICE</div>
  <section class="gv-answer">
    <div class="gv-transcription">{{Transcription}}</div>
    <div class="gv-word"><span class="gv-article">{{Article}}</span> {{Word}}</div>
    {{#Audio}}<div class="gv-audio">{{Audio}}</div>{{/Audio}}
  </section>
  {{#ContextGreek}}
  <section class="gv-context">
    {{#ContextTranscription}}<div class="gv-context-transcription">{{ContextTranscription}}</div>{{/ContextTranscription}}
    <div class="gv-context-greek">{{ContextGreek}}</div>
    {{#ContextRussian}}<div class="gv-context-russian">{{ContextRussian}}</div>{{/ContextRussian}}
    {{#ContextAudio}}<div class="gv-audio gv-context-audio">{{ContextAudio}}</div>{{/ContextAudio}}
  </section>
  {{/ContextGreek}}
</main>
{{/Distractor3}}
{{/Distractor2}}
{{/Distractor1}}
"""

STYLING = """
.card {
  margin: 0;
  padding: 24px 14px;
  color: #17221c;
  background: #f4f1e9;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
  font-size: 18px;
  line-height: 1.5;
  text-align: center;
}
.gv-shell {
  width: min(100%, 720px);
  margin: 0 auto;
  padding: clamp(20px, 5vw, 42px);
  border-radius: 22px;
  background: #fffdf8;
  box-sizing: border-box;
}
.gv-image { margin: 0 auto 28px; }
.gv-image img {
  display: block;
  width: auto;
  max-width: 100%;
  max-height: min(42vh, 360px);
  margin: 0 auto;
  border-radius: 16px;
  object-fit: contain;
}
.gv-primary { font-size: clamp(30px, 7vw, 52px); font-weight: 700; }
.gv-prompt { margin-top: 24px; color: #69736c; font-size: 15px; }
.gv-answer { padding: 8px 0; }
.gv-transcription {
  margin-bottom: 5px;
  color: #7c8580;
  font-size: clamp(17px, 4vw, 24px);
  font-weight: 500;
}
.gv-word {
  font-family: Georgia, "Times New Roman", serif;
  font-size: clamp(38px, 9vw, 66px);
  font-weight: 600;
  line-height: 1.15;
}
.gv-article { color: #355e4b; }
.gv-audio { margin-top: 18px; }
.replay-button svg { width: 30px; height: 30px; }
.gv-context {
  margin-top: 34px;
  padding-top: 28px;
  border-top: 1px solid #dcd9cf;
}
.gv-context-transcription { color: #7c8580; font-size: 14px; }
.gv-context-greek {
  margin-top: 7px;
  font-family: Georgia, "Times New Roman", serif;
  font-size: clamp(21px, 5vw, 30px);
  line-height: 1.4;
}
.gv-context-russian { margin-top: 12px; color: #505b54; font-size: 16px; }
.gv-context-audio { margin-top: 16px; }
.gv-recognition .gv-primary { margin-bottom: 24px; }
.gv-context-hint { margin-top: 28px; font-size: 22px; font-weight: 700; }
.gv-cloze-transcription { margin-top: 4px; font-size: 16px; }
.gv-cloze { margin-top: 10px; }
.gv-type-answer { margin-top: 14px; }
#typeans {
  width: min(100%, 420px);
  padding: 12px 14px !important;
  border: 1px solid #b8beb9 !important;
  border-radius: 10px;
  font-family: inherit !important;
  font-size: 24px !important;
  box-sizing: border-box;
}
code#typeans { display: inline-block; white-space: pre-wrap; }
.gv-front-on-back {
  margin-bottom: 30px;
  padding-bottom: 28px;
  border-bottom: 1px solid #dcd9cf;
}
.gv-front-on-back .gv-shell { width: 100%; padding: 0; box-shadow: none; }
.gv-skill-badge {
  display: inline-block;
  margin-bottom: 24px;
  padding: 6px 10px;
  border-radius: 999px;
  color: #355e4b;
  background: #e5efe9;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
}
.gv-multiple-choice .gv-image { margin-bottom: 20px; }
.gv-multiple-choice .gv-image img { max-height: min(28vh, 220px); }
.gv-multiple-choice .gv-primary { font-size: clamp(27px, 6vw, 44px); }
.gv-choices { display: grid; gap: 10px; margin-top: 24px; }
.gv-choice {
  position: relative;
  width: 100%;
  box-sizing: border-box;
  min-height: 72px;
  padding: 10px 44px;
  border: 1px solid #cfd6d0;
  border-radius: 14px;
  color: #17221c;
  background: #f8faf7;
  font: inherit;
  text-align: center;
  cursor: pointer;
}
.gv-choice:disabled { opacity: 1; cursor: default; }
.gv-choice-transcription { display: block; color: #7c8580; font-size: 14px; }
.gv-choice-word {
  display: block;
  margin-top: 2px;
  font-family: Georgia, "Times New Roman", serif;
  font-size: clamp(21px, 5vw, 28px);
  font-weight: 600;
  line-height: 1.2;
}
.gv-choice .gv-article { color: inherit; }
.gv-choice.is-correct { border-color: #4f8b6d; background: #e6f3eb; }
.gv-choice.is-wrong { border-color: #b85c55; background: #f9e8e6; }
.gv-choice.is-correct::before,
.gv-choice.is-wrong::before {
  position: absolute;
  top: 50%;
  left: 16px;
  font-size: 22px;
  font-weight: 800;
  transform: translateY(-50%);
}
.gv-choice.is-correct::before { content: "✓"; color: #397558; }
.gv-choice.is-wrong::before { content: "✕"; color: #a44740; }
.card.nightMode, .card.night_mode,
.nightMode .card, .night_mode .card { color: #edf1ed; background: #17221c; }
.nightMode .gv-shell, .night_mode .gv-shell { background: #223129; }
.nightMode .gv-transcription, .night_mode .gv-transcription,
.nightMode .gv-context-transcription, .night_mode .gv-context-transcription,
.nightMode .gv-prompt, .night_mode .gv-prompt { color: #aeb9b1; }
.nightMode .gv-context-russian, .night_mode .gv-context-russian { color: #ced6d0; }
.nightMode .gv-context, .night_mode .gv-context,
.nightMode .gv-front-on-back, .night_mode .gv-front-on-back { border-color: #45544b; }
.nightMode .gv-skill-badge, .night_mode .gv-skill-badge { color: #b9dcc8; background: #314a3b; }
.nightMode .gv-choice, .night_mode .gv-choice { color: #edf1ed; border-color: #506158; background: #293a31; }
.nightMode .gv-choice.is-correct, .night_mode .gv-choice.is-correct { border-color: #71aa88; background: #294737; }
.nightMode .gv-choice.is-wrong, .night_mode .gv-choice.is-wrong { border-color: #ca7770; background: #4a302e; }
@media (max-width: 520px) {
  .card { padding: 0; }
  .gv-shell { min-height: 100vh; border-radius: 0; }
  .gv-image img { max-height: 36vh; }
}
"""

CARD_TEMPLATES = [
    {"Name": MULTIPLE_CHOICE_NAME, "Front": MULTIPLE_CHOICE_FRONT, "Back": MULTIPLE_CHOICE_BACK},
    {"Name": RECOGNITION_NAME, "Front": RECOGNITION_FRONT, "Back": RECOGNITION_BACK},
    {"Name": CONTEXT_NAME, "Front": CONTEXT_FRONT, "Back": CONTEXT_BACK},
    {"Name": PRODUCTION_NAME, "Front": PRODUCTION_FRONT, "Back": PRODUCTION_BACK},
]


def _result(response: dict, action: str):
    if response.get("error"):
        raise RuntimeError(f"AnkiConnect {action}: {response['error']}")
    return response.get("result")


def _model_name(version: int) -> str:
    return f"{MODEL_BASE_NAME} v{version}"


def _is_compatible(model_name: str) -> bool:
    fields = _result(
        anki_operations.invoke("modelFieldNames", {"modelName": model_name}),
        "modelFieldNames",
    )
    templates = _result(
        anki_operations.invoke("modelTemplates", {"modelName": model_name}),
        "modelTemplates",
    )
    multiple_choice_back = templates.get(MULTIPLE_CHOICE_NAME, {}).get("Back", "")
    return (
        fields == FIELD_NAMES
        and list(templates) == TEMPLATE_NAMES
        and "{{ContextAudio}}" in multiple_choice_back
    )


def ensure_model() -> str:
    names = _result(anki_operations.invoke("modelNames"), "modelNames") or []
    version = MODEL_VERSION
    while True:
        name = _model_name(version)
        if name not in names:
            response = anki_operations.invoke(
                "createModel",
                {
                    "modelName": name,
                    "inOrderFields": FIELD_NAMES,
                    "css": STYLING,
                    "isCloze": False,
                    "cardTemplates": CARD_TEMPLATES,
                },
            )
            _result(response, "createModel")
            return name
        if _is_compatible(name):
            return name
        version += 1
