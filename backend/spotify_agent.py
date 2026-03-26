import base64
import json
import os
import secrets
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from dotenv import load_dotenv

load_dotenv()


class SpotifyAgent:
    AUTH_HOST = "127.0.0.1"
    AUTH_PORT = 8888
    TOKEN_FILE = ".spotify_tokens.json"
    SCOPES = [
        "streaming",
        "user-read-email",
        "user-read-private",
        "user-modify-playback-state",
        "user-read-playback-state",
        "user-read-currently-playing",
        "user-read-recently-played",
        "user-top-read",
    ]

    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
        self.client_id = os.getenv("SPOTIFY_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()
        self.redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback").strip()
        self.token_file = self.workspace_root / self.TOKEN_FILE
        self.tokens = self._load_tokens()
        self.auth_state = None
        self.auth_server = None
        self.auth_server_thread = None
        self.auth_event = threading.Event()
        self.auth_error = None
        self.preferred_device_id = self.tokens.get("preferred_device_id")
        self.preferred_device_name = self.tokens.get("preferred_device_name")

    def _load_tokens(self):
        if not self.token_file.exists():
            return {}
        try:
            return json.loads(self.token_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_tokens(self):
        self.tokens["preferred_device_id"] = self.preferred_device_id
        self.tokens["preferred_device_name"] = self.preferred_device_name
        self.token_file.write_text(json.dumps(self.tokens, indent=2), encoding="utf-8")

    def is_configured(self):
        return bool(self.client_id and self.client_secret and self.redirect_uri)

    def is_authenticated(self):
        return bool(self.tokens.get("access_token") and self.tokens.get("refresh_token"))

    def get_status(self):
        authenticated = self.is_authenticated()
        if authenticated:
            try:
                self.ensure_access_token()
            except Exception as exc:
                self.auth_error = str(exc)
                authenticated = False
                self.tokens = {}
                self.preferred_device_id = None
                self.preferred_device_name = None
                if self.token_file.exists():
                    self.token_file.unlink()
        return {
            "configured": self.is_configured(),
            "authenticated": authenticated,
            "auth_pending": self.auth_server is not None and not self.auth_event.is_set(),
            "auth_error": self.auth_error,
            "preferred_device_id": self.preferred_device_id,
            "preferred_device_name": self.preferred_device_name,
            "expires_at": self.tokens.get("expires_at"),
            "has_refresh_token": bool(self.tokens.get("refresh_token")),
            "web_playback_token": self.tokens.get("access_token") if authenticated else None,
        }

    def _basic_auth_header(self):
        raw = f"{self.client_id}:{self.client_secret}".encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("utf-8")

    def _request_json(self, method: str, url: str, *, headers=None, data=None):
        resolved_headers = dict(headers or {})
        req = Request(url, method=method.upper(), headers=resolved_headers)
        if data is not None:
            content_type = (resolved_headers.get("Content-Type") or resolved_headers.get("content-type") or "").lower()
            if isinstance(data, dict):
                if "application/x-www-form-urlencoded" in content_type:
                    req.data = urlencode(data).encode("utf-8")
                else:
                    req.data = json.dumps(data).encode("utf-8")
            elif isinstance(data, (bytes, bytearray)):
                req.data = data
            else:
                req.data = str(data).encode("utf-8")
        try:
            with urlopen(req, timeout=20) as response:
                text = response.read().decode("utf-8") if response.length != 0 else ""
                return response.status, json.loads(text) if text else {}
        except HTTPError as e:
            payload = e.read().decode("utf-8", errors="ignore")
            try:
                parsed = json.loads(payload)
            except Exception:
                parsed = {"error": payload or e.reason}
            raise RuntimeError(f"Spotify API error {e.code}: {parsed}")
        except URLError as e:
            raise RuntimeError(f"Spotify network error: {e.reason}")

    def ensure_access_token(self):
        if not self.is_authenticated():
            raise RuntimeError("Spotify is not authenticated")

        expires_at = float(self.tokens.get("expires_at") or 0)
        if time.time() < expires_at - 60:
            return self.tokens["access_token"]

        status, payload = self._request_json(
            "POST",
            "https://accounts.spotify.com/api/token",
            headers={
                "Authorization": self._basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.tokens["refresh_token"],
            },
        )
        if status != 200:
            raise RuntimeError("Failed to refresh Spotify token")

        self.tokens["access_token"] = payload["access_token"]
        self.tokens["expires_at"] = time.time() + int(payload.get("expires_in", 3600))
        if payload.get("refresh_token"):
            self.tokens["refresh_token"] = payload["refresh_token"]
        self._save_tokens()
        return self.tokens["access_token"]

    def _spotify_api(self, method: str, path: str, *, query=None, body=None):
        token = self.ensure_access_token()
        url = f"https://api.spotify.com/v1{path}"
        if query:
            url += "?" + urlencode(query, doseq=True)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        return self._request_json(method, url, headers=headers, data=body)

    def set_preferred_device(self, device_id: str | None, device_name: str | None = None):
        self.preferred_device_id = device_id or None
        self.preferred_device_name = device_name or None
        if self.tokens:
            self._save_tokens()

    def clear_tokens(self):
        self.tokens = {}
        self.auth_state = None
        self.auth_error = None
        self.preferred_device_id = None
        self.preferred_device_name = None
        if self.token_file.exists():
            self.token_file.unlink()

    def begin_auth(self):
        if not self.is_configured():
            raise RuntimeError("Spotify credentials are not configured")

        self.auth_state = secrets.token_urlsafe(24)
        self.auth_event.clear()
        self.auth_error = None
        self._start_callback_server()

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "scope": " ".join(self.SCOPES),
            "redirect_uri": self.redirect_uri,
            "state": self.auth_state,
            "show_dialog": "true",
        }
        return f"https://accounts.spotify.com/authorize?{urlencode(params)}"

    def _start_callback_server(self):
        if self.auth_server:
            try:
                self.auth_server.shutdown()
            except Exception:
                pass
            self.auth_server = None

        agent = self

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                parsed = urlparse(self.path)
                if parsed.path != "/callback":
                    self.send_response(404)
                    self.end_headers()
                    return

                qs = parse_qs(parsed.query)
                state = (qs.get("state") or [""])[0]
                code = (qs.get("code") or [""])[0]
                error = (qs.get("error") or [""])[0]

                if error:
                    agent.auth_error = f"Spotify authorization failed: {error}"
                    message = "Spotify authorization failed. You can close this tab."
                elif state != agent.auth_state or not code:
                    agent.auth_error = "Spotify authorization state mismatch"
                    message = "Spotify authorization state mismatch. You can close this tab."
                else:
                    try:
                        agent.exchange_code_for_token(code)
                        agent.auth_error = None
                        message = "Spotify connected successfully. You can return to Edith."
                    except Exception as exc:
                        agent.auth_error = str(exc)
                        message = f"Spotify connection failed: {exc}"

                body = f"""<!doctype html>
<html>
<head><meta charset="utf-8"><title>Spotify Auth</title></head>
<body style="background:#0b0b0b;color:#f5f5f5;font-family:-apple-system,system-ui,sans-serif;padding:40px;">
<h1 style="font-size:24px;margin:0 0 12px;">Spotify</h1>
<p style="font-size:16px;line-height:1.5;">{message}</p>
</body>
</html>"""
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body.encode("utf-8"))))
                self.end_headers()
                self.wfile.write(body.encode("utf-8"))
                agent.auth_event.set()
                threading.Thread(target=agent._shutdown_callback_server, daemon=True).start()

            def log_message(self, format, *args):
                return

        self.auth_server = ThreadingHTTPServer((self.AUTH_HOST, self.AUTH_PORT), CallbackHandler)
        self.auth_server_thread = threading.Thread(target=self.auth_server.serve_forever, daemon=True)
        self.auth_server_thread.start()

    def _shutdown_callback_server(self):
        if self.auth_server:
            try:
                self.auth_server.shutdown()
                self.auth_server.server_close()
            finally:
                self.auth_server = None

    def exchange_code_for_token(self, code: str):
        status, payload = self._request_json(
            "POST",
            "https://accounts.spotify.com/api/token",
            headers={
                "Authorization": self._basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
            },
        )
        if status != 200:
            raise RuntimeError("Failed to exchange Spotify authorization code")

        self.tokens = {
            "access_token": payload["access_token"],
            "refresh_token": payload.get("refresh_token", self.tokens.get("refresh_token")),
            "scope": payload.get("scope", ""),
            "token_type": payload.get("token_type", "Bearer"),
            "expires_at": time.time() + int(payload.get("expires_in", 3600)),
        }
        self._save_tokens()

    def get_devices(self):
        _, payload = self._spotify_api("GET", "/me/player/devices")
        return payload.get("devices", [])

    def get_playback_state(self):
        try:
            _, payload = self._spotify_api("GET", "/me/player")
            return payload
        except RuntimeError as exc:
            if "404" in str(exc):
                return {}
            raise

    def _safe_playback_state(self):
        try:
            return self.get_playback_state() or {}
        except Exception:
            return {}

    def _safe_devices(self):
        try:
            return self.get_devices() or []
        except Exception:
            return []

    def _is_restriction_error(self, error: Exception) -> bool:
        text = str(error)
        return "Restriction violated" in text or "403" in text

    def search(self, query: str, search_type: str = "track", limit: int = 5):
        _, payload = self._spotify_api(
            "GET",
            "/search",
            query={
                "q": query,
                "type": search_type,
                "limit": limit,
            },
        )
        return payload

    def _normalize_device_text(self, text: str):
        normalized = (text or "").strip().lower()
        normalized = normalized.replace("-", " ")
        normalized = normalized.replace("_", " ")
        normalized = " ".join(normalized.split())
        replacements = {
            "air pods": "airpods",
            "head phones": "headphones",
            "speaker system": "speaker",
            "tv speaker": "tv",
            "television": "tv",
            "iphone": "phone",
            "mobile": "phone",
            "cell phone": "phone",
            "macbook": "laptop",
            "computer": "laptop",
        }
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)
        return normalized

    def _device_aliases(self, device: dict):
        name = self._normalize_device_text(device.get("name", ""))
        device_type = self._normalize_device_text(device.get("type", ""))
        aliases = {name}

        if "speaker" in name or device_type == "speaker":
            aliases.update({"speaker", "speakers", "room speaker"})
        if any(token in name for token in ("airpods", "headphones", "buds")):
            aliases.update({"headphones", "headphone", "airpods", "buds"})
        if any(token in name for token in ("iphone", "phone")):
            aliases.update({"phone", "iphone", "mobile"})
        if any(token in name for token in ("tv", "television")):
            aliases.update({"tv", "television"})
        if any(token in name for token in ("macbook", "laptop", "computer")):
            aliases.update({"laptop", "computer", "macbook"})
        if "edith" in name:
            aliases.update({"edith", "this device", "this mac", "this computer"})

        room_tokens = ("dining room", "living room", "bedroom", "study", "office", "kitchen")
        for token in room_tokens:
            if token in name:
                aliases.add(token)
                if "speaker" in name:
                    aliases.add(f"{token} speaker")

        if device_type:
            aliases.add(device_type)
        return {alias for alias in aliases if alias}

    def _score_name_match(self, device: dict, query: str):
        label_norm = self._normalize_device_text(device.get("name", ""))
        query_norm = self._normalize_device_text(query)
        if not label_norm or not query_norm:
            return 0
        score = 0
        if query_norm == label_norm:
            score += 12
        if query_norm in label_norm or label_norm in query_norm:
            score += 8
        aliases = self._device_aliases(device)
        if query_norm in aliases:
            score += 10
        query_terms = [term for term in query_norm.split() if term]
        score += sum(2 for term in query_terms if term in label_norm)
        for alias in aliases:
            if alias == query_norm:
                score += 6
            elif query_norm in alias or alias in query_norm:
                score += 3
        device_type = self._normalize_device_text(device.get("type", ""))
        if device_type and device_type in query_norm:
            score += 2
        return score

    def _device_by_id(self, device_id: str | None):
        if not device_id:
            return None
        devices = self.get_devices()
        return next((device for device in devices if device.get("id") == device_id), None)

    def find_device(self, query: str):
        query_norm = (query or "").strip()
        if not query_norm:
            return None
        devices = self.get_devices()
        ranked = []
        for device in devices:
            name = device.get("name", "")
            score = self._score_name_match(device, query_norm)
            if score <= 0:
                continue
            if device.get("is_active"):
                score += 2
            if device.get("is_restricted"):
                score -= 5
            ranked.append((score, len(name or ""), device))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return ranked[0][2] if ranked else None

    def _resolve_target_device(self, explicit_device_id: str | None = None):
        devices = self.get_devices()

        if explicit_device_id:
            return explicit_device_id
        if self.preferred_device_id:
            preferred = next((d for d in devices if d.get("id") == self.preferred_device_id), None)
            if preferred and not (preferred.get("is_restricted") or False):
                return self.preferred_device_id

        active = next((d for d in devices if d.get("is_active")), None)
        if active and not (active.get("is_restricted") or False):
            return active.get("id")

        unrestricted = next((d for d in devices if not (d.get("is_restricted") or False)), None)
        if unrestricted:
            return unrestricted.get("id")

        return devices[0]["id"] if devices else None

    def _resolve_target_device_with_query(self, explicit_device_id: str | None = None, device_query: str | None = None):
        if explicit_device_id:
            return explicit_device_id
        if device_query:
            matched = self.find_device(device_query)
            if matched and matched.get("id"):
                return matched["id"]
        return self._resolve_target_device(explicit_device_id)

    def transfer_playback(self, device_id: str | None = None, play: bool = True):
        target_device = self._resolve_target_device(device_id)
        if not target_device:
            raise RuntimeError("No Spotify playback device is available")
        self._spotify_api(
            "PUT",
            "/me/player",
            body={"device_ids": [target_device], "play": bool(play)},
        )
        matched = self._device_by_id(target_device)
        if matched:
            self.set_preferred_device(matched.get("id"), matched.get("name"))
        return {"device_id": target_device, "device_name": (matched or {}).get("name"), "play": bool(play)}

    def transfer_playback_to_query(self, device_query: str | None = None, play: bool = True):
        target_device = self._resolve_target_device_with_query(device_query=device_query)
        if not target_device:
            raise RuntimeError("No matching Spotify playback device is available")
        self._spotify_api(
            "PUT",
            "/me/player",
            body={"device_ids": [target_device], "play": bool(play)},
        )
        matched = self.find_device(device_query or "") if device_query else None
        if matched:
            self.set_preferred_device(matched.get("id"), matched.get("name"))
        return {
            "device_id": target_device,
            "device_name": (matched or {}).get("name"),
            "play": bool(play),
        }

    def _normalize_play_kind(self, kind: str | None, query: str | None):
        normalized = (kind or "").strip().lower()
        if normalized in {"track", "album", "playlist", "artist"}:
            return normalized
        query_norm = (query or "").strip().lower()
        if not query_norm:
            return "track"
        if "playlist" in query_norm:
            return "playlist"
        if "album" in query_norm or "ep " in query_norm or query_norm.endswith(" ep"):
            return "album"
        if "artist" in query_norm:
            return "artist"
        return "track"

    def _pick_search_item(self, payload: dict, kind: str):
        key_map = {
            "track": "tracks",
            "album": "albums",
            "playlist": "playlists",
            "artist": "artists",
        }
        key = key_map[kind]
        items = (payload.get(key) or {}).get("items", [])
        return items[0] if items else None

    def _describe_spotify_item(self, item: dict, kind: str):
        if kind == "track":
            artists = ", ".join(a.get("name", "") for a in item.get("artists", []))
            return f"{item.get('name')} - {artists}".strip(" -")
        if kind == "album":
            artists = ", ".join(a.get("name", "") for a in item.get("artists", []))
            return f"{item.get('name')} by {artists}".strip()
        if kind == "playlist":
            owner = ((item.get("owner") or {}).get("display_name") or "").strip()
            return f"{item.get('name')} by {owner}".strip(" by")
        if kind == "artist":
            return item.get("name") or "the requested artist"
        return item.get("name") or "the requested audio"

    def play(self, *, query: str | None = None, uri: str | None = None, device_id: str | None = None, device_query: str | None = None, kind: str | None = None):
        target_device = self._resolve_target_device_with_query(device_id, device_query)
        if not target_device:
            raise RuntimeError("No Spotify playback device is available")

        body: dict[str, Any] | None = None
        selected_name = None
        resolved_kind = self._normalize_play_kind(kind, query)

        if query and not uri:
            search_types = resolved_kind if resolved_kind != "track" else "track,album,playlist,artist"
            results = self.search(query, search_types, limit=5)
            if resolved_kind == "track":
                selected_kind = None
                selected_item = None
                for candidate_kind in ("track", "playlist", "album", "artist"):
                    item = self._pick_search_item(results, candidate_kind)
                    if item:
                        selected_kind = candidate_kind
                        selected_item = item
                        break
                if not selected_item:
                    raise RuntimeError(f"No Spotify result found for '{query}'")
            else:
                selected_kind = resolved_kind
                selected_item = self._pick_search_item(results, resolved_kind)
                if not selected_item:
                    raise RuntimeError(f"No Spotify {resolved_kind} found for '{query}'")

            uri = selected_item.get("uri")
            selected_name = self._describe_spotify_item(selected_item, selected_kind)
            resolved_kind = selected_kind

        matched_device = None
        if device_query:
            matched_device = self.find_device(device_query)

        if uri:
            if resolved_kind == "track":
                body = {"uris": [uri]}
            else:
                body = {"context_uri": uri}

        self._spotify_api("PUT", "/me/player/play", query={"device_id": target_device}, body=body)
        if matched_device:
            self.set_preferred_device(matched_device.get("id"), matched_device.get("name"))
        elif target_device:
            matched_device = self._device_by_id(target_device)
            if matched_device:
                self.set_preferred_device(matched_device.get("id"), matched_device.get("name"))
        return {
            "device_id": target_device,
            "device_name": (matched_device or {}).get("name"),
            "uri": uri,
            "kind": resolved_kind,
            "selected_name": selected_name,
        }

    def pause(self, device_id: str | None = None):
        target_device = self._resolve_target_device(device_id)
        try:
            self._spotify_api("PUT", "/me/player/pause", query={"device_id": target_device} if target_device else None)
            return {"device_id": target_device}
        except RuntimeError as exc:
            if self._is_restriction_error(exc):
                state = self.get_playback_state() or {}
                if not state.get("is_playing", False):
                    return {"device_id": target_device, "fallback_verified": True}
            raise

    def next_track(self, device_id: str | None = None):
        target_device = self._resolve_target_device(device_id)
        self._spotify_api("POST", "/me/player/next", query={"device_id": target_device} if target_device else None)
        return {"device_id": target_device}

    def previous_track(self, device_id: str | None = None):
        target_device = self._resolve_target_device(device_id)
        self._spotify_api("POST", "/me/player/previous", query={"device_id": target_device} if target_device else None)
        return {"device_id": target_device}

    def set_volume(self, volume_percent: int, device_id: str | None = None):
        target_device = self._resolve_target_device(device_id)
        volume = max(0, min(100, int(volume_percent)))
        query = {"volume_percent": volume}
        if target_device:
            query["device_id"] = target_device
        self._spotify_api("PUT", "/me/player/volume", query=query)
        return {"device_id": target_device, "volume_percent": volume}

    def confirm_action_effect(self, action: str, *, before_state=None, device_id: str | None = None, device_query: str | None = None, volume_percent: int | None = None, wait_seconds: float = 0.45):
        time.sleep(wait_seconds)
        after_state = self._safe_playback_state()
        after_devices = self._safe_devices()
        before_state = before_state or {}
        before_item = before_state.get("item") or {}
        after_item = after_state.get("item") or {}
        before_uri = before_item.get("uri")
        after_uri = after_item.get("uri")

        if action == "pause":
            return (not after_state.get("is_playing", False), after_state)

        if action == "play":
            return (bool(after_state.get("is_playing", False) or after_item.get("uri")), after_state)

        if action in {"next", "previous"}:
            changed_track = bool(after_uri and before_uri and after_uri != before_uri)
            progress_reset = (
                isinstance(before_state.get("progress_ms"), int)
                and isinstance(after_state.get("progress_ms"), int)
                and after_state.get("progress_ms", 0) + 1500 < before_state.get("progress_ms", 0)
            )
            return (changed_track or progress_reset or bool(after_item.get("uri")), after_state)

        if action == "transfer":
            target_device = self._resolve_target_device_with_query(device_id, device_query)
            active = next((device for device in after_devices if device.get("is_active")), None)
            return (bool(target_device and active and active.get("id") == target_device), after_state)

        if action == "volume":
            target_device = self._resolve_target_device_with_query(device_id, device_query)
            target = None
            if target_device:
                target = next((device for device in after_devices if device.get("id") == target_device), None)
            if not target:
                target = next((device for device in after_devices if device.get("is_active")), None)
            actual = target.get("volume_percent") if target else None
            if actual is None:
                return (False, after_state)
            requested = max(0, min(100, int(volume_percent or 0)))
            return (abs(actual - requested) <= 5, after_state)

        return (False, after_state)

    def get_recent_tracks(self, limit: int = 10):
        _, payload = self._spotify_api("GET", "/me/player/recently-played", query={"limit": max(1, min(limit, 50))})
        return payload.get("items", [])

    def get_top_tracks(self, limit: int = 10, time_range: str = "medium_term"):
        _, payload = self._spotify_api(
            "GET",
            "/me/top/tracks",
            query={"limit": max(1, min(limit, 50)), "time_range": time_range},
        )
        return payload.get("items", [])

    def dj_pick(self, prompt: str | None = None):
        current = self.get_playback_state() or {}
        current_uri = ((current.get("item") or {}).get("uri")) if current else None

        if prompt:
            result = self.play(query=prompt)
            result["mode"] = "prompt"
            return result

        recent_items = self.get_recent_tracks(limit=15)
        recent_uris = {
            ((item.get("track") or {}).get("uri"))
            for item in recent_items
            if item.get("track")
        }

        top_tracks = self.get_top_tracks(limit=20)
        for track in top_tracks:
            uri = track.get("uri")
            if not uri or uri == current_uri:
                continue
            if uri in recent_uris:
                continue
            result = self.play(uri=uri)
            result["mode"] = "top_tracks"
            result["selected_name"] = f"{track.get('name')} - {', '.join(a.get('name', '') for a in track.get('artists', []))}".strip(" -")
            return result

        if top_tracks:
            track = top_tracks[0]
            result = self.play(uri=track.get("uri"))
            result["mode"] = "fallback_top_track"
            result["selected_name"] = f"{track.get('name')} - {', '.join(a.get('name', '') for a in track.get('artists', []))}".strip(" -")
            return result

        raise RuntimeError("Spotify DJ mode could not find a suitable next track")

    def open_auth_in_browser(self):
        auth_url = self.begin_auth()
        webbrowser.open(auth_url)
        return auth_url
