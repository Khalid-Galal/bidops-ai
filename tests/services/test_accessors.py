"""Accessors module: singleton caching behavior (no network/model downloads)."""


def test_get_search_service_is_cached(monkeypatch):
    import app.services.accessors as accessors

    monkeypatch.setattr(accessors, "_search_service", None)
    monkeypatch.setattr(accessors, "_embedding_service", None)

    svc1 = accessors.get_search_service()
    svc2 = accessors.get_search_service()

    assert svc1 is svc2


def test_get_citation_verifier_is_cached(monkeypatch):
    import app.services.accessors as accessors

    monkeypatch.setattr(accessors, "_citation_verifier", None)

    verifier1 = accessors.get_citation_verifier()
    verifier2 = accessors.get_citation_verifier()

    assert verifier1 is verifier2


def test_get_llm_service_requires_a_key(monkeypatch):
    import app.services.accessors as accessors

    class _FakeSettings:
        gemini_model = "gemini-2.5-pro"

        def gemini_key_list(self):
            return []

    monkeypatch.setattr(accessors, "_llm_service", None)
    monkeypatch.setattr(accessors, "get_settings", lambda: _FakeSettings())

    try:
        accessors.get_llm_service()
        raised = False
    except ValueError:
        raised = True

    assert raised
