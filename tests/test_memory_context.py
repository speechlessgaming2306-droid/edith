from project_manager import ProjectManager


class FakeMem0Store:
    def __init__(self):
        self.is_enabled = True
        self.saved_notes = []
        self.chat_messages = []

    def add_chat_message(self, sender, text):
        self.chat_messages.append((sender, text))
        return True

    def add_memory_note(self, text):
        self.saved_notes.append(text)
        return True

    def search(self, query, limit=8):
        if "ice cream" not in query.lower() and "icecream" not in query.lower():
            return []
        return [{
            "sender": "Memory",
            "text": "Sir's favorite ice cream is pistachio.",
            "kind": "explicit_note",
            "timestamp": 9999999999,
        }]

    def get_recent_memories(self, limit=40):
        return [{
            "sender": "Memory",
            "text": "Sir's favorite ice cream is pistachio.",
            "kind": "explicit_note",
            "timestamp": 9999999999,
        }]


def test_recall_memory_matches_fav_icecream_variants(tmp_path):
    manager = ProjectManager(str(tmp_path))
    manager.register_conversation_start()
    manager.save_memory_note("Sir's favorite ice cream is cookies and cream.")

    results = manager.recall_memory("what's my fav icecream", limit=5)

    assert results
    assert "cookies and cream" in results[0]["text"].lower()


def test_build_relevant_memory_context_prioritizes_explicit_note(tmp_path):
    manager = ProjectManager(str(tmp_path))
    manager.register_conversation_start()
    manager.log_chat("User", "I like vanilla sometimes.")
    manager.save_memory_note("Sir's favorite ice cream is mint chocolate chip.")
    manager.log_chat("User", "Remember that I prefer dry sarcasm over cheerful jokes.")

    context = manager.build_relevant_memory_context("Do you remember my favorite ice cream?", limit=3)

    assert context
    assert "mint chocolate chip" in context[-1]["text"].lower() or "mint chocolate chip" in context[0]["text"].lower()
    assert any(entry["kind"] == "explicit_note" for entry in context)


def test_user_favorite_statement_is_promoted_to_explicit_memory(tmp_path):
    manager = ProjectManager(str(tmp_path))
    manager.register_conversation_start()

    manager.log_chat("User", "My favourite ice cream is cookies and cream.")

    results = manager.recall_memory("what's my favorite ice cream", limit=5)

    assert results
    assert any(entry["kind"] == "explicit_note" for entry in results)
    assert "cookies and cream" in results[0]["text"].lower()


def test_startup_silent_memory_includes_promoted_favorite_fact(tmp_path):
    manager = ProjectManager(str(tmp_path))
    manager.register_conversation_start()

    manager.log_chat("User", "My favorite song is Nights by Frank Ocean.")

    anchors = manager.build_silent_memory_context(limit=10, max_chars=1200)

    assert anchors
    assert any("nights by frank ocean" in entry["text"].lower() for entry in anchors)


def test_mem0_results_are_merged_into_relevant_context(tmp_path, monkeypatch):
    fake_store = FakeMem0Store()
    monkeypatch.setattr("project_manager.Mem0MemoryStore.from_workspace", lambda workspace_root: fake_store)

    manager = ProjectManager(str(tmp_path))
    manager.register_conversation_start()

    context = manager.build_relevant_memory_context("Do you remember my favorite ice cream?", limit=3)

    assert context
    assert any("pistachio" in entry["text"].lower() for entry in context)


def test_mem0_receives_explicit_memory_notes(tmp_path, monkeypatch):
    fake_store = FakeMem0Store()
    monkeypatch.setattr("project_manager.Mem0MemoryStore.from_workspace", lambda workspace_root: fake_store)

    manager = ProjectManager(str(tmp_path))
    manager.register_conversation_start()
    manager.save_memory_note("Sir's favorite movie is Interstellar.")

    assert fake_store.saved_notes == ["Sir's favorite movie is Interstellar."]
