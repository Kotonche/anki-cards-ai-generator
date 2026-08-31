import logging

import requests

from generator.config import Config


SIBLING_SPACING_PRESET_PREFIX = "Anki Generator · spaced siblings"


def _result_or_raise(response: dict, action: str):
    if response.get("error"):
        raise RuntimeError(f"AnkiConnect {action}: {response['error']}")
    return response.get("result")


def check_deck_exists(deck_name: str) -> bool:
    # Check existing decks
    result = invoke('deckNames')
    if deck_name not in result['result']:
        logging.info(f"Anki deck '{deck_name}' does not exist")
        return False
    else:
        logging.debug(f"Anki deck '{deck_name}' exists")
        return True


def create_deck(deck_name):
    result = invoke('createDeck', {'deck': deck_name})
    if result.get('error') is None:
        logging.info(f"Deck '{deck_name}' created successfully.")
        return True
    else:
        error_msg = result.get('error')
        logging.error(f"Failed to create deck '{deck_name}': {error_msg}")
        raise Exception(f"An error occurred: {error_msg}")


def ensure_new_sibling_spacing(deck_name: str) -> bool:
    """Use template order and show at most one new sibling from a note per day."""
    config = _result_or_raise(
        invoke("getDeckConfig", {"deck": deck_name}),
        "getDeckConfig",
    )
    if not isinstance(config, dict) or not isinstance(config.get("new"), dict):
        raise RuntimeError("AnkiConnect getDeckConfig: unexpected deck configuration")

    desired = config["new"].get("bury") is True and config.get("newSortOrder", 0) == 0
    if desired:
        return False

    if not str(config.get("name", "")).startswith(SIBLING_SPACING_PRESET_PREFIX):
        source_id = config.get("id")
        if source_id is None:
            raise RuntimeError("AnkiConnect getDeckConfig: configuration ID is missing")
        deck_label = deck_name.replace("::", " · ")
        clone_id = _result_or_raise(
            invoke(
                "cloneDeckConfigId",
                {
                    "name": f"{SIBLING_SPACING_PRESET_PREFIX} · {deck_label}",
                    "cloneFrom": source_id,
                },
            ),
            "cloneDeckConfigId",
        )
        if clone_id is False:
            raise RuntimeError("AnkiConnect cloneDeckConfigId: failed to clone deck preset")
        assigned = _result_or_raise(
            invoke("setDeckConfigId", {"decks": [deck_name], "configId": clone_id}),
            "setDeckConfigId",
        )
        if assigned is not True:
            raise RuntimeError("AnkiConnect setDeckConfigId: failed to assign deck preset")
        config = _result_or_raise(
            invoke("getDeckConfig", {"deck": deck_name}),
            "getDeckConfig",
        )
        if not isinstance(config, dict) or not isinstance(config.get("new"), dict):
            raise RuntimeError("AnkiConnect getDeckConfig: unexpected cloned configuration")

    config["new"]["bury"] = True
    config["newSortOrder"] = 0
    saved = _result_or_raise(
        invoke("saveDeckConfig", {"config": config}),
        "saveDeckConfig",
    )
    if saved is not True:
        raise RuntimeError("AnkiConnect saveDeckConfig: failed to save deck preset")
    logging.info("New sibling spacing enabled for deck [%s]", deck_name)
    return True


def check_card_exists(deck_name, word):
    tag = word_to_tag(word)
    return check_card_exists_with_tag(deck_name, tag)


def check_card_exists_with_tag(deck_name, tag):
    existing_cards = find_all_cards_with_tag(deck_name, tag)
    if len(existing_cards) >= 1:
        logging.info(f"Card with tag [{tag}] exists in deck [{deck_name}]")
        return True
    else:
        logging.debug(f"Card with tag [{tag}] does not exist in deck [{deck_name}]")
        return False


def delete_card_from_deck(deck_name: str, word: str) -> bool:
    tag = word_to_tag(word)
    return delete_cards_from_deck_with_tag(deck_name, tag)


def delete_cards_from_deck_with_tag(deck_name: str, tag: str) -> bool:
    logging.info(f"Deleting cards from deck [{deck_name}] using tag [{tag}]")
    card_ids = find_all_cards_with_tag(deck_name, tag)
    if not card_ids:
        logging.warning("No cards found with the specified term in the given deck.")
        return True
    delete_result = delete_cards_by_id(card_ids)
    if delete_result.get('error') is None:
        # sometimes cards are not deleted -> retry
        remaining_cards = find_all_cards_with_tag(deck_name, tag)
        if len(remaining_cards) == 0:
            logging.info(f"Successfully deleted cards with tag [{tag}]")
            return True
        else:
            logging.error(f"Deletion returned no error, but some cards with tag [{tag}] are still in the deck - {remaining_cards}."
                          f" This happens, if a card is in review process. Restart Anki and try again.")
            return False

    else:
        logging.error(f"Failed to delete cards: {delete_result.get('error')}")
        return False


def find_all_cards_with_tag(deck_name, tag):
    card_ids = find_cards(f'"deck:{deck_name}" tag:"{tag}"')
    logging.info(f"Found [{len(card_ids)}] cards with tag [{tag}] in deck [{deck_name}]")
    logging.debug(f"Found cards with tag {tag} in deck [{deck_name}]: [{card_ids}]")
    return card_ids


def find_cards(query):
    return invoke('findCards', {'query': query})['result']


def delete_cards_by_id(card_ids):
    cards_info = get_card_info(card_ids)
    if cards_info.get('error'):
        return cards_info
    note_ids = sorted({card['note'] for card in cards_info.get('result', [])})
    result = invoke('deleteNotes', {'notes': note_ids})
    logging.info(f"Deletion performed for note ids {note_ids} resolved from card ids {card_ids}")
    return result


def get_all_card_ids_from_deck(deck_name: str):
    return invoke('findCards', {'query': f'deck:"{deck_name}"'})


def get_card_info(card_ids):
    return invoke('cardsInfo', {'cards': card_ids})


def get_all_words_from_deck(deck_name) -> list[str]:
    card_ids = get_all_card_ids_from_deck(deck_name)['result']
    if not card_ids:
        logging.info(f"No cards found in deck '{deck_name}'.")
        return []

    cards_info = get_card_info(card_ids)['result']
    words = []
    for card in cards_info:
        field = card['fields'].get('Front') or card['fields'].get('Word')
        if field:
            words.append(field['value'])
    return words


def invoke(action, params=None):
    if params is None:
        params = {}
    request = {'action': action, 'version': 6, 'params': params}
    response = requests.post(Config.ANKI_CONNECT_URL, json=request, timeout=15)
    response.raise_for_status()
    return response.json()


def word_to_tag(word: str) -> str:
    formatted_word = word.replace(' ', '_').lower()  # Format word for consistent tagging
    return formatted_word


def source_word_to_tag(word: str) -> str:
    return f"source::{word_to_tag(word)}"
