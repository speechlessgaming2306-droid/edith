import os
import json
import shutil
import time
import re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from mem0_memory import Mem0MemoryStore

class ProjectManager:
    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
        self.projects_dir = self.workspace_root / "projects"
        legacy_desktop_projects_dir = Path.home() / "Desktop" / "Harvey Projects"
        preferred_desktop_projects_dir = Path.home() / "Desktop" / "Edith Projects"
        self.desktop_projects_dir = legacy_desktop_projects_dir if legacy_desktop_projects_dir.exists() else preferred_desktop_projects_dir
        self.memory_dir = self.workspace_root / "long_term_memory"
        self.conversation_logs_dir = self.memory_dir / "conversations"
        self.global_memory_file = self.memory_dir / "edith_memory.jsonl"
        self.behavior_profile_file = self.memory_dir / "behavior_profile.json"
        self.session_state_file = self.memory_dir / "session_state.json"
        self.tasks_file = self.memory_dir / "tasks.json"
        self.reminders_file = self.memory_dir / "reminders.json"
        self.calendar_file = self.memory_dir / "calendar_events.json"
        self.communications_file = self.memory_dir / "communications.json"
        self.current_project = "temp"
        self.current_conversation_number = 0
        self.current_conversation_file = None
        self.mem0_store = None
        
        # Ensure projects root exists
        if not self.projects_dir.exists():
            self.projects_dir.mkdir(parents=True)

        if not self.memory_dir.exists():
            self.memory_dir.mkdir(parents=True)
        if not self.conversation_logs_dir.exists():
            self.conversation_logs_dir.mkdir(parents=True)
        if not self.desktop_projects_dir.exists():
            self.desktop_projects_dir.mkdir(parents=True, exist_ok=True)

        self.reload_memory_store()
            
        # Clear temp project on startup if it exists
        temp_path = self.projects_dir / "temp"
        if temp_path.exists():
            print("[ProjectManager] Clearing temp project...")
            shutil.rmtree(temp_path)
            
        # Ensure temp project receives fresh creation
        self.create_project("temp")

    def reload_memory_store(self):
        self.mem0_store = Mem0MemoryStore.from_workspace(self.workspace_root)

    def _load_json_state(self, path: Path, default):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return json.loads(json.dumps(default))

    def _save_json_state(self, path: Path, payload):
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def create_project(self, name: str):
        """Creates a new project directory with subfolders."""
        safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '-', '_')]).strip()
        if not safe_name:
            return False, "Project name was empty."

        project_path = self._project_path_for_name(safe_name)
        
        if not project_path.exists():
            project_path.mkdir(parents=True)
            (project_path / "cad").mkdir(exist_ok=True)
            (project_path / "browser").mkdir(exist_ok=True)
            (project_path / "documents").mkdir(exist_ok=True)
            print(f"[ProjectManager] Created project: {safe_name}")
            if safe_name == "temp":
                return True, f"Project '{safe_name}' created."
            return True, f"Project '{safe_name}' created on your Desktop at '{project_path}'."
        return False, f"Project '{safe_name}' already exists."

    def switch_project(self, name: str):
        """Switches the active project context."""
        safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '-', '_')]).strip()
        project_path = self._project_path_for_name(safe_name)
        
        if project_path.exists():
            self.current_project = safe_name
            print(f"[ProjectManager] Switched to project: {safe_name}")
            return True, f"Switched to project '{safe_name}'."
        return False, f"Project '{safe_name}' does not exist."

    def list_projects(self):
        """Returns a list of available projects."""
        names = set()
        if self.projects_dir.exists():
            names.update(d.name for d in self.projects_dir.iterdir() if d.is_dir())
        if self.desktop_projects_dir.exists():
            names.update(d.name for d in self.desktop_projects_dir.iterdir() if d.is_dir())
        return sorted(names)

    def get_current_project_path(self):
        return self._project_path_for_name(self.current_project)

    def _project_path_for_name(self, name: str) -> Path:
        safe_name = "".join([c for c in name if c.isalnum() or c in (' ', '-', '_')]).strip()
        if safe_name == "temp":
            return self.projects_dir / "temp"
        return self.desktop_projects_dir / safe_name

    def register_conversation_start(self):
        state = {"conversation_count": 0}
        if self.session_state_file.exists():
            try:
                state = json.loads(self.session_state_file.read_text(encoding="utf-8"))
            except Exception:
                state = {"conversation_count": 0}

        count = int(state.get("conversation_count", 0)) + 1
        state["conversation_count"] = count
        state["last_started_at"] = time.time()
        self.session_state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
        self.current_conversation_number = count
        self.current_conversation_file = self.conversation_logs_dir / f"conversation_{count:03d}.jsonl"
        return count

    def get_conversation_log_path(self, number: int | None = None) -> Path | None:
        conversation_number = number or self.current_conversation_number
        if not conversation_number:
            return None
        return self.conversation_logs_dir / f"conversation_{conversation_number:03d}.jsonl"

    def open_conversation_log(self, number: int | None = None):
        path = self.get_conversation_log_path(number)
        if not path or not path.exists():
            conversation_number = number or self.current_conversation_number
            return False, f"Conversation {conversation_number} does not have a saved log yet.", None
        return True, f"Opened conversation {number or self.current_conversation_number} log.", path

    def suggest_project_name(self, *seeds: str):
        stop_words = {
            "a", "an", "the", "file", "files", "new", "project", "folder", "document",
            "write", "make", "create", "this", "that", "my", "for", "with", "and", "to",
        }
        for seed in seeds:
            text = re.sub(r"\s+", " ", (seed or "").strip())
            if not text:
                continue
            text = Path(text).stem.replace("_", " ").replace("-", " ")
            words = re.findall(r"[A-Za-z][A-Za-z']+", text)
            words = [word for word in words if word.lower() not in stop_words]
            if words:
                candidate = " ".join(words[:4]).strip()
                if len(candidate) >= 4:
                    return candidate.title()

        stamp = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%b %d")
        return f"Working Draft {stamp}"

    def log_chat(self, sender: str, text: str):
        """Appends a chat message to the current project's history and the long-term memory log."""
        log_file = self.get_current_project_path() / "chat_history.jsonl"
        timestamp = time.time()
        entry = {
            "timestamp": timestamp,
            "sender": sender,
            "text": text,
            "conversation": self.current_conversation_number,
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        if self.current_conversation_file:
            with open(self.current_conversation_file, "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "timestamp": timestamp,
                    "sender": sender,
                    "text": text,
                    "project": self.current_project,
                    "conversation": self.current_conversation_number,
                }) + "\n")

        memory_entry = {
            "timestamp": timestamp,
            "project": self.current_project,
            "sender": sender,
            "text": text,
            "kind": "chat",
            "conversation": self.current_conversation_number,
        }
        with open(self.global_memory_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(memory_entry) + "\n")

        if self.mem0_store and self.mem0_store.is_enabled:
            self.mem0_store.add_chat_message(sender, text)

        if sender == "User":
            self._update_behavior_profile(text, timestamp)
            for memory_note in self._extract_user_memory_notes(text):
                self.save_memory_note(memory_note, timestamp=timestamp)

    def _extract_user_memory_notes(self, text: str):
        source_text = re.sub(r"\s+", " ", (text or "").strip())
        if not source_text:
            return []

        patterns = [
            (
                re.compile(
                    r"\bmy\s+favou?rite\s+([a-z0-9][a-z0-9\s'&-]{1,40}?)\s+is\s+(.+)$",
                    re.IGNORECASE,
                ),
                lambda match: f"Sir's favorite {match.group(1).strip()} is {match.group(2).strip().rstrip('.!?')}.",
            ),
            (
                re.compile(
                    r"\bi\s+prefer\s+(.+?)\s+for\s+my\s+favou?rite\s+([a-z0-9][a-z0-9\s'&-]{1,40})\b",
                    re.IGNORECASE,
                ),
                lambda match: f"Sir's favorite {match.group(2).strip()} is {match.group(1).strip().rstrip('.!?')}.",
            ),
            (
                re.compile(
                    r"\bremember\s+that\s+my\s+favou?rite\s+([a-z0-9][a-z0-9\s'&-]{1,40}?)\s+is\s+(.+)$",
                    re.IGNORECASE,
                ),
                lambda match: f"Sir's favorite {match.group(1).strip()} is {match.group(2).strip().rstrip('.!?')}.",
            ),
        ]

        notes = []
        for pattern, renderer in patterns:
            match = pattern.search(source_text)
            if match:
                rendered = renderer(match)
                rendered = re.sub(r"\s+", " ", rendered).strip()
                if rendered:
                    notes.append(rendered)

        deduped = []
        seen = set()
        for note in notes:
            normalized = self._normalize_memory_search_text(note)
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(note)
        return deduped

    def save_memory_note(self, text: str, timestamp: float | None = None):
        """Stores an explicit memory note for cross-conversation recall."""
        note_text = re.sub(r"\s+", " ", (text or "").strip())
        if not note_text:
            return False

        normalized_note = self._normalize_memory_search_text(note_text)
        for entry in reversed(self._read_global_memory_entries()):
            if entry.get("kind") != "explicit_note":
                continue
            existing_text = re.sub(r"\s+", " ", str(entry.get("text") or "").strip())
            if self._normalize_memory_search_text(existing_text) == normalized_note:
                return False

        timestamp = timestamp or time.time()
        entry = {
            "timestamp": timestamp,
            "project": self.current_project,
            "sender": "Memory",
            "text": note_text,
            "kind": "explicit_note"
        }
        with open(self.global_memory_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        if self.mem0_store and self.mem0_store.is_enabled:
            self.mem0_store.add_memory_note(note_text)
        return True

    def _new_record_id(self, prefix: str):
        stamp = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y%m%d%H%M%S")
        return f"{prefix}_{stamp}_{int(time.time() * 1000) % 1000:03d}"

    def get_recent_global_memory(self, limit: int = 40):
        """Returns explicit memory notes for quiet cross-conversation recall."""
        history = []
        if self.global_memory_file.exists():
            try:
                with open(self.global_memory_file, "r", encoding="utf-8") as f:
                    lines = f.readlines()

                for line in lines[-limit:]:
                    try:
                        entry = json.loads(line)
                        if entry.get("kind") == "explicit_note":
                            history.append(entry)
                    except json.JSONDecodeError:
                        continue
            except Exception as e:
                print(f"[ProjectManager] [ERR] Failed to read global memory: {e}")

        if self.mem0_store and self.mem0_store.is_enabled:
            history.extend(self.mem0_store.get_recent_memories(limit=limit))

        deduped = []
        seen = set()
        for entry in sorted(history, key=lambda item: float(item.get("timestamp", 0) or 0), reverse=True):
            text = re.sub(r"\s+", " ", str(entry.get("text") or "").strip())
            normalized = self._normalize_memory_search_text(text)
            if not text or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append({
                "timestamp": float(entry.get("timestamp", 0) or 0),
                "project": entry.get("project"),
                "sender": entry.get("sender", "Memory"),
                "text": text,
                "kind": entry.get("kind", "explicit_note"),
            })
            if len(deduped) >= limit:
                break
        return deduped

    def _read_global_memory_entries(self):
        if not self.global_memory_file.exists():
            return []

        entries = []
        try:
            with open(self.global_memory_file, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"[ProjectManager] [ERR] Failed to read global memory entries: {e}")
        return entries

    def _normalize_memory_search_text(self, text: str) -> str:
        normalized = (text or "").lower()
        normalized = normalized.replace("favourite", "favorite")
        normalized = re.sub(r"\bice[\s-]*cream\b", "icecream", normalized)
        normalized = re.sub(r"\bfav\b", "favorite", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _memory_query_terms(self, query: str):
        stop_words = {
            "a", "an", "and", "are", "be", "did", "do", "does", "for", "from",
            "have", "i", "is", "it", "know", "me", "my", "of", "remember",
            "said", "tell", "that", "the", "to", "was", "what", "whats", "when",
            "where", "which", "who", "why", "you",
        }
        query_terms = []
        for term in re.split(r"[^a-z0-9]+", self._normalize_memory_search_text(query)):
            if len(term) < 3 or term in stop_words:
                continue
            query_terms.append(term)
        return query_terms

    def build_relevant_memory_context(self, query: str, limit: int = 4, max_chars: int = 900):
        query = (query or "").strip()
        if not query:
            return []

        normalized_query = self._normalize_memory_search_text(query)
        query_terms = self._memory_query_terms(query)
        if not normalized_query and not query_terms:
            return []

        scored = []
        now = time.time()
        entries = list(self._read_global_memory_entries())
        if self.mem0_store and self.mem0_store.is_enabled:
            entries.extend(self.mem0_store.search(query, limit=max(limit * 3, 8)))

        for entry in entries:
            text = (entry.get("text") or "").strip()
            if not text:
                continue

            normalized_text = self._normalize_memory_search_text(text)
            score = 0
            if normalized_query and normalized_query in normalized_text:
                score += 18

            term_hits = sum(1 for term in query_terms if term in normalized_text)
            score += term_hits * 4

            kind = entry.get("kind")
            sender = entry.get("sender")
            if kind == "explicit_note":
                score += 6
            if sender == "User":
                score += 2
            if "favorite" in normalized_text and any(term in normalized_query for term in ("favorite", "icecream")):
                score += 5

            age_seconds = max(0.0, now - float(entry.get("timestamp", 0) or 0))
            if age_seconds <= 30 * 24 * 60 * 60:
                score += 2

            if score > 0:
                scored.append((score, entry.get("timestamp", 0), entry))

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)

        selected = []
        total_chars = 0
        seen = set()
        for score, _, entry in scored:
            text = re.sub(r"\s+", " ", (entry.get("text") or "").strip())
            normalized_text = self._normalize_memory_search_text(text)
            if not text or normalized_text in seen:
                continue
            if score < 6:
                continue

            rendered = f"[{entry.get('sender', 'Unknown')}] {text}"
            if total_chars + len(rendered) > max_chars:
                break
            selected.append({
                "sender": entry.get("sender", "Unknown"),
                "text": text,
                "kind": entry.get("kind", "chat"),
                "timestamp": entry.get("timestamp", 0),
                "score": score,
            })
            seen.add(normalized_text)
            total_chars += len(rendered) + 1
            if len(selected) >= limit:
                break

        selected.sort(key=lambda item: float(item.get("timestamp", 0) or 0))
        return selected

    def build_silent_memory_context(self, limit: int = 36, max_chars: int = 2600):
        """
        Builds a quiet long-term memory context from the full memory log.
        It prefers explicit notes plus substantial user messages and avoids noisy filler.
        """
        entries = self.get_recent_global_memory(limit=max(limit * 3, 36))
        if not entries:
            return []

        selected = []
        seen_texts = set()
        conversation_counts = {}
        explicit_note_count = 0
        now = time.time()
        for entry in reversed(entries):
            text = (entry.get("text") or "").strip()
            if not text:
                continue

            normalized = re.sub(r"\s+", " ", text).strip().lower()
            if not normalized or normalized in seen_texts:
                continue

            kind = entry.get("kind", "chat")
            sender = entry.get("sender", "")
            if kind == "explicit_note":
                priority = 3
                if explicit_note_count >= 6:
                    continue
                text = re.sub(r"\s+", " ", text).strip()
                if len(text) > 420:
                    text = text[:417].rstrip() + "..."
            else:
                continue

            entry_timestamp = float(entry.get("timestamp", 0) or 0)
            age_seconds = max(0.0, now - entry_timestamp)
            conversation_id = entry.get("conversation") or "unknown"
            conversation_counts.setdefault(conversation_id, 0)

            if kind != "explicit_note" and age_seconds > 10 * 24 * 60 * 60:
                continue
            if conversation_counts[conversation_id] >= 3:
                continue

            if priority >= 2:
                selected.append({
                    "timestamp": entry.get("timestamp"),
                    "sender": sender,
                    "project": entry.get("project"),
                    "text": text,
                    "kind": kind,
                })
                seen_texts.add(normalized)
                conversation_counts[conversation_id] += 1
                if kind == "explicit_note":
                    explicit_note_count += 1

            if len(selected) >= limit:
                break

        selected.reverse()

        trimmed = []
        total_chars = 0
        for entry in selected:
            line = f"[{entry.get('sender', 'Unknown')}] {entry.get('text', '')}"
            if total_chars + len(line) > max_chars:
                break
            trimmed.append(entry)
            total_chars += len(line) + 1
        return trimmed

    def _default_behavior_profile(self):
        return {
            "updated_at": 0,
            "totals": {
                "messages": 0,
                "multi_step": 0,
                "directive": 0,
                "reflective": 0,
                "casual": 0,
                "profane": 0,
                "playful": 0,
            },
            "time_buckets": {
                "morning": 0,
                "afternoon": 0,
                "evening": 0,
                "night": 0,
            },
            "topics": {
                "study": 0,
                "browser": 0,
                "files": 0,
                "music": 0,
                "fitness": 0,
                "emotion": 0,
                "image": 0,
            },
        }

    def _bucket_for_timestamp(self, timestamp: float):
        hour = datetime.fromtimestamp(timestamp, ZoneInfo("Asia/Kolkata")).hour
        if 5 <= hour < 12:
            return "morning"
        if 12 <= hour < 17:
            return "afternoon"
        if 17 <= hour < 22:
            return "evening"
        return "night"

    def _classify_user_text(self, text: str):
        normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
        if not normalized:
            return None

        profanity_tokens = {"fuck", "fucking", "shit", "damn", "hell", "ass"}
        casual_tokens = {"bro", "lol", "lmao", "ykwim", "gonna", "wanna", "pls", "bruh"}
        playful_tokens = {"lol", "lmao", "haha", "bro", "ykwim"}
        directive_starts = (
            "open ", "close ", "make ", "fix ", "copy ", "move ", "delete ",
            "switch ", "tell ", "generate ", "create ", "show ", "go ", "play ",
            "pause ", "skip ", "search ", "plan ", "give ", "read ", "write "
        )
        reflective_tokens = {"why", "feel", "think", "remember", "anxious", "spiral", "slacking", "exam", "habit"}

        topics = {
            "study": ("exam", "study", "board", "school", "class", "english"),
            "browser": ("chrome", "youtube", "whatsapp", "browser", "tab", "extension", "kapture"),
            "files": ("file", "folder", "pdf", "html", "project", "copy", "move", "delete"),
            "music": ("spotify", "song", "music", "playlist", "play"),
            "fitness": ("gym", "run", "fitness", "workout", "nicotine", "smoking"),
            "emotion": ("ex", "breakup", "fear", "lust", "focused", "anxious", "sad"),
            "image": ("image", "art", "wallpaper", "poster", "generate an image"),
        }

        features = {
            "multi_step": int((" and " in normalized) or ("," in normalized) or (" then " in normalized)),
            "directive": int(normalized.startswith(directive_starts)),
            "reflective": int(("?" in normalized) or any(token in normalized for token in reflective_tokens)),
            "casual": int(any(token in normalized for token in casual_tokens)),
            "profane": int(any(token in normalized for token in profanity_tokens)),
            "playful": int(any(token in normalized for token in playful_tokens)),
            "topics": {name: int(any(token in normalized for token in tokens)) for name, tokens in topics.items()},
        }
        return features

    def _load_behavior_profile(self):
        if self.behavior_profile_file.exists():
            try:
                return json.loads(self.behavior_profile_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        profile = self._rebuild_behavior_profile_from_history()
        self._save_behavior_profile(profile)
        return profile

    def _save_behavior_profile(self, profile):
        self.behavior_profile_file.write_text(json.dumps(profile, indent=2), encoding="utf-8")

    def _rebuild_behavior_profile_from_history(self):
        profile = self._default_behavior_profile()
        for entry in self._read_global_memory_entries():
            if entry.get("sender") != "User" or entry.get("kind") != "chat":
                continue
            self._apply_behavior_features(profile, entry.get("text", ""), float(entry.get("timestamp", 0) or 0))
        return profile

    def _apply_behavior_features(self, profile, text: str, timestamp: float):
        features = self._classify_user_text(text)
        if not features:
            return
        profile["updated_at"] = max(profile.get("updated_at", 0), timestamp)
        profile["totals"]["messages"] += 1
        for key in ("multi_step", "directive", "reflective", "casual", "profane", "playful"):
            profile["totals"][key] += int(features.get(key, 0))
        bucket = self._bucket_for_timestamp(timestamp or time.time())
        profile["time_buckets"][bucket] += 1
        for topic, value in features.get("topics", {}).items():
            profile["topics"][topic] += int(value)

    def _update_behavior_profile(self, text: str, timestamp: float):
        try:
            profile = self._load_behavior_profile()
            self._apply_behavior_features(profile, text, timestamp)
            self._save_behavior_profile(profile)
        except Exception as e:
            print(f"[ProjectManager] [ERR] Failed to update behavior profile: {e}")

    def build_behavior_profile_context(self, max_lines: int = 6):
        try:
            profile = self._load_behavior_profile()
        except Exception as e:
            print(f"[ProjectManager] [ERR] Failed to load behavior profile: {e}")
            return []

        totals = profile.get("totals", {})
        messages = max(int(totals.get("messages", 0)), 0)
        if messages == 0:
            return []

        lines = []

        if totals.get("casual", 0) >= 3:
            tone_line = "Sir's natural register is casual, compressed, and conversational."
            if totals.get("profane", 0) >= 2:
                tone_line += " Mild profanity appears in his tone at times; mirroring it lightly is acceptable when it feels natural."
            lines.append(tone_line)

        if totals.get("multi_step", 0) >= 3 or totals.get("directive", 0) >= max(3, totals.get("reflective", 0)):
            lines.append("Sir often gives dense multi-step commands and expects silent decomposition rather than hand-holding.")

        if totals.get("playful", 0) >= 2 and totals.get("reflective", 0) >= 2:
            lines.append("He shifts between playful edge and serious self-audit quickly. Match the room, then switch cleanly.")

        time_buckets = profile.get("time_buckets", {})
        if time_buckets:
            top_bucket = max(time_buckets, key=time_buckets.get)
            if time_buckets.get(top_bucket, 0) >= 3:
                lines.append(f"Recent activity clusters most around the {top_bucket}. Use that as soft context, not dogma.")

        topic_map = {
            "study": "exams and study pressure",
            "browser": "browser control and web workflows",
            "files": "file and project management",
            "music": "music control",
            "fitness": "fitness and nicotine discipline",
            "emotion": "emotional pattern management",
            "image": "image generation and visuals",
        }
        ranked_topics = sorted(
            ((count, topic) for topic, count in profile.get("topics", {}).items() if count > 0),
            reverse=True,
        )
        top_topics = [topic_map[topic] for count, topic in ranked_topics[:3] if count >= 2]
        if top_topics:
            lines.append("Recurring priorities lately: " + ", ".join(top_topics) + ".")

        return lines[:max_lines]

    def _default_task_store(self):
        return {"tasks": []}

    def _default_reminder_store(self):
        return {"reminders": []}

    def _default_calendar_store(self):
        return {"events": []}

    def _default_communications_store(self):
        return {"items": []}

    def _match_record(self, records, query: str, keys: tuple[str, ...]):
        normalized_query = re.sub(r"\s+", " ", (query or "").strip().lower())
        if not normalized_query:
            return None

        for record in records:
            if normalized_query == str(record.get("id", "")).lower():
                return record

        query_terms = [term for term in re.split(r"[\s_./:-]+", normalized_query) if term]
        ranked = []
        for record in records:
            haystacks = [
                re.sub(r"\s+", " ", str(record.get(key, "")).strip().lower())
                for key in keys
            ]
            score = 0
            if any(normalized_query == hay for hay in haystacks):
                score += 20
            if any(normalized_query in hay for hay in haystacks):
                score += 10
            score += sum(
                2
                for term in query_terms
                for hay in haystacks
                if term in hay
            )
            if score > 0:
                ranked.append((score, float(record.get("created_at", 0) or 0), record))

        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return ranked[0][2] if ranked else None

    def create_task(self, title: str, details: str = "", due_at: str | None = None, priority: str = "normal", project: str | None = None):
        title = re.sub(r"\s+", " ", (title or "").strip())
        if not title:
            return False, "Task title was empty.", None

        store = self._load_json_state(self.tasks_file, self._default_task_store())
        now = time.time()
        task = {
            "id": self._new_record_id("task"),
            "title": title,
            "details": (details or "").strip(),
            "due_at": (due_at or "").strip() or None,
            "priority": (priority or "normal").strip().lower(),
            "project": project or self.current_project,
            "status": "open",
            "created_at": now,
            "completed_at": None,
        }
        store["tasks"].append(task)
        self._save_json_state(self.tasks_file, store)
        return True, f"Task added: {title}.", task

    def list_tasks(self, status: str = "open", limit: int = 12):
        store = self._load_json_state(self.tasks_file, self._default_task_store())
        tasks = store.get("tasks", [])
        normalized = (status or "open").strip().lower()
        if normalized in {"open", "active", "pending"}:
            tasks = [task for task in tasks if task.get("status") != "done"]
        elif normalized in {"done", "completed", "closed"}:
            tasks = [task for task in tasks if task.get("status") == "done"]
        tasks.sort(key=lambda task: (
            task.get("status") == "done",
            task.get("due_at") or "zzzz",
            -float(task.get("created_at", 0) or 0),
        ))
        return tasks[:limit]

    def complete_task(self, query: str):
        store = self._load_json_state(self.tasks_file, self._default_task_store())
        task = self._match_record(store.get("tasks", []), query, ("title", "details", "id"))
        if not task:
            return False, f"No task matched '{query}'.", None

        task["status"] = "done"
        task["completed_at"] = time.time()
        self._save_json_state(self.tasks_file, store)
        return True, f"Completed task '{task['title']}'.", task

    def schedule_reminder(self, title: str, when: str, note: str = "", recurrence: str = "once"):
        title = re.sub(r"\s+", " ", (title or "").strip())
        when = re.sub(r"\s+", " ", (when or "").strip())
        if not title or not when:
            return False, "Reminder title and time are required.", None

        store = self._load_json_state(self.reminders_file, self._default_reminder_store())
        reminder = {
            "id": self._new_record_id("reminder"),
            "title": title,
            "when": when,
            "note": (note or "").strip(),
            "recurrence": (recurrence or "once").strip().lower(),
            "status": "active",
            "created_at": time.time(),
        }
        store["reminders"].append(reminder)
        self._save_json_state(self.reminders_file, store)
        return True, f"Reminder scheduled: {title} at {when}.", reminder

    def list_reminders(self, status: str = "active", limit: int = 12):
        store = self._load_json_state(self.reminders_file, self._default_reminder_store())
        reminders = store.get("reminders", [])
        normalized = (status or "active").strip().lower()
        if normalized in {"active", "open", "pending"}:
            reminders = [item for item in reminders if item.get("status") != "done"]
        elif normalized in {"done", "completed", "closed"}:
            reminders = [item for item in reminders if item.get("status") == "done"]
        reminders.sort(key=lambda item: ((item.get("when") or "zzzz"), -float(item.get("created_at", 0) or 0)))
        return reminders[:limit]

    def create_calendar_event(self, title: str, start_at: str, end_at: str | None = None, location: str = "", notes: str = ""):
        title = re.sub(r"\s+", " ", (title or "").strip())
        start_at = re.sub(r"\s+", " ", (start_at or "").strip())
        if not title or not start_at:
            return False, "Calendar event title and start time are required.", None

        store = self._load_json_state(self.calendar_file, self._default_calendar_store())
        event = {
            "id": self._new_record_id("event"),
            "title": title,
            "start_at": start_at,
            "end_at": (end_at or "").strip() or None,
            "location": (location or "").strip(),
            "notes": (notes or "").strip(),
            "created_at": time.time(),
        }
        store["events"].append(event)
        self._save_json_state(self.calendar_file, store)
        return True, f"Calendar event created: {title} at {start_at}.", event

    def list_calendar_events(self, limit: int = 12):
        store = self._load_json_state(self.calendar_file, self._default_calendar_store())
        events = store.get("events", [])
        events.sort(key=lambda item: ((item.get("start_at") or "zzzz"), -float(item.get("created_at", 0) or 0)))
        return events[:limit]

    def build_active_memory_context(self, short_limit: int = 8, long_limit: int = 18):
        entries = self._read_global_memory_entries()
        if not entries:
            return {"recent": [], "anchors": []}

        recent = []
        for entry in reversed(entries):
            if entry.get("kind") != "chat":
                continue
            sender = entry.get("sender", "Unknown")
            text = (entry.get("text") or "").strip()
            if not text:
                continue
            normalized = re.sub(r"\s+", " ", text.lower()).strip()
            if sender == "User" and (
                normalized.startswith((
                    "open ", "close ", "go to ", "navigate ", "play ", "pause ", "skip ",
                    "search ", "find ", "whatsapp ", "email ", "mail ", "text ", "message ",
                    "send ", "click ", "type ", "switch ", "create ", "move ", "delete ",
                ))
                or len(normalized) < 12
            ):
                continue
            recent.append({
                "sender": sender,
                "text": text,
                "timestamp": entry.get("timestamp"),
            })
            if len(recent) >= short_limit:
                break
        recent.reverse()
        anchors = self.build_silent_memory_context(limit=long_limit, max_chars=1800)
        return {"recent": recent, "anchors": anchors}

    def build_proactive_brief(self, max_lines: int = 5):
        lines = []
        open_tasks = self.list_tasks(status="open", limit=4)
        due_tasks = [task for task in open_tasks if task.get("due_at")]
        if due_tasks:
            sample = due_tasks[0]
            lines.append(f"Open task with a due time: {sample['title']} ({sample['due_at']}).")
        elif open_tasks:
            lines.append(f"Active task queue exists. Top item: {open_tasks[0]['title']}.")

        reminders = self.list_reminders(status="active", limit=3)
        if reminders:
            lines.append(f"Upcoming reminder: {reminders[0]['title']} at {reminders[0]['when']}.")

        events = self.list_calendar_events(limit=3)
        if events:
            lines.append(f"Calendar context: {events[0]['title']} at {events[0]['start_at']}.")

        profile = self._load_behavior_profile()
        topics = profile.get("topics", {})
        if topics.get("study", 0) >= 3:
            lines.append("Study pressure is a recurring live theme. Push toward concrete work when sir starts drifting.")
        if topics.get("browser", 0) >= 3:
            lines.append("Browser automation is a common workflow. Prefer structured execution over vague browsing.")

        pending_comms = self.list_pending_communications(limit=2)
        if pending_comms:
            item = pending_comms[0]
            sender = item.get("sender") or item.get("from") or "Someone"
            lines.append(f"Unread communication waiting from {sender} on {item.get('channel', 'message')}.")

        return lines[:max_lines]

    def log_communication(self, *, channel: str, direction: str, sender: str = "", recipient: str = "", subject: str = "", body: str = "", provider: str = "", metadata=None, requires_user_reply: bool = False):
        store = self._load_json_state(self.communications_file, self._default_communications_store())
        item = {
            "id": self._new_record_id("comm"),
            "channel": (channel or "").strip().lower() or "message",
            "direction": (direction or "").strip().lower() or "outbound",
            "sender": (sender or "").strip(),
            "recipient": (recipient or "").strip(),
            "subject": (subject or "").strip(),
            "body": (body or "").strip(),
            "provider": (provider or "").strip(),
            "metadata": metadata or {},
            "requires_user_reply": bool(requires_user_reply),
            "status": "pending" if requires_user_reply else "logged",
            "created_at": time.time(),
        }
        store["items"].append(item)
        self._save_json_state(self.communications_file, store)
        return item

    def list_pending_communications(self, limit: int = 6):
        store = self._load_json_state(self.communications_file, self._default_communications_store())
        items = [item for item in store.get("items", []) if item.get("status") == "pending"]
        items.sort(key=lambda item: float(item.get("created_at", 0) or 0), reverse=True)
        return items[:limit]

    def get_recent_communications(self, limit: int = 20):
        store = self._load_json_state(self.communications_file, self._default_communications_store())
        items = list(store.get("items", []))
        items.sort(key=lambda item: float(item.get("created_at", 0) or 0), reverse=True)
        return items[:limit]

    def get_recent_thread_for_contact(self, contact: str, limit: int = 6):
        contact = (contact or "").strip().lower()
        if not contact:
            return []
        store = self._load_json_state(self.communications_file, self._default_communications_store())
        items = []
        for item in store.get("items", []):
            sender = str(item.get("sender") or "").strip().lower()
            recipient = str(item.get("recipient") or "").strip().lower()
            if contact and (contact in sender or contact in recipient):
                items.append(item)
        items.sort(key=lambda item: float(item.get("created_at", 0) or 0), reverse=True)
        return items[:limit]

    def resolve_communication(self, query: str | None = None):
        store = self._load_json_state(self.communications_file, self._default_communications_store())
        items = store.get("items", [])
        if query:
            item = self._match_record(items, query, ("sender", "recipient", "subject", "body", "id"))
        else:
            pending = self.list_pending_communications(limit=1)
            item = pending[0] if pending else None
        if not item:
            return False, "No pending communication matched.", None
        item["status"] = "resolved"
        self._save_json_state(self.communications_file, store)
        return True, f"Resolved communication from {item.get('sender') or item.get('recipient') or 'unknown'}.", item

    def get_latest_communication(self, channel: str | None = None, direction: str | None = None):
        store = self._load_json_state(self.communications_file, self._default_communications_store())
        items = store.get("items", [])
        filtered = []
        for item in items:
            if channel and item.get("channel") != channel:
                continue
            if direction and item.get("direction") != direction:
                continue
            filtered.append(item)
        filtered.sort(key=lambda item: float(item.get("created_at", 0) or 0), reverse=True)
        return filtered[0] if filtered else None

    def recall_memory(self, query: str, limit: int = 8):
        """Searches the full long-term memory log for relevant entries."""
        query = (query or "").strip().lower()
        if not query:
            return []

        matches = self.build_relevant_memory_context(query, limit=limit, max_chars=5000)
        return [
            {
                "sender": entry.get("sender", "Unknown"),
                "text": entry.get("text", ""),
                "kind": entry.get("kind", "chat"),
                "timestamp": entry.get("timestamp", 0),
            }
            for entry in matches
        ]

    def _candidate_files(self):
        roots = [self.get_current_project_path(), self.desktop_projects_dir, self.workspace_root]
        seen = set()
        candidates = []
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if not path.is_file():
                    continue
                if path in seen:
                    continue
                seen.add(path)
                candidates.append(path)
        return candidates

    def find_file(self, query: str, limit: int = 8):
        query = (query or "").strip().lower()
        if not query:
            return []

        if query.startswith(("~", "/", ".")):
            path = Path(os.path.expanduser(query))
            if path.exists() and path.is_file():
                return [path]

        query_terms = [term for term in re.split(r"[\s_./-]+", query) if term]
        ranked = []
        for path in self._candidate_files():
            haystack = str(path).lower()
            name = path.name.lower()
            score = 0
            if query in haystack or query in name:
                score += 12
            score += sum(2 for term in query_terms if term in haystack)
            if self.current_project != "temp" and str(self.get_current_project_path()).lower() in haystack:
                score += 3
            if path.suffix.lower() in {".pdf", ".html", ".htm", ".docx", ".txt", ".md"}:
                score += 1
            if score > 0:
                ranked.append((score, len(str(path)), path))

        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [path for _, _, path in ranked[:limit]]

    def copy_file(self, source_query: str, destination: str | None = None):
        matches = self.find_file(source_query, limit=1)
        if not matches:
            return False, f"No file matched '{source_query}'.", None

        source = matches[0]
        normalized_destination = (destination or "").strip().lower()
        if normalized_destination in {"", "here", "current project", "this project", "current folder", "this folder"}:
            dest_base = self.get_current_project_path()
        elif normalized_destination in {"desktop", "my desktop"}:
            dest_base = Path.home() / "Desktop"
        elif destination:
            dest_base = Path(os.path.expanduser(destination))
            if not dest_base.is_absolute():
                dest_base = self.get_current_project_path() / destination
        else:
            dest_base = self.get_current_project_path()

        if dest_base.suffix:
            final_path = dest_base
            final_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            dest_base.mkdir(parents=True, exist_ok=True)
            final_path = dest_base / source.name

        shutil.copy2(source, final_path)
        return True, f"Copied '{source.name}' to '{final_path}'.", final_path

    def edit_file(self, target_query: str, content: str):
        matches = self.find_file(target_query, limit=1)
        if not matches:
            return False, f"No file matched '{target_query}'.", None

        target = matches[0]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return True, f"Updated '{target.name}'.", target

    def move_file(self, source_query: str, destination: str):
        matches = self.find_file(source_query, limit=1)
        if not matches:
            return False, f"No file matched '{source_query}'.", None

        source = matches[0]
        normalized_destination = (destination or "").strip().lower()
        if normalized_destination in {"", "here", "current project", "this project", "current folder", "this folder"}:
            dest_base = self.get_current_project_path()
        elif normalized_destination in {"desktop", "my desktop"}:
            dest_base = Path.home() / "Desktop"
        else:
            dest_base = Path(os.path.expanduser(destination))
            if not dest_base.is_absolute():
                dest_base = self.get_current_project_path() / destination

        if dest_base.suffix:
            final_path = dest_base
            final_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            dest_base.mkdir(parents=True, exist_ok=True)
            final_path = dest_base / source.name

        shutil.move(str(source), str(final_path))
        return True, f"Moved '{source.name}' to '{final_path}'.", final_path

    def delete_file(self, target_query: str):
        matches = self.find_file(target_query, limit=1)
        if not matches:
            return False, f"No file matched '{target_query}'.", None

        target = matches[0]
        target.unlink(missing_ok=False)
        return True, f"Deleted '{target.name}'.", target

    def get_conversation_archive(self, limit_sessions: int = 12, max_messages_per_session: int = 80):
        entries = [
            entry for entry in self._read_global_memory_entries()
            if entry.get("kind") == "chat" and entry.get("sender") in {"User", "Edith", "EdithVision"}
        ]
        if not entries:
            return []

        entries.sort(key=lambda item: item.get("timestamp", 0))
        sessions = []
        current = None
        last_ts = None
        gap_seconds = 20 * 60

        for entry in entries:
            ts = float(entry.get("timestamp", 0) or 0)
            conversation_number = int(entry.get("conversation") or 0)
            if (
                current is None
                or (
                    conversation_number
                    and current.get("conversation") != conversation_number
                )
                or last_ts is None
                or ts - last_ts > gap_seconds
            ):
                current = {
                    "started_at": ts,
                    "project": entry.get("project") or "temp",
                    "conversation": conversation_number or None,
                    "messages": [],
                }
                sessions.append(current)

            current["messages"].append({
                "timestamp": ts,
                "sender": entry.get("sender", "Unknown"),
                "text": entry.get("text", ""),
                "project": entry.get("project") or current["project"],
                "conversation": conversation_number or current.get("conversation"),
            })
            current["project"] = entry.get("project") or current["project"]
            if conversation_number:
                current["conversation"] = conversation_number
            last_ts = ts

        trimmed_sessions = []
        for session in sessions[-limit_sessions:]:
            trimmed_sessions.append({
                "started_at": session["started_at"],
                "project": session["project"],
                "conversation": session.get("conversation"),
                "messages": session["messages"][-max_messages_per_session:],
            })
        return list(reversed(trimmed_sessions))

    def save_cad_artifact(self, source_path: str, prompt: str):
        """Copies a generated CAD file to the project's 'cad' folder."""
        if not os.path.exists(source_path):
            print(f"[ProjectManager] [ERR] Source file not found: {source_path}")
            return None

        # Create a filename based on timestamp and prompt
        timestamp = int(time.time())
        # Brief sanitization of prompt for filename
        safe_prompt = "".join([c for c in prompt if c.isalnum() or c in (' ', '-', '_')])[:30].strip().replace(" ", "_")
        filename = f"{timestamp}_{safe_prompt}.stl"
        
        dest_path = self.get_current_project_path() / "cad" / filename
        
        try:
            shutil.copy2(source_path, dest_path)
            print(f"[ProjectManager] Saved CAD artifact to: {dest_path}")
            return str(dest_path)
        except Exception as e:
            print(f"[ProjectManager] [ERR] Failed to save artifact: {e}")
            return None

    def get_project_context(self, max_file_size: int = 10000) -> str:
        """
        Gathers context about the current project for the AI.
        Lists all files and reads text file contents (up to max_file_size bytes).
        """
        project_path = self.get_current_project_path()
        if not project_path.exists():
            return f"Project '{self.current_project}' does not exist."

        context_lines = [f"=== Project Context: '{self.current_project}' ==="]
        context_lines.append(f"Project directory: {project_path}")
        context_lines.append("")

        # List all files recursively
        all_files = []
        for root, dirs, files in os.walk(project_path):
            for f in files:
                rel_path = os.path.relpath(os.path.join(root, f), project_path)
                all_files.append(rel_path)

        if not all_files:
            context_lines.append("(No files in project yet)")
        else:
            context_lines.append(f"Files ({len(all_files)} total):")
            for f in all_files:
                context_lines.append(f"  - {f}")

        context_lines.append("")

        # Read text files (skip binary and large files)
        text_extensions = {'.txt', '.py', '.js', '.jsx', '.ts', '.tsx', '.json', '.md', '.html', '.css', '.jsonl'}
        for rel_path in all_files:
            ext = os.path.splitext(rel_path)[1].lower()
            if ext not in text_extensions:
                continue

            full_path = project_path / rel_path
            try:
                file_size = full_path.stat().st_size
                if file_size > max_file_size:
                    context_lines.append(f"--- {rel_path} (too large: {file_size} bytes, skipped) ---")
                    continue

                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                context_lines.append(f"--- {rel_path} ---")
                context_lines.append(content)
                context_lines.append("")
            except Exception as e:
                context_lines.append(f"--- {rel_path} (error reading: {e}) ---")

        return "\n".join(context_lines)

    def get_recent_chat_history(self, limit: int = 10):
        """Returns the last 'limit' chat messages from history."""
        log_file = self.get_current_project_path() / "chat_history.jsonl"
        if not log_file.exists():
            return []
            
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
            # Parse last N lines
            history = []
            for line in lines[-limit:]:
                try:
                    entry = json.loads(line)
                    history.append(entry)
                except json.JSONDecodeError:
                    continue
            return history
        except Exception as e:
            print(f"[ProjectManager] [ERR] Failed to read chat history: {e}")
            return []
