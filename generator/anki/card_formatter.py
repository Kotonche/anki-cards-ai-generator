import os

from . import anki_operations
from ..config import Config
from ..entities import CardData, CardRawDataV1, GreekVocabularyDataV1


def get_front_html(card_data: CardRawDataV1) -> str:
    formatted_text = card_data.card_text.replace('. ', '.<br>')
    styles = """
    <style>
    .card {
        max-width: 90%; 
        margin: auto; 
        padding: 10px;
    }
    .card-image {
        max-width: 100%; 
        max-height: 450px; 
        height: auto; 
        width: auto; 
        border-radius: 10px;
    }
    
    .card-text {
        font-size: 18px;
        text-align: justify;
        line-height: 1.5;
    }
    
    .hint {
        font-family: Consolas;
        font-size: 20px;
        
        display: flex; 
        justify-content: space-between; 
        align-items: center; 
        margin-top: 50px; 
        margin-bottom: 10px;
    }
    
    .delimiter {
        margin-top: 30px;
        margin-bottom: 30px;
        height: 3px;
        border: none;
        background-color: #ccc;
        display: block;
    }
    
    .dictionary-url {
        color: gray; 
        font-weight: bold;
        text-decoration: underline; 
    }
    
    .audio-container {
        text-align: right;
    }
    .audio-text {
        color: gray;
        font-weight: bold;
    }
    .audio-button {
        margin-left: 5px;
    }
    
</style>"""
    front_content = styles + f"""
    <div class="card">
        <!-- Image -->
        <img class="card-image" src="{os.path.basename(card_data.image_path)}">
        
        <!-- Delimiter -->
        <hr class="delimiter">   
             
        <!-- Text -->
        <p class="card-text">{formatted_text}</p>
        
        <!-- Delimiter -->
        <hr class="delimiter">
        
        <!-- Dictionary Link and Audio Button -->
    """

    # Prepare the container for dictionary link and audio
    front_content += """
    <div class='hint'>
    """

    # If there's a dictionary URL, add a link to it
    if card_data.dictionary_url:
        front_content += f"<a class='dictionary-url' href='{card_data.dictionary_url}' target='_blank'>Dictionary</a>"

    # Add audio if it exists
    if card_data.audio_path:
        audio_text = f"<span class='audio-text'>Audio</span>"
        audio_button = f"<span class='audio-button'>[sound:{os.path.basename(card_data.audio_path)}]</span>"
        front_content += f"<div class='audio-container'>{audio_text}{audio_button}</div>"

    # Close the container
    front_content += "</div>"

    front_content += """
    </div>
    """
    return front_content


def get_back_html(card_data: CardRawDataV1) -> str:
    return f"""
    <div style='font-family: Verdana, sans-serif; font-size: 20px; text-align: center; margin-bottom: 20px;'>
        {card_data.word}
    </div>
    """


def format_greek_vocabulary(card_data: GreekVocabularyDataV1, deck_name: str):
    image = f'<img src="{os.path.basename(card_data.image_path)}">' if card_data.image_path else ""
    audio = f"[sound:{os.path.basename(card_data.audio_path)}]" if card_data.audio_path else ""
    context_audio = (
        f"[sound:{os.path.basename(card_data.context_audio_path)}]"
        if card_data.context_audio_path
        else ""
    )
    return {
        "deckName": deck_name,
        "modelName": Config.CARD_MODEL,
        "fields": {
            "Word": card_data.word,
            "Article": card_data.article,
            "Transcription": card_data.transcription,
            "Translation": card_data.translation,
            "Image": image,
            "Audio": audio,
            "ContextGreek": card_data.context_greek,
            "ContextTranscription": card_data.context_transcription,
            "ContextRussian": card_data.context_russian,
            "ContextCloze": card_data.context_cloze,
            "ContextClozeTranscription": card_data.context_cloze_transcription,
            "ContextAnswer": card_data.context_answer,
            "ContextAudio": context_audio,
            "Distractor1": card_data.distractor1,
            "Distractor1Transcription": card_data.distractor1_transcription,
            "Distractor2": card_data.distractor2,
            "Distractor2Transcription": card_data.distractor2_transcription,
            "Distractor3": card_data.distractor3,
            "Distractor3Transcription": card_data.distractor3_transcription,
        },
        "options": {
            "allowDuplicate": True,
            "duplicateScope": "deck",
        },
        "tags": [
            anki_operations.word_to_tag(card_data.word),
            anki_operations.source_word_to_tag(card_data.source_word),
            "greek",
            "greek-vocabulary",
            "ai-generated",
            f"level::{Config.LEVEL.lower()}",
        ],
    }


def format(card_data: CardData, deck_name: str):
    if isinstance(card_data, GreekVocabularyDataV1):
        return format_greek_vocabulary(card_data, deck_name)

    # Ensure sentences end with a new line in HTML and handle text styling
    front_content = get_front_html(card_data)
    back_content = get_back_html(card_data)

    # Construct the note dictionary with HTML content
    return {
        "deckName": deck_name,
        "modelName": Config.CARD_MODEL,
        "fields": {
            "Front": front_content,
            "Back": back_content
        },
        "options": {
            "allowDuplicate": True,
            "duplicateScope": "deck"
        },
        "tags": [anki_operations.word_to_tag(card_data.word), "ai-generated"]
    }
