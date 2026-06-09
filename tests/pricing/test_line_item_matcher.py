from app.services.pricing.line_item_matcher import best_match, match_score, normalize_desc


def test_normalize_strips_punctuation_and_case():
    assert normalize_desc("Supply & Install (Chiller)!") == "supply install chiller"


def test_identical_descriptions_score_1():
    assert match_score("Concrete grade C30", "concrete grade c30") == 1.0


def test_reordered_words_score_high():
    s = match_score("Split AC unit supply and installation",
                    "Supply and install split AC unit")
    assert s >= 0.6


def test_unrelated_descriptions_score_low():
    assert match_score("Concrete C30 foundation", "Split AC indoor unit") < 0.3


def test_empty_scores_zero():
    assert match_score("", "anything") == 0.0


def test_best_match_picks_highest_above_threshold():
    candidates = [
        {"description": "VRF outdoor condensing unit", "rate": 8000},
        {"description": "Split AC unit supply and installation", "rate": 1200},
    ]
    item, score = best_match("Split AC unit (supply & install)", candidates, threshold=0.45)
    assert item is not None
    assert item["rate"] == 1200
    assert score >= 0.45


def test_best_match_returns_none_below_threshold():
    candidates = [{"description": "Asphalt road base", "rate": 50}]
    item, score = best_match("Curtain wall glazing", candidates, threshold=0.45)
    assert item is None


def test_best_match_uses_semantic_scorer_when_higher():
    candidates = [{"description": "totally different text", "rate": 99}]
    # fuzzy score is ~0; injected semantic scorer forces a match
    item, score = best_match(
        "anything", candidates, threshold=0.45,
        semantic_scorer=lambda a, b: 0.9,
    )
    assert item is not None and score == 0.9


def test_best_match_tie_returns_first():
    # two candidates with identical descriptions (equal score) -> the
    # first-listed candidate wins (stable, strict >, not >=).
    candidates = [
        {"description": "Concrete grade C30", "rate": 100},
        {"description": "Concrete grade C30", "rate": 200},
    ]
    item, score = best_match("Concrete grade C30", candidates, threshold=0.45)
    assert item["rate"] == 100
    assert score == 1.0
