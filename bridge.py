from __future__ import annotations

import argparse
import asyncio
import base64
import collections
import contextlib
import datetime
import json
import logging
import os
import random
import re
import ssl
import sys
import time
import webbrowser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import aiohttp
    from aiohttp import web
except ImportError:
    sys.exit("Manca aiohttp. Installa con:  pip install -r requirements.txt")

LOG = logging.getLogger("valo")

LOG_LINES: "collections.deque[dict[str, Any]]" = collections.deque(maxlen=300)


MESSAGES = {
    "Collegato come %s#%s  region=%s shard=%s build=%s":
        "Connected as %s#%s  region=%s shard=%s build=%s",
    "Cache partite: %d gia' analizzate":
        "Match cache: %d already analysed",
    "Cache lobby: %d partite gia' lette":
        "Lobby cache: %d matches already read",
    "Cronologia competitive non leggibile: %s":
        "Competitive history not readable: %s",
    "Match %s non leggibile: %s":
        "Match %s not readable: %s",
    "Act in corso: %d da Riot, %d dall'archivio, medie su %d "
    "(Riot ne dichiara %d)":
        "Current act: %d from Riot, %d from the archive, averages over %d "
        "(Riot declares %d)",
    "Account cambiato: ora sei %s#%s":
        "Account changed: you are now %s#%s",
    "Aggiorno statistiche":
        "Refreshing stats",
    "Aggiorno statistiche (%s)":
        "Refreshing stats (%s)",
    "Aggiornamento statistiche fallito: %s":
        "Stats refresh failed: %s",
    "La presenza non contiene sessionLoopState. Passo agli endpoint "
    "sul mio puuid per capire se sono in partita.":
        "Presence carries no sessionLoopState. Falling back to the endpoints "
        "on my own puuid to tell whether I am in a match.",
    "Stato partita: %s -> %s":
        "Match state: %s -> %s",
    "Stato partita: %s -> %s (via endpoint proprio)":
        "Match state: %s -> %s (via own endpoint)",
    "Roster partita %s (%s): %d in squadra, %d avversari":
        "Match roster %s (%s): %d on your team, %d enemies",
    "Partita nuova senza passare dai menu: %s":
        "New match without going through the menus: %s",
    "Medie: %d giocatori su %d in %.0fs (%d partite considerate, "
    "%d in cache, %d frenate da Riot)":
        "Averages: %d players out of %d in %.0fs (%d matches considered, "
        "%d cached, %d throttled by Riot)",
    "Websocket: variante '%s' accettata":
        "Websocket: variant '%s' accepted",
    "%s Resto in attesa.":
        "%s Standing by.",
    "%s (%s). Resto in attesa.":
        "%s (%s). Standing by.",
    "Il Riot Client risponde ma Valorant non e' in presenza.":
        "The Riot Client answers but Valorant is not in presence.",
    "Client non raggiungibile":
        "Client not reachable",
    "Presenza Valorant agganciata.":
        "Valorant presence hooked.",
    "In ascolto sulle presenze":
        "Listening on presences",
    "Websocket chiuso (%s). Riprovo in sottofondo.":
        "Websocket closed (%s). Retrying in the background.",
    "Nessuna variante websocket accettata da questo client "
    "(build %s). Uso il polling ogni 2s: funziona, con al massimo "
    "2 secondi di ritardo sul cambio di stato.":
        "No websocket variant accepted by this client (build %s). Falling "
        "back to polling every 2s: it works, with at most 2 seconds of delay "
        "on state changes.",
    "Dashboard collegato (%d attivi)":
        "Dashboard connected (%d active)",
    "Dashboard scollegato (%d attivi)":
        "Dashboard disconnected (%d active)",
    "Chiusura richiesta dal dashboard.":
        "Shutdown requested from the dashboard.",
    "Chiave HenrikDev accettata e salvata.":
        "HenrikDev key accepted and saved.",
    "Chiave HenrikDev salvata. L'archivio non conosce ancora "
    "questo account: si popola dopo la prossima partita.":
        "HenrikDev key saved. The archive does not know this account yet: "
        "it fills in after the next match.",
    "avvio": "startup",
    "richiesta manuale": "manual request",
    "dal dashboard": "from the dashboard",
    "fine partita": "match over",
    "cambio account": "account switch",
    "chiave nuova": "new key",
    "periodico": "periodic",
    "archivio": "archive",
    "unione": "both sources",
    "connessione rifiutata": "connection refused",
    "rifiutata": "rejected",
    "vuota": "empty",
    "Lockfile non trovato. Avvia il Riot Client e riprova.":
        "Lockfile not found. Start the Riot Client and try again.",
    "Regione non rilevata. Entra una volta nel menu di Valorant, oppure "
    "imposta le variabili d'ambiente VALO_REGION e VALO_SHARD.":
        "Region not detected. Enter the Valorant menu once, or set the "
        "VALO_REGION and VALO_SHARD environment variables.",
    "Versione client non rilevata. Avvia Valorant e riprova.":
        "Client version not detected. Start Valorant and try again.",
    "Il Riot Client e' aperto ma Valorant no. Avvia Valorant e "
    "aspetta di essere nel menu principale.":
        "The Riot Client is open but Valorant is not. Start Valorant and wait "
        "until you are in the main menu.",
}


def tr_en(text: str) -> str:
    return MESSAGES.get(text, text)


class UILogHandler(logging.Handler):

    def emit(self, record: logging.LogRecord) -> None:
        with contextlib.suppress(Exception):
            LOG_LINES.append({
                "at": record.created,
                "level": record.levelname,
                "text": record.getMessage(),
                "en": self.in_english(record),
            })

    @staticmethod
    def in_english(record: logging.LogRecord) -> str:
        args = record.args if isinstance(record.args, tuple) else (
            () if record.args is None else (record.args,))
        try:
            english = tr_en(str(record.msg))
            return english % tuple(
                tr_en(a) if isinstance(a, str) else a for a in args
            ) if args else english
        except Exception:
            return record.getMessage()

HERE = Path(__file__).resolve().parent
WEB_DIR = HERE / "web"

UI_VERSION = "56"


def find_index() -> "Path | None":
    for cand in (WEB_DIR / "index.html", HERE / "index.html"):
        if cand.is_file():
            return cand
    return None


def index_ui_version() -> str | None:
    page = find_index()
    if page is None:
        return None
    try:
        text = page.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    m = re.search(r'name="valo-ui"\s+content="([^"]+)"', text)
    return m.group(1) if m else "assente"


MISSING_PAGE = """<!DOCTYPE html><html lang="it"><meta charset="utf-8">
<title>index.html mancante</title>
<style>body{{background:#10171a;color:#e8e4da;font:14px/1.7 ui-monospace,monospace;
padding:56px 32px;max-width:660px}}b{{color:#f0a23c}}code{{color:#f0a23c}}
p{{color:#7d8f94}}</style>
<p><b>Manca index.html.</b></p>
<p>Il ponte è partito ma non trova il dashboard. Mettilo in una di queste posizioni:</p>
<p><code>{a}</code><br><code>{b}</code></p>
<p>Poi ricarica questa pagina. Il ponte non va riavviato.</p>
</html>"""


TIERS = [
    "Unranked", "-", "-",
    "Iron 1", "Iron 2", "Iron 3",
    "Bronze 1", "Bronze 2", "Bronze 3",
    "Silver 1", "Silver 2", "Silver 3",
    "Gold 1", "Gold 2", "Gold 3",
    "Platinum 1", "Platinum 2", "Platinum 3",
    "Diamond 1", "Diamond 2", "Diamond 3",
    "Ascendant 1", "Ascendant 2", "Ascendant 3",
    "Immortal 1", "Immortal 2", "Immortal 3",
    "Radiant",
]

SHARD_BY_REGION = {
    "na": "na", "latam": "na", "br": "na",
    "eu": "eu", "ap": "ap", "kr": "kr", "pbe": "pbe",
}

REGION_ALIAS = {
    "euw": "eu", "euw1": "eu", "eune": "eu", "eun1": "eu", "eu1": "eu",
    "tr": "eu", "tr1": "eu", "ru": "eu", "ru1": "eu", "me": "eu", "me1": "eu",
    "oce": "ap", "oc1": "ap", "sg": "ap", "sg2": "ap", "tw": "ap", "tw2": "ap",
    "vn": "ap", "vn2": "ap", "th": "ap", "th2": "ap", "ph": "ap", "ph2": "ap",
    "id": "ap", "jp": "ap", "jp1": "ap", "sea": "ap",
    "lan": "latam", "la1": "latam", "las": "latam", "la2": "latam",
    "na1": "na", "br1": "br", "kr1": "kr",
}


def normalize_region(region: str) -> tuple[str, str]:
    region = REGION_ALIAS.get(region, region)
    return region, SHARD_BY_REGION.get(region, "")

CLIENT_PLATFORM = (
    "ew0KCSJwbGF0Zm9ybVR5cGUiOiAiUEMiLA0KCSJwbGF0Zm9ybU9TIjogIldpbmRvd3MiLA0K"
    "CSJwbGF0Zm9ybU9TVmVyc2lvbiI6ICIxMC4wLjE5MDQyLjEuMjU2LjY0Yml0IiwNCgkicGxh"
    "dGZvcm1DaGlwc2V0IjogIlVua25vd24iDQp9"
)

QUEUE_LABELS = {
    "competitive": "Competitive",
    "unrated": "Unrated",
    "swiftplay": "Swiftplay",
    "spikerush": "Spike Rush",
    "deathmatch": "Deathmatch",
    "ggteam": "Escalation",
    "hurm": "Team Deathmatch",
    "premier": "Premier",
    "": "Custom",
}

CACHE_VERSION = 1
ROW_CACHE_VERSION = 3

FFA_QUEUES = {"deathmatch"}

STATE_LABELS = {
    "MENUS": "Nei menu",
    "PREGAME": "Agent select",
    "INGAME": "In partita",
    "AWAY": "Assente",
    "OFFLINE": "Offline",
}


def local_appdata() -> Path:
    p = os.environ.get("LOCALAPPDATA")
    if p:
        return Path(p)
    return Path.home() / "AppData" / "Local"


LOCKFILE_PATH = Path(
    os.environ.get("VALO_LOCKFILE")
    or local_appdata() / "Riot Games" / "Riot Client" / "Config" / "lockfile"
)
SHOOTER_LOG = local_appdata() / "VALORANT" / "Saved" / "Logs" / "ShooterGame.log"
CACHE_FILE = local_appdata() / "valo-readout" / "matches.json"
STARTUP_LOG = local_appdata() / "valo-readout" / "bridge.log"
PEEK_CACHE_FILE = local_appdata() / "valo-readout" / "peeked.json"
INSTANCE_LOCK = local_appdata() / "valo-readout" / "bridge.lock"
PEEK_CACHE_MAX = 12000
PEEK_ACT = -1


def short_error(exc: BaseException) -> str:
    if isinstance(exc, aiohttp.ClientConnectorError):
        host = getattr(exc, "host", "") or ""
        cause = getattr(getattr(exc, "os_error", None), "strerror", "") or ""
        if host:
            return f"{host} non raggiungibile" + (f" ({cause})" if cause else "")
        return "connessione rifiutata" + (f" ({cause})" if cause else "")
    text = str(exc)
    return re.sub(r"\s*ssl:<[^>]*>", "", text).strip() or type(exc).__name__


def side_label(team: str, rounds_played: int | None) -> str:
    if not team:
        return ""
    parte = "attacco" if str(team).lower() == "red" else "difesa"
    if rounds_played is None:
        return parte
    if rounds_played >= 24:
        return ""
    if rounds_played >= 12:
        parte = "difesa" if parte == "attacco" else "attacco"
    return parte


def iso_ms(value: Any) -> int:
    with contextlib.suppress(Exception):
        testo = str(value).replace("Z", "+00:00")
        return int(datetime.datetime.fromisoformat(testo).timestamp() * 1000)
    return 0


def remote_ssl() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    with contextlib.suppress(Exception):
        import certifi
        ctx.load_verify_locations(cafile=certifi.where())
    return ctx


class BridgeError(RuntimeError):

    def __init__(self, message: str, en: str = "") -> None:
        super().__init__(message)
        self.en = en or tr_en(message)


HENRIK_KEY_FILE = local_appdata() / "valo-readout" / "henrik.key"
HENRIK_BASE = "https://api.henrikdev.xyz/valorant"


class Henrik:

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self.session = session
        self.key = os.environ.get("VALO_HENRIK_KEY", "").strip()
        if not self.key:
            with contextlib.suppress(OSError):
                self.key = HENRIK_KEY_FILE.read_text(encoding="utf-8").strip()
        self._calls: list[float] = []
        self._lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        return bool(self.key)

    async def adopt(self, key: str, region: str, puuid: str) -> str:
        key = key.strip()
        if not key:
            return "vuota"
        url = f"{HENRIK_BASE}/v1/by-puuid/lifetime/matches/{region}/{puuid}"
        try:
            async with self.session.get(
                url, headers={"Authorization": key},
                params={"mode": "competitive", "size": "1"},
            ) as r:
                esito = ""
                if r.status in (401, 403):
                    return "rifiutata"
                if r.status == 404:
                    esito = "nuovo"
                elif r.status != 200:
                    return f"http {r.status}"
        except Exception as exc:
            return short_error(exc)

        with contextlib.suppress(OSError):
            HENRIK_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
            HENRIK_KEY_FILE.write_text(key, encoding="utf-8")
        self.key = key
        if esito == "nuovo":
            LOG.info("Chiave HenrikDev salvata. L'archivio non conosce ancora "
                     "questo account: si popola dopo la prossima partita.")
        else:
            LOG.info("Chiave HenrikDev accettata e salvata.")
        return esito

    async def _throttle(self) -> None:
        async with self._lock:
            now = time.time()
            self._calls = [t for t in self._calls if now - t < 60]
            if len(self._calls) >= 26:
                await asyncio.sleep(max(0.0, 60 - (now - self._calls[0]) + 0.5))
                now = time.time()
                self._calls = [t for t in self._calls if now - t < 60]
            self._calls.append(time.time())

    async def lifetime(self, puuid: str, region: str,
                       size: int = 200) -> list[dict[str, Any]] | None:
        if not self.enabled:
            return None
        await self._throttle()
        url = f"{HENRIK_BASE}/v1/by-puuid/lifetime/matches/{region}/{puuid}"
        try:
            async with self.session.get(
                url, headers={"Authorization": self.key},
                params={"mode": "competitive", "size": str(size)},
            ) as r:
                if r.status != 200:
                    LOG.debug("Henrik %s -> http %s", puuid[:8], r.status)
                    return None
                body = await r.json(content_type=None)
        except Exception as exc:
            LOG.debug("Henrik %s non raggiungibile: %s", puuid[:8], short_error(exc))
            return None

        rows: list[dict[str, Any]] = []
        for m in (body or {}).get("data") or []:
            meta = m.get("meta") or {}
            st = m.get("stats") or {}
            teams = m.get("teams") or {}
            mine = str(st.get("team", "")).lower()
            other = "blue" if mine == "red" else "red"
            my_r, their_r = teams.get(mine), teams.get(other)
            rounds = (my_r or 0) + (their_r or 0)
            shots = st.get("shots") or {}
            score = st.get("score", 0)
            rows.append({
                "matchId": meta.get("id", ""),
                "seasonId": str((meta.get("season") or {}).get("id", "")).lower(),
                "seasonShort": str((meta.get("season") or {}).get("short", "")),
                "map": (meta.get("map") or {}).get("name", "—"),
                "agent": (st.get("character") or {}).get("name", "—"),
                "kills": st.get("kills", 0),
                "deaths": st.get("deaths", 0),
                "assists": st.get("assists", 0),
                "score": score,
                "combatScore": score,
                "rounds": rounds,
                "acs": round(score / rounds, 1) if rounds else 0.0,
                "shots": {"head": shots.get("head", 0),
                          "body": shots.get("body", 0),
                          "leg": shots.get("leg", 0)},
                "won": None if my_r is None or their_r is None else my_r > their_r,
                "startedAt": iso_ms(meta.get("started_at")),
            })
        return rows

    async def mmr_by_act(self, puuid: str,
                         region: str) -> dict[str, dict[str, int]] | None:
        if not self.enabled:
            return None
        await self._throttle()
        url = f"{HENRIK_BASE}/v2/by-puuid/mmr/{region}/{puuid}"
        try:
            async with self.session.get(
                url, headers={"Authorization": self.key},
            ) as r:
                if r.status != 200:
                    return None
                body = await r.json(content_type=None)
        except Exception as exc:
            LOG.debug("Henrik mmr %s: %s", puuid[:8], short_error(exc))
            return None

        fuori: dict[str, dict[str, int]] = {}
        for short, s in ((body or {}).get("data") or {}).get("by_season", {}).items():
            if not isinstance(s, dict) or not s.get("number_of_games"):
                continue
            gradi = [int(s.get("final_rank") or 0)]
            gradi += [int(w.get("tier") or 0) for w in (s.get("act_rank_wins") or [])]
            fuori[short] = {
                "peak": max(gradi),
                "games": int(s.get("number_of_games") or 0),
                "wins": int(s.get("wins") or 0),
            }
        return fuori

    async def rr_samples(self, puuid: str,
                         region: str) -> list[tuple[str, int, int]] | None:
        if not self.enabled:
            return None
        await self._throttle()
        url = f"{HENRIK_BASE}/v1/by-puuid/stored-mmr-history/{region}/{puuid}"
        try:
            async with self.session.get(
                url, headers={"Authorization": self.key},
                params={"size": "1000"},
            ) as r:
                if r.status != 200:
                    return None
                body = await r.json(content_type=None)
        except Exception as exc:
            LOG.debug("Henrik mmr-history %s: %s", puuid[:8], short_error(exc))
            return None

        fuori: list[tuple[str, int, int]] = []
        for m in (body or {}).get("data") or []:
            sid = str((m.get("season") or {}).get("id", "")).lower()
            grado = (m.get("tier") or {}).get("id")
            rr = m.get("ranking_in_tier")
            if sid and grado is not None and rr is not None:
                fuori.append((sid, int(grado), int(rr)))
        return fuori

    async def act_rows(self, puuid: str, region: str,
                       acts: set[str]) -> list[dict[str, Any]] | None:
        rows = await self.lifetime(puuid, region)
        if rows is None:
            return None
        return [r for r in rows if r["seasonId"] in acts]


@dataclass
class Lockfile:
    name: str
    pid: int
    port: int
    password: str
    protocol: str

    @property
    def basic_auth(self) -> str:
        raw = f"riot:{self.password}".encode()
        return "Basic " + base64.b64encode(raw).decode()

    @classmethod
    def read(cls) -> "Lockfile":
        if not LOCKFILE_PATH.exists():
            raise BridgeError("Lockfile non trovato. Avvia il Riot Client e riprova.")
        parts = LOCKFILE_PATH.read_text(encoding="utf-8").strip().split(":")
        if len(parts) != 5:
            raise BridgeError(f"Lockfile in formato inatteso: {parts!r}",
                              f"Lockfile in unexpected format: {parts!r}")
        return cls(parts[0], int(parts[1]), int(parts[2]), parts[3], parts[4])


class RiotClient:

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self.session = session
        self.lock: Lockfile | None = None
        self.puuid = ""
        self.game_name = ""
        self.game_tag = ""
        self.access_token = ""
        self.entitlement = ""
        self.region = ""
        self.shard = ""
        self.client_version = ""
        self._token_at = 0.0
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self._local_ssl = ctx


    @property
    def local_base(self) -> str:
        assert self.lock is not None
        return f"https://127.0.0.1:{self.lock.port}"

    async def local_get(self, path: str) -> Any:
        assert self.lock is not None
        headers = {"Authorization": self.lock.basic_auth}
        async with self.session.get(
            self.local_base + path, headers=headers, ssl=self._local_ssl
        ) as r:
            r.raise_for_status()
            return await r.json(content_type=None)


    @property
    def pd(self) -> str:
        return f"https://pd.{self.shard}.a.pvp.net"

    @property
    def glz(self) -> str:
        return f"https://glz-{self.region}-1.{self.shard}.a.pvp.net"

    @property
    def shared(self) -> str:
        return f"https://shared.{self.shard}.a.pvp.net"

    async def _remote_headers(self) -> dict[str, str]:
        if time.time() - self._token_at > 45 * 60:
            await self.refresh_tokens()
        return {
            "Authorization": f"Bearer {self.access_token}",
            "X-Riot-Entitlements-JWT": self.entitlement,
            "X-Riot-ClientPlatform": CLIENT_PLATFORM,
            "X-Riot-ClientVersion": self.client_version,
        }

    async def remote_get(self, url: str) -> Any:
        headers = await self._remote_headers()
        async with self.session.get(url, headers=headers) as r:
            if r.status == 404:
                return None
            r.raise_for_status()
            return await r.json(content_type=None)

    async def remote_put(self, url: str, payload: Any) -> Any:
        headers = await self._remote_headers()
        async with self.session.put(url, headers=headers, json=payload) as r:
            if r.status == 404:
                return None
            r.raise_for_status()
            return await r.json(content_type=None)


    async def connect(self) -> None:
        self.lock = Lockfile.read()
        try:
            await self.refresh_tokens()
        except aiohttp.ClientConnectorError:
            raise BridgeError(
                f"Il lockfile indica la porta {self.lock.port} ma nessuno risponde. "
                "Di solito e' un lockfile vecchio: chiudi del tutto Valorant e il "
                "Riot Client, riaprili, poi riavvia il ponte.",
                f"The lockfile points at port {self.lock.port} but nobody answers. "
                "Usually it is a stale lockfile: close Valorant and the Riot "
                "Client completely, reopen them, then restart the bridge."
            ) from None
        await self.load_identity()
        await self.detect_region()
        await self.detect_version()
        LOG.info(
            "Collegato come %s#%s  region=%s shard=%s build=%s",
            self.game_name, self.game_tag, self.region, self.shard, self.client_version,
        )

    async def refresh_tokens(self) -> None:
        try:
            data = await self.local_get("/entitlements/v1/token")
        except aiohttp.ClientResponseError as exc:
            if exc.status in (401, 403, 404):
                raise BridgeError(
                    "Il Riot Client e' aperto ma Valorant no. Avvia Valorant e "
                    "aspetta di essere nel menu principale.") from None
            raise
        self.access_token = data["accessToken"]
        self.entitlement = data["token"]
        self.puuid = data.get("subject") or self.puuid
        self._token_at = time.time()

    async def load_identity(self) -> None:
        with contextlib.suppress(Exception):
            s = await self.local_get("/chat/v1/session")
            self.puuid = s.get("puuid") or self.puuid
            self.game_name = s.get("game_name", "")
            self.game_tag = s.get("game_tag", "")

    async def detect_region(self) -> None:
        env_region = os.environ.get("VALO_REGION", "").lower()
        if env_region:
            self.region = env_region
            self.shard = os.environ.get("VALO_SHARD", "").lower() or SHARD_BY_REGION.get(
                env_region, env_region
            )
            return
        m = self._log_search(r"https://glz-([a-z\-]+)-1\.([a-z]+)\.a\.pvp\.net")
        if m and m.group(2) in SHARD_BY_REGION.values():
            self.region, self.shard = m.group(1), m.group(2)
            return
        with contextlib.suppress(Exception):
            rl = await self.local_get("/riotclient/region-locale")
            region, shard = normalize_region(str(rl.get("region", "")).lower())
            if region and shard:
                self.region, self.shard = region, shard
                return
            if region:
                LOG.warning("Il client dichiara la regione '%s', che Valorant non "
                            "usa. Serve il log del gioco per saperlo con certezza.",
                            region)
        raise BridgeError(
            "Regione non rilevata. Entra una volta nel menu di Valorant, oppure "
            "imposta le variabili d'ambiente VALO_REGION e VALO_SHARD."
        )

    async def redetect_region(self) -> bool:
        prima = (self.region, self.shard)
        try:
            await self.detect_region()
        except BridgeError:
            return False
        if (self.region, self.shard) == prima:
            return False
        LOG.info("Regione corretta: %s/%s invece di %s/%s",
                 self.region, self.shard, prima[0] or "?", prima[1] or "?")
        return True

    async def detect_version(self) -> None:
        env_v = os.environ.get("VALO_CLIENT_VERSION", "")
        if env_v:
            self.client_version = env_v
            return
        m = self._log_search(r"CI server version: ([\w\.\-]+)")
        if m:
            self.client_version = m.group(1)
            return
        with contextlib.suppress(Exception):
            async with self.session.get("https://valorant-api.com/v1/version") as r:
                d = await r.json()
                self.client_version = d["data"]["riotClientVersion"]
                return
        raise BridgeError("Versione client non rilevata. Avvia Valorant e riprova.")

    @staticmethod
    def _log_search(pattern: str) -> "re.Match[str] | None":
        if not SHOOTER_LOG.exists():
            return None
        try:
            text = SHOOTER_LOG.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return None
        found = list(re.finditer(pattern, text))
        return found[-1] if found else None


@dataclass
class State:

    bridge: str = "starting"
    error: str | None = None
    error_en: str | None = None
    henrik: bool = False
    henrik_key: str = ""
    mock: bool = False
    account: dict[str, Any] = field(default_factory=dict)
    live: dict[str, Any] = field(default_factory=dict)
    roster: dict[str, Any] = field(default_factory=dict)
    rank: dict[str, Any] = field(default_factory=dict)
    recent: dict[str, Any] = field(default_factory=dict)
    matches: list[dict[str, Any]] = field(default_factory=list)
    acts: list[dict[str, Any]] = field(default_factory=list)
    updated_at: float = 0.0

    def to_json(self) -> dict[str, Any]:
        return {
            "bridge": self.bridge,
            "error": self.error,
            "errorEn": self.error_en or self.error,
            "henrik": self.henrik,
            "henrikKey": self.henrik_key,
            "mock": self.mock,
            "account": self.account,
            "live": self.live,
            "roster": self.roster,
            "rank": self.rank,
            "recent": self.recent,
            "matches": self.matches,
            "acts": self.acts,
            "updatedAt": self.updated_at,
            "log": list(LOG_LINES),
        }


def tier_name(tier: int | None) -> str:
    if tier is None:
        return "—"
    if 0 <= tier < len(TIERS):
        return TIERS[tier]
    return f"Tier {tier}"


def map_name(map_id: str) -> str:
    if not map_id:
        return "—"
    return map_id.rstrip("/").rsplit("/", 1)[-1]


class Tracker:

    def __init__(self, riot: RiotClient, history_size: int = 10,
                 peek: int = PEEK_ACT, henrik: "Henrik | None" = None) -> None:
        self.riot = riot
        self.henrik = henrik or Henrik(riot.session)
        self.history_size = history_size
        self.peek = peek
        self.state = State()
        self.state.henrik = self.henrik.enabled
        self.state.henrik_key = self.henrik.key
        self.clients: set[web.WebSocketResponse] = set()
        self._agents: dict[str, str] = {}
        self._maps: dict[str, str] = {}
        self._seasons: dict[str, str] = {}
        self._episodes: dict[str, str] = {}
        self._active_seasons: set[str] = set()
        self._row_cache: dict[str, dict[str, Any]] = {}
        self._act_info: dict[str, dict[str, int]] = {}
        self._act_saved: dict[str, dict[str, int]] = {}
        self._last_loop_state = ""
        self._stats_lock = asyncio.Lock()
        self._presence_blind = False
        self._glz_at = 0.0
        self._names: dict[str, str] = {}
        self._tiers: dict[str, dict[str, Any]] = {}
        self._roster_match = ""
        self._roster_loop = ""
        self._roster_at = 0.0
        self._match_id = ""
        self._match_loop = ""
        self._match_at = 0.0
        self._last_match_id = ""
        self._pstats: dict[str, dict[str, Any]] = {}
        self._peeked: dict[str, dict[str, dict[str, Any]]] = {}
        self._peek_sem = asyncio.Semaphore(3)
        self._peek_cooldown = 0.0
        self._peek_429 = 0
        self._peek_task: asyncio.Task[None] | None = None


    async def push(self) -> None:
        self.state.updated_at = time.time()
        payload = json.dumps(self.state.to_json())
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_str(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    async def fail(self, message: str, en: str = "") -> None:
        LOG.error(message)
        self.state.bridge = "error"
        self.state.error = message
        self.state.error_en = en or tr_en(message)
        await self.push()


    async def load_content(self) -> None:
        with contextlib.suppress(Exception):
            async with self.riot.session.get(
                "https://valorant-api.com/v1/agents?isPlayableCharacter=true"
            ) as r:
                d = await r.json()
                self._agents = {a["uuid"].lower(): a["displayName"] for a in d["data"]}
        with contextlib.suppress(Exception):
            async with self.riot.session.get("https://valorant-api.com/v1/maps") as r:
                d = await r.json()
                for m in d["data"]:
                    if m.get("mapUrl"):
                        self._maps[m["mapUrl"].lower()] = m["displayName"]
        with contextlib.suppress(Exception):
            content = await self.riot.remote_get(
                f"{self.riot.shared}/content-service/v3/content"
            )
            episodio = ""
            for s in (content or {}).get("Seasons", []):
                sid = s["ID"].lower()
                self._seasons[sid] = s.get("Name", s["ID"])
                if s.get("IsActive"):
                    self._active_seasons.add(sid)
                if str(s.get("Type") or "").lower() == "episode":
                    episodio = s.get("Name", "")
                elif episodio:
                    self._episodes[sid] = episodio
        with contextlib.suppress(Exception):
            async with self.riot.session.get(
                "https://valorant-api.com/v1/seasons"
            ) as r:
                d = await r.json()
            names = {s["uuid"].lower(): s.get("displayName", "")
                     for s in d["data"]}
            for s in d["data"]:
                uid = s["uuid"].lower()
                if s.get("displayName"):
                    self._seasons.setdefault(uid, s["displayName"])
                parent = str(s.get("parentUuid") or "").lower()
                if parent and names.get(parent):
                    self._episodes[uid] = names[parent]


    @staticmethod
    def _read_row_file() -> dict[str, dict[str, Any]]:
        with contextlib.suppress(Exception):
            data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            versione = data.get("v")
            if versione == ROW_CACHE_VERSION:
                return data.get("accounts") or {}
            if versione == 2:
                return {p: {"rows": r, "acts": {}}
                        for p, r in (data.get("accounts") or {}).items()}
            if data.get("puuid"):
                return {data["puuid"]: {"rows": data.get("rows") or {},
                                        "acts": {}}}
        return {}

    def load_row_cache(self) -> None:
        with contextlib.suppress(Exception):
            mio = self._read_row_file().get(self.riot.puuid) or {}
            self._row_cache = mio.get("rows") or {}
            self._act_saved = mio.get("acts") or {}
            if self._row_cache:
                LOG.info("Cache partite: %d gia' analizzate", len(self._row_cache))

    def load_peek_cache(self) -> None:
        with contextlib.suppress(Exception):
            data = json.loads(PEEK_CACHE_FILE.read_text(encoding="utf-8"))
            if data.get("v") == CACHE_VERSION:
                self._peeked = data.get("matches") or {}
                LOG.info("Cache lobby: %d partite gia' lette", len(self._peeked))

    def _save_peek_cache(self) -> None:
        with contextlib.suppress(Exception):
            rows = self._peeked
            if len(rows) > PEEK_CACHE_MAX:
                rows = dict(list(rows.items())[-PEEK_CACHE_MAX:])
                self._peeked = rows
            PEEK_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            PEEK_CACHE_FILE.write_text(
                json.dumps({"v": CACHE_VERSION, "matches": rows}), encoding="utf-8")

    def _save_row_cache(self) -> None:
        with contextlib.suppress(Exception):
            if not self.riot.puuid:
                return
            tutti = self._read_row_file()
            mio = tutti.get(self.riot.puuid) or {}
            acts = dict(mio.get("acts") or {})
            acts.update(self._act_saved)
            tutti[self.riot.puuid] = {"rows": self._row_cache, "acts": acts}
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            CACHE_FILE.write_text(
                json.dumps({"v": ROW_CACHE_VERSION, "accounts": tutti}),
                encoding="utf-8")

    def map_label(self, path: str) -> str:
        if not path:
            return "—"
        return self._maps.get(path.lower().rstrip("/")) or map_name(path)

    def agent_name(self, uuid: str) -> str:
        return self._agents.get((uuid or "").lower(), "—")

    def season_name(self, uuid: str) -> str:
        key = (uuid or "").lower()
        act = self._seasons.get(key)
        if not act:
            return "act sconosciuto"
        episode = self._episodes.get(key)
        return f"{episode} // {act}" if episode else act


    @staticmethod
    def _season_info(mmr: dict[str, Any]) -> dict[str, dict[str, int]]:
        comp = ((mmr.get("QueueSkills") or {}).get("competitive")) or {}
        fuori: dict[str, dict[str, int]] = {}
        for sid, entry in (comp.get("SeasonalInfoBySeasonID") or {}).items():
            gradi = [int(entry.get("CompetitiveTier") or 0)]
            gradi += [int(k) for k in (entry.get("WinsByTier") or {})]
            fuori[sid.lower()] = {
                "peak": max(gradi),
                "games": int(entry.get("NumberOfGames") or 0),
                "wins": int(entry.get("NumberOfWinsWithPlacements")
                            or entry.get("NumberOfWins") or 0),
            }
        return fuori

    async def refresh_rank(self) -> None:
        mmr = await self.riot.remote_get(
            f"{self.riot.pd}/mmr/v1/players/{self.riot.puuid}"
        )
        if not mmr:
            return
        self._act_info = self._season_info(mmr)

        comp = (mmr.get("QueueSkills") or {}).get("competitive") or {}
        seasons = comp.get("SeasonalInfoBySeasonID") or {}

        read = self._read_mmr(mmr)
        current_tier, current_rr = read["tier"], read["rr"]
        peak_tier = read["peak"] or 0
        act_wins = act_games = 0

        current = None
        for sid, info in seasons.items():
            if sid.lower() in self._active_seasons:
                current = info
                break
        if current is None and seasons:
            current = max(seasons.values(), key=lambda i: i.get("NumberOfGames", 0))
        if current:
            act_wins = (current.get("NumberOfWinsWithPlacements")
                        or current.get("NumberOfWins", 0))
            act_games = current.get("NumberOfGames", 0)
            if current_tier in (None, 0):
                current_tier = current.get("CompetitiveTier") or current_tier
                current_rr = current.get("RankedRating") or current_rr

        self.state.rank = {
            "tier": current_tier,
            "tierName": tier_name(current_tier),
            "rr": current_rr,
            "peakTier": peak_tier or None,
            "peakTierName": tier_name(peak_tier) if peak_tier else "—",
            "peakSeason": read["peakAct"],
            "actWins": act_wins,
            "actGames": act_games,
            "actName": next((self.season_name(k) for k in seasons
                             if k.lower() in self._active_seasons), ""),
            "maxTier": len(TIERS) - 1,
        }


    async def competitive_history(self, puuid: str,
                                  limit: int | None = None) -> list[str]:
        ids: list[str] = []
        total = None
        while total is None or len(ids) < total:
            if limit and len(ids) >= limit:
                break
            lo = len(ids)
            try:
                page = await self.riot.remote_get(
                    f"{self.riot.pd}/match-history/v1/history/{puuid}"
                    f"?startIndex={lo}&endIndex={lo + 20}&queue=competitive"
                )
            except Exception as exc:
                LOG.debug("History di %s finita a %d (%s)",
                          puuid[:8], lo, short_error(exc))
                break
            entries = (page or {}).get("History") or []
            if not entries:
                break
            if total is None:
                total = (page or {}).get("Total") or len(entries)
            ids += [e["MatchID"] for e in entries if e.get("MatchID")]
            if len(ids) >= (total or 0) or len(ids) > 600:
                break
        return ids[:limit] if limit else ids

    async def refresh_matches(self) -> None:
        puuid = self.riot.puuid
        try:
            ids = await self.competitive_history(puuid)
        except Exception as exc:
            LOG.warning("Cronologia competitive non leggibile: %s", short_error(exc))
            return

        rr_by_match: dict[str, dict[str, Any]] = {}
        for lo in (0, 20):
            try:
                upd = await self.riot.remote_get(
                    f"{self.riot.pd}/mmr/v1/players/{puuid}/competitiveupdates"
                    f"?startIndex={lo}&endIndex={lo + 20}&queue=competitive"
                )
            except Exception as exc:
                LOG.debug("competitiveupdates finiti a %d (%s)", lo, short_error(exc))
                break
            voci = (upd or {}).get("Matches") or []
            if not voci:
                break
            for m in voci:
                delta = m.get("RankedRatingEarned")
                if delta is None:
                    delta = m.get("RankedRatingEarnedTotal")
                rr_by_match[m.get("MatchID", "")] = {
                    "delta": delta,
                    "tier": m.get("TierAfterUpdate"),
                    "rr": m.get("RankedRatingAfterUpdate"),
                }

        rows: list[dict[str, Any]] = []
        for match_id in ids:
            try:
                row = await self._match_row_cached(match_id, puuid)
            except Exception as exc:
                LOG.warning("Match %s non leggibile: %s", match_id[:8], exc)
                continue
            if not row:
                continue
            if row.get("seasonId", "") not in self._active_seasons:
                continue
            agg_rr = rr_by_match.get(match_id) or {}
            row["rrDelta"] = agg_rr.get("delta")
            if agg_rr.get("rr") is not None:
                row["tierAfter"] = agg_rr.get("tier")
                row["rrAfter"] = agg_rr.get("rr")
                salvata = self._row_cache.get(match_id)
                if salvata is not None:
                    salvata["tierAfter"] = agg_rr.get("tier")
                    salvata["rrAfter"] = agg_rr.get("rr")
            rows.append(row)

        merged = {r["matchId"]: r for r in rows}
        for match_id, row in self._row_cache.items():
            if (row.get("seasonId") in self._active_seasons
                    and not row.get("src") and match_id not in merged):
                merged[match_id] = row
        rows = sorted(merged.values(),
                      key=lambda r: r.get("startedAt") or 0, reverse=True)

        self._save_row_cache()
        self.state.matches = rows[:self.history_size]

        tutte = None
        if self.henrik.enabled:
            tutte = await self.henrik.lifetime(puuid, self.riot.region, size=1000)
        act_rows = (None if tutte is None else
                    [r for r in tutte if r["seasonId"] in self._active_seasons])

        info = {**self._act_saved, **self._act_info}
        if tutte:
            per_sigla = await self.henrik.mmr_by_act(puuid, self.riot.region)
            if per_sigla:
                sigla_a_id = {r["seasonShort"]: r["seasonId"]
                              for r in tutte if r.get("seasonShort")}
                for sigla, v in per_sigla.items():
                    sid = sigla_a_id.get(sigla)
                    if sid and sid not in info:
                        info[sid] = v
        campioni: list[tuple[str, int, int]] = [
            (str(r.get("seasonId") or ""), int(r["tierAfter"]), int(r["rrAfter"]))
            for r in self._row_cache.values()
            if r.get("rrAfter") is not None and r.get("tierAfter")
        ]
        if tutte:
            campioni += await self.henrik.rr_samples(puuid, self.riot.region) or []

        for r in (tutte or []):
            mid = r.get("matchId")
            if mid and mid not in self._row_cache:
                self._row_cache[mid] = {**r, "src": "arch"}

        self._act_saved = info
        self._save_row_cache()
        self.state.acts = self._by_act(tutte or [], rows, info, campioni)

        globale = self.state.rank.get("peakTier")
        for a in self.state.acts:
            if a["peakTier"] == globale and a.get("peakRR") is not None:
                self.state.rank["peakRR"] = a["peakRR"]
                break
        n_arch = len(act_rows or [])
        if act_rows:
            unione = {r["matchId"]: r for r in act_rows if r.get("matchId")}
            aggiunte = 0
            for r in rows:
                if r.get("matchId") and r["matchId"] not in unione:
                    unione[r["matchId"]] = r
                    aggiunte += 1
            self.state.recent = self._aggregate(list(unione.values()))
            self.state.recent["source"] = "archivio" if not aggiunte else "unione"
        else:
            self.state.recent = self._aggregate(rows, self.state.rank)
            self.state.recent["source"] = "riot"
        self.state.recent["actGames"] = self.state.rank.get("actGames") or 0

        LOG.info("Act in corso: %d da Riot, %d dall'archivio, medie su %d "
                 "(Riot ne dichiara %d)", len(rows), n_arch,
                 self.state.recent.get("games", 0),
                 self.state.recent["actGames"])

    async def _match_row_cached(self, match_id: str, puuid: str
                                ) -> dict[str, Any] | None:
        hit = self._row_cache.get(match_id)
        if hit is not None and not hit.get("src"):
            return dict(hit)
        row = await self._match_row(match_id, puuid)
        if row:
            self._row_cache[match_id] = row
        elif hit is not None:
            return dict(hit)
        return dict(row) if row else None

    async def _match_row(
        self, match_id: str, puuid: str
    ) -> dict[str, Any] | None:
        det = await self.riot.remote_get(
            f"{self.riot.pd}/match-details/v1/matches/{match_id}"
        )
        if not det:
            return None

        me = next(
            (p for p in det.get("players", []) if p.get("subject") == puuid), None
        )
        if not me:
            return None

        st = me.get("stats") or {}
        rounds = st.get("roundsPlayed") or 0
        kills = st.get("kills", 0)
        deaths = st.get("deaths", 0)
        assists = st.get("assists", 0)
        score = st.get("score", 0)

        head = body = leg = 0
        for rnd in det.get("roundResults", []):
            for ps in rnd.get("playerStats", []):
                if ps.get("subject") != puuid:
                    continue
                for dmg in ps.get("damage", []):
                    head += dmg.get("headshots", 0)
                    body += dmg.get("bodyshots", 0)
                    leg += dmg.get("legshots", 0)

        my_team = me.get("teamId")
        won = None
        my_score = their_score = None
        for team in det.get("teams", []):
            if team.get("teamId") == my_team:
                won = bool(team.get("won"))
                my_score = team.get("roundsWon")
            else:
                their_score = team.get("roundsWon")

        info = det.get("matchInfo") or {}
        return {
            "matchId": match_id,
            "seasonId": str(info.get("seasonId", "")).lower(),
            "map": self.map_label(info.get("mapId", "")),
            "agent": self.agent_name(me.get("characterId", "")),
            "kills": kills,
            "deaths": deaths,
            "assists": assists,
            "acs": round(score / rounds, 1) if rounds else 0.0,
            "combatScore": score,
            "rounds": rounds,
            "shots": {"head": head, "body": body, "leg": leg},
            "won": won,
            "score": [my_score, their_score],
            "startedAt": info.get("gameStartMillis"),
        }

    @staticmethod
    def _aggregate(rows: list[dict[str, Any]],
                   rank: dict[str, Any] | None = None) -> dict[str, Any]:
        if not rows:
            return {}
        k = sum(r["kills"] for r in rows)
        d = sum(r["deaths"] for r in rows)
        a = sum(r["assists"] for r in rows)
        rounds = sum(r["rounds"] for r in rows) or 1
        head = sum(r["shots"]["head"] for r in rows)
        shots = head + sum(r["shots"]["body"] + r["shots"]["leg"] for r in rows)
        wins = sum(1 for r in rows if r["won"] is True)
        decided = sum(1 for r in rows if r["won"] is not None) or 1
        combat = sum(r.get("combatScore", r["acs"] * r["rounds"]) for r in rows)

        by_agent: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            by_agent.setdefault(r["agent"], []).append(r)
        best_agent = ""
        best_kda = -1.0
        for agent, group in by_agent.items():
            if len(group) < 2:
                continue
            gk = sum(x["kills"] for x in group)
            ga = sum(x["assists"] for x in group)
            gd = sum(x["deaths"] for x in group) or 1
            kda = (gk + ga) / gd
            if kda > best_kda:
                best_agent, best_kda = agent, kda

        act_games = (rank or {}).get("actGames") or 0
        act_wins = (rank or {}).get("actWins") or 0
        if act_games and act_wins <= act_games:
            win_rate, shown_w, shown_l = (round(act_wins / act_games * 100),
                                          act_wins, act_games - act_wins)
        else:
            act_games = 0
            win_rate, shown_w, shown_l = (round(wins / decided * 100),
                                          wins, decided - wins)

        by_map: dict[str, dict[str, Any]] = {}
        for r in rows:
            m = by_map.setdefault(r.get("map") or "—", {
                "games": 0, "wins": 0, "losses": 0,
                "k": 0, "d": 0, "combat": 0, "rounds": 0,
                "head": 0, "shots": 0,
            })
            m["games"] += 1
            if r["won"] is True:
                m["wins"] += 1
            elif r["won"] is False:
                m["losses"] += 1
            m["k"] += r["kills"]
            m["d"] += r["deaths"]
            m["combat"] += r.get("combatScore", r["acs"] * r["rounds"])
            m["rounds"] += r["rounds"]
            colpi = r.get("shots") or {}
            m["head"] += colpi.get("head", 0)
            m["shots"] += (colpi.get("head", 0) + colpi.get("body", 0)
                           + colpi.get("leg", 0))

        maps = [{
            "map": name,
            "games": m["games"],
            "wins": m["wins"],
            "losses": m["losses"],
            "winRate": round(m["wins"] / (m["wins"] + m["losses"]) * 100)
                       if (m["wins"] + m["losses"]) else None,
            "kd": round(m["k"] / (m["d"] or 1), 2),
            "acs": round(m["combat"] / m["rounds"]) if m["rounds"] else None,
            "hs": round(m["head"] / m["shots"] * 100, 1) if m["shots"] else None,
        } for name, m in by_map.items()]
        maps.sort(key=lambda x: (-(x["winRate"] or 0), -x["games"], x["map"]))

        return {
            "games": len(rows),
            "actGames": act_games,
            "maps": maps,
            "kills": k,
            "deaths": d,
            "assists": a,
            "kd": round(k / (d or 1), 2),
            "kda": round((k + a) / (d or 1), 2),
            "acs": round(combat / rounds, 1),
            "hs": round(head / shots * 100, 1) if shots else 0.0,
            "winRate": win_rate,
            "wins": shown_w,
            "losses": shown_l,
            "killsPerRound": round(k / rounds, 2),
            "bestAgent": best_agent,
            "bestAgentKda": round(best_kda, 2) if best_agent else None,
        }

    @staticmethod
    def _peak_rr(sid: str, picco: int,
                 campioni: list[tuple[str, int, int]]) -> int | None:
        if picco < 24:
            return None
        valori = [rr for s, t, rr in campioni if s == sid and t == picco]
        return max(valori) if valori else None

    def _by_act(self, esterne: list[dict[str, Any]], locali: list[dict[str, Any]],
                info: dict[str, dict[str, int]],
                campioni: list[tuple[str, int, int]]) -> list[dict[str, Any]]:
        per: dict[str, dict[str, dict[str, Any]]] = {}
        for r in (*esterne, *locali, *self._row_cache.values()):
            sid = str(r.get("seasonId") or "").lower()
            if sid and r.get("matchId"):
                per.setdefault(sid, {})[r["matchId"]] = r

        fuori: list[dict[str, Any]] = []
        for sid, righe in per.items():
            dati = info.get(sid) or {}
            agg = self._aggregate(list(righe.values()),
                                  {"actGames": dati.get("games") or 0,
                                   "actWins": dati.get("wins") or 0})
            if not agg.get("games"):
                continue
            picco = dati.get("peak") or 0
            fuori.append({
                "season": sid,
                "name": self.season_name(sid),
                "at": max((x.get("startedAt") or 0) for x in righe.values()),
                "peakTier": picco or None,
                "peakTierName": tier_name(picco) if picco else "—",
                "peakRR": self._peak_rr(sid, picco, campioni),
                **{k: agg[k] for k in ("games", "actGames", "wins", "losses",
                                       "winRate", "kd", "kda", "acs", "hs",
                                       "bestAgent")},
            })
        fuori.sort(key=lambda a: a["at"], reverse=True)
        return fuori

    async def resync_identity(self) -> bool:
        old = self.riot.puuid
        self.riot.lock = Lockfile.read()
        await self.riot.refresh_tokens()
        await self.riot.load_identity()
        if not self.riot.puuid or self.riot.puuid == old:
            return False

        LOG.info("Account cambiato: ora sei %s#%s",
                 self.riot.game_name, self.riot.game_tag)
        await self.riot.detect_region()
        self.state.account = {
            "name": self.riot.game_name,
            "tag": self.riot.game_tag,
            "region": self.riot.region,
        }
        self._row_cache.clear()
        self.forget_roster()
        self.state.matches = []
        self.state.recent = {}
        self.state.rank = {}
        self._last_loop_state = ""
        self._match_at = 0.0
        self._presence_blind = False
        self.load_row_cache()
        return True

    async def refresh_stats(self, reason: str = "") -> None:
        if self._stats_lock.locked():
            return
        async with self._stats_lock:
            if reason:
                LOG.info("Aggiorno statistiche (%s)", reason)
            else:
                LOG.info("Aggiorno statistiche")
            with contextlib.suppress(Exception):
                if await self.resync_identity():
                    self.state.bridge = "connected"
                    self.state.error = None
                    await self.push()
            for tentativo in (1, 2):
                try:
                    await self.refresh_rank()
                    await self.refresh_matches()
                    self.state.error = None
                    break
                except Exception as exc:
                    if tentativo == 1 and await self.riot.redetect_region():
                        self.state.account["region"] = self.riot.region
                        continue
                    LOG.warning("Aggiornamento statistiche fallito: %s", exc)
                    self.state.error = f"Statistiche non aggiornate: {exc}"
                    self.state.error_en = f"Stats not refreshed: {exc}"
                    break
            await self.push()
            with contextlib.suppress(Exception):
                await self.refresh_roster(force=True)


    def _apply_presence(self, private_b64: str) -> bool:
        try:
            pad = "=" * (-len(private_b64) % 4)
            data = json.loads(base64.b64decode(private_b64 + pad))
        except Exception:
            return False

        loop = data.get("sessionLoopState", "")
        if not loop:
            if not self._presence_blind:
                LOG.info(
                    "La presenza non contiene sessionLoopState. Passo agli endpoint "
                    "sul mio puuid per capire se sono in partita."
                )
                self._presence_blind = True
            return False
        self._presence_blind = False
        queue = data.get("queueId", "")
        ally = data.get("partyOwnerMatchScoreAllyTeam")
        enemy = data.get("partyOwnerMatchScoreEnemyTeam")

        self.state.live = {
            "loopState": loop,
            "loopLabel": STATE_LABELS.get(loop, loop or "—"),
            "queue": QUEUE_LABELS.get(queue, queue or "—"),
            "map": self.map_label(data.get("matchMap", "")),
            "partySize": data.get("partySize"),
            "provisioning": data.get("provisioningFlow", ""),
            "score": [ally, enemy] if loop == "INGAME" else None,
            "roundsPlayed": (ally or 0) + (enemy or 0) if loop == "INGAME" else None,
        }

        changed = loop != self._last_loop_state
        if changed:
            LOG.info("Stato partita: %s -> %s", self._last_loop_state or "?", loop)
            if loop == "MENUS" and self._last_loop_state in ("INGAME", "PREGAME"):
                self.forget_roster()
                asyncio.create_task(self._refresh_after_match())
        self._last_loop_state = loop
        return changed

    async def _refresh_after_match(self) -> None:
        await asyncio.sleep(6)
        await self.refresh_stats("fine partita")

    async def _read_presence_once(self) -> str:
        data = await self.riot.local_get("/chat/v4/presences")
        for p in data.get("presences", []):
            if p.get("puuid") != self.riot.puuid:
                continue
            if str(p.get("product", "")).lower() != "valorant":
                continue
            if self._apply_presence(p.get("private", "")):
                await self.push()
            return "ok"
        return "assente"

    async def current_match_id(self, max_age: float = 3.0) -> tuple[str, str]:
        if time.time() - self._match_at < max_age:
            return self._match_loop, self._match_id

        puuid = self.riot.puuid
        loop, match_id = "MENUS", ""
        pre = await self.riot.remote_get(f"{self.riot.glz}/pregame/v1/players/{puuid}")
        if pre:
            loop, match_id = "PREGAME", pre.get("MatchID", "")
        else:
            core = await self.riot.remote_get(
                f"{self.riot.glz}/core-game/v1/players/{puuid}")
            if core:
                loop, match_id = "INGAME", core.get("MatchID", "")

        self._match_loop, self._match_id = loop, match_id
        self._match_at = time.time()
        return loop, match_id

    async def detect_state_remote(self) -> None:
        self._glz_at = time.time()
        try:
            loop, match_id = await self.current_match_id()
        except Exception as exc:
            LOG.debug("Fallback stato non riuscito: %s", short_error(exc))
            return

        if loop == self._last_loop_state and match_id == self._last_match_id:
            return

        if loop != self._last_loop_state:
            LOG.info("Stato partita: %s -> %s (via endpoint proprio)",
                     self._last_loop_state or "?", loop)
        elif match_id:
            LOG.info("Partita nuova senza passare dai menu: %s", match_id[:8])
            self.forget_roster()

        was = self._last_loop_state
        self._last_loop_state = loop
        self._last_match_id = match_id
        self.state.live = {
            "loopState": loop,
            "loopLabel": STATE_LABELS.get(loop, loop),
            "queue": "—",
            "map": "—",
            "partySize": None,
            "provisioning": "",
            "score": None,
            "roundsPlayed": None,
            "scoreUnavailable": loop == "INGAME",
        }
        if loop == "MENUS":
            self.forget_roster()
        await self.push()
        if loop == "MENUS" and was in ("INGAME", "PREGAME"):
            asyncio.create_task(self._refresh_after_match())


    def forget_roster(self) -> bool:
        had = bool(self.state.roster)
        self.state.roster = {}
        self._roster_match = ""
        self._tiers.clear()
        self._pstats.clear()
        self._peeked.clear()
        self._roster_loop = ""
        if self._peek_task and not self._peek_task.done():
            self._peek_task.cancel()
        self._peek_task = None
        return had

    async def refresh_roster(self, force: bool = False) -> None:
        self._roster_at = time.time()
        if force:
            self._match_at = 0.0
        try:
            loop, match_id = await self.current_match_id()
        except Exception as exc:
            LOG.debug("Roster: stato non leggibile (%s)", short_error(exc))
            return

        if loop == "MENUS" or not match_id:
            if self.forget_roster():
                await self.push()
            return
        if (not force and loop == "INGAME" and match_id == self._roster_match
                and self._roster_loop == "INGAME"):
            return

        try:
            found = (await self._pregame_roster(match_id) if loop == "PREGAME"
                     else await self._coregame_roster(match_id))
        except Exception as exc:
            LOG.debug("Roster non leggibile: %s", short_error(exc))
            return
        if not found:
            return
        players, meta = found

        if match_id != self._roster_match:
            self._tiers.clear()
            self._pstats.clear()
            if self._peek_task and not self._peek_task.done():
                self._peek_task.cancel()
            self._peek_task = None
        await self._decorate(players)

        allies = [p for p in players if p["ally"]]
        enemies = [p for p in players if not p["ally"]]
        rank_key = lambda p: (not p["me"], -(p["tier"] or 0), p["agent"])
        self.state.roster = {
            "matchId": match_id,
            "loop": loop,
            "allies": sorted(allies, key=rank_key),
            "enemies": sorted(enemies, key=rank_key),
            **meta,
        }
        if (match_id, loop) != (self._roster_match, self._roster_loop):
            LOG.info("Roster partita %s (%s): %d in squadra, %d avversari",
                     match_id[:8], loop.lower(), len(allies), len(enemies))
        self._roster_match, self._roster_loop = match_id, loop

        for key in ("map", "queue"):
            if meta.get(key) and self.state.live.get(key) in (None, "", "—"):
                self.state.live[key] = meta[key]
        await self.push()

        if self.peek != 0 and any(p["puuid"] not in self._pstats for p in players):
            if self._peek_task is None or self._peek_task.done():
                self._peek_task = asyncio.create_task(
                    self._fill_stats([p["puuid"] for p in players]))

    async def _coregame_roster(self, match_id: str):
        det = await self.riot.remote_get(
            f"{self.riot.glz}/core-game/v1/matches/{match_id}")
        if not det:
            return None
        rows = det.get("Players") or []
        my_team = next((p.get("TeamID") for p in rows
                        if p.get("Subject") == self.riot.puuid), "")
        players = [self._player_row(p, p.get("TeamID") == my_team, True)
                   for p in rows if not p.get("IsCoach")]
        queue = (det.get("MatchmakingData") or {}).get("QueueID") or ""
        punteggio = (self.state.live or {}).get("score") or []
        giocati = sum(x for x in punteggio if isinstance(x, int)) if punteggio else None
        return players, {
            "map": self.map_label(det.get("MapID", "")),
            "queue": QUEUE_LABELS.get(queue, queue or "—"),
            "queueId": queue,
            "ffa": queue in FFA_QUEUES,
            "side": "" if queue in FFA_QUEUES else side_label(my_team, giocati),
            "enemiesHidden": False,
        }

    async def _pregame_roster(self, match_id: str):
        det = await self.riot.remote_get(
            f"{self.riot.glz}/pregame/v1/matches/{match_id}")
        if not det:
            return None
        rows = (det.get("AllyTeam") or {}).get("Players") or []
        players = [
            self._player_row(
                p, True,
                str(p.get("CharacterSelectionState", "")).lower() == "locked")
            for p in rows if not p.get("IsCoach")
        ]
        queue = det.get("QueueID") or ""
        ffa = queue in FFA_QUEUES
        return players, {
            "map": self.map_label(det.get("MapID", "")),
            "queue": QUEUE_LABELS.get(queue, queue or "—"),
            "queueId": queue,
            "ffa": ffa,
            "side": "" if ffa else side_label(
                (det.get("AllyTeam") or {}).get("TeamID", ""), None),
            "enemiesHidden": not ffa,
        }


    def _player_row(self, p: dict[str, Any], ally: bool, locked: bool) -> dict[str, Any]:
        ident = p.get("PlayerIdentity") or {}
        puuid = p.get("Subject", "")
        return {
            "puuid": puuid,
            "me": puuid == self.riot.puuid,
            "ally": ally,
            "agent": self.agent_name(p.get("CharacterID", "")),
            "locked": locked,
            "incognito": bool(ident.get("Incognito")),
            "level": None if ident.get("HideAccountLevel") else ident.get("AccountLevel"),
            "name": "",
            "tier": None,
            "tierName": "—",
            "rr": None,
            "stale": False,
            "peakTier": None,
            "peakTierName": "—",
            "peakAct": "",
            "stats": None,
        }

    async def _decorate(self, players: list[dict[str, Any]]) -> None:
        with contextlib.suppress(Exception):
            await self._load_names([p["puuid"] for p in players])
        for p in players:
            p["name"] = "" if p["incognito"] else self._names.get(p["puuid"], "")

        missing = [p["puuid"] for p in players
                   if p["puuid"] and p["puuid"] not in self._tiers]
        if missing:
            await asyncio.gather(*(self._load_tier(u) for u in missing))
        for p in players:
            info = self._tiers.get(p["puuid"]) or {}
            tier = info.get("tier")
            p["tier"] = tier
            p["tierName"] = tier_name(tier) if tier is not None else "—"
            p["rr"] = info.get("rr")
            p["stale"] = bool(info) and not info.get("current", True)
            peak = info.get("peak")
            p["peakTier"] = peak
            p["peakTierName"] = tier_name(peak) if peak else "—"
            p["peakAct"] = info.get("peakAct", "")
            p["stats"] = self._pstats.get(p["puuid"]) if self.peek else {}

    async def _load_names(self, puuids: list[str]) -> None:
        todo = sorted({u for u in puuids if u and u not in self._names})
        if not todo:
            return
        data = await self.riot.remote_put(
            f"{self.riot.pd}/name-service/v2/players", todo)
        for entry in data or []:
            name = entry.get("GameName") or ""
            tag = entry.get("TagLine") or ""
            if name:
                self._names[entry.get("Subject", "")] = f"{name}#{tag}" if tag else name


    async def _fill_stats(self, puuids: list[str]) -> None:
        todo = [u for u in puuids if u and u not in self._pstats]
        if not todo:
            return
        started = time.time()
        try:
            await asyncio.gather(*(self._load_stats(u) for u in todo))
        except asyncio.CancelledError:
            self._save_peek_cache()
            raise
        except Exception as exc:
            LOG.debug("Medie interrotte: %s", short_error(exc))
            return
        done = sum(1 for u in todo if self._pstats.get(u))
        games = sum((self._pstats.get(u) or {}).get("games", 0) for u in todo)
        LOG.info("Medie: %d giocatori su %d in %.0fs (%d partite considerate, "
                 "%d in cache, %d frenate da Riot)", done, len(todo),
                 time.time() - started, games, len(self._peeked), self._peek_429)
        self._save_peek_cache()

    async def _load_stats(self, puuid: str) -> None:
        stats: dict[str, Any] = {}
        if self.henrik.enabled:
            rows = await self.henrik.act_rows(
                puuid, self.riot.region, self._active_seasons)
            if rows is not None:
                self._pstats[puuid] = self._player_average(rows)
                await self._apply_stats()
                return
        try:
            if self.peek == PEEK_ACT:
                wanted = (self._tiers.get(puuid) or {}).get("actGames") or 0
                ids = await self.competitive_history(
                    puuid, limit=(wanted + 3) if wanted else 60)
            else:
                ids = await self.competitive_history(puuid, limit=self.peek)

            seen = await asyncio.gather(
                *(self._peek_match_details(i) for i in ids),
                return_exceptions=True)
            rows = [r[puuid] for r in seen
                    if isinstance(r, dict) and puuid in r
                    and (self.peek != PEEK_ACT
                         or r.get("_season") in self._active_seasons)]
            stats = self._player_average(rows)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            LOG.debug("Medie di %s non leggibili: %s", puuid[:8], short_error(exc))
        self._pstats[puuid] = stats
        self._save_peek_cache()
        await self._apply_stats()

    async def _peek_match_details(self, match_id: str) -> dict[str, dict[str, Any]]:
        if match_id in self._peeked:
            return self._peeked[match_id]
        async with self._peek_sem:
            if match_id in self._peeked:
                return self._peeked[match_id]
            det = None
            for attempt in range(4):
                now = time.time()
                if now < self._peek_cooldown:
                    await asyncio.sleep(self._peek_cooldown - now)
                try:
                    det = await self.riot.remote_get(
                        f"{self.riot.pd}/match-details/v1/matches/{match_id}")
                    break
                except asyncio.CancelledError:
                    raise
                except aiohttp.ClientResponseError as exc:
                    if exc.status != 429 or attempt == 3:
                        LOG.debug("Partita %s non letta: %s",
                                  match_id[:8], short_error(exc))
                        return {}
                    pause = 2.0 * (attempt + 1)
                    with contextlib.suppress(Exception):
                        pause = float((exc.headers or {}).get("Retry-After") or pause)
                    pause = min(max(pause, 1.0), 30.0)
                    self._peek_cooldown = max(self._peek_cooldown, time.time() + pause)
                    self._peek_429 += 1
                except Exception as exc:
                    LOG.debug("Partita %s non letta: %s",
                              match_id[:8], short_error(exc))
                    return {}
            if det is None:
                return {}
            teams = {t.get("teamId"): t for t in (det or {}).get("teams", [])}
            info = (det or {}).get("matchInfo") or {}
            rows: dict[str, Any] = {
                "_season": str(info.get("seasonId", "")).lower(),
            }
            for p in (det or {}).get("players", []):
                st = p.get("stats") or {}
                team = teams.get(p.get("teamId")) or {}
                rows[p.get("subject", "")] = {
                    "kills": st.get("kills", 0),
                    "deaths": st.get("deaths", 0),
                    "assists": st.get("assists", 0),
                    "score": st.get("score", 0),
                    "rounds": st.get("roundsPlayed", 0),
                    "won": team.get("won"),
                }
            self._peeked[match_id] = rows
            return rows

    @staticmethod
    def _player_average(rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {}
        k = sum(r["kills"] for r in rows)
        d = sum(r["deaths"] for r in rows)
        a = sum(r["assists"] for r in rows)
        rounds = sum(r["rounds"] for r in rows)
        decided = [r for r in rows if r["won"] is not None]
        wins = sum(1 for r in decided if r["won"])
        shots = [r.get("shots") or {} for r in rows]
        head = sum(s.get("head", 0) for s in shots)
        aimed = head + sum(s.get("body", 0) + s.get("leg", 0) for s in shots)
        return {
            "games": len(rows),
            "hs": round(head / aimed * 100, 1) if aimed else None,
            "kda": round((k + a) / (d or 1), 2),
            "kd": round(k / (d or 1), 2),
            "acs": round(sum(r["score"] for r in rows) / rounds) if rounds else None,
            "winRate": round(wins / len(decided) * 100) if decided else None,
        }

    async def _apply_stats(self) -> None:
        touched = False
        for side in ("allies", "enemies"):
            for row in self.state.roster.get(side, []):
                fresh = self._pstats.get(row.get("puuid", ""))
                if fresh is not None and row.get("stats") != fresh:
                    row["stats"] = fresh
                    touched = True
        if touched:
            await self.push()

    async def _load_tier(self, puuid: str) -> None:
        info: dict[str, Any] = {}
        try:
            mmr = await self.riot.remote_get(
                f"{self.riot.pd}/mmr/v1/players/{puuid}")
            if mmr:
                info = self._read_mmr(mmr)
        except Exception as exc:
            LOG.debug("Rank di %s non leggibile: %s", puuid[:8], short_error(exc))
        self._tiers[puuid] = info

    def _read_mmr(self, mmr: dict[str, Any]) -> dict[str, Any]:
        comp = ((mmr.get("QueueSkills") or {}).get("competitive")) or {}
        seasons = comp.get("SeasonalInfoBySeasonID") or {}

        latest = mmr.get("LatestCompetitiveUpdate") or {}
        tier = latest.get("TierAfterUpdate")
        rr = latest.get("RankedRatingAfterUpdate")
        current = str(latest.get("SeasonID", "")).lower() in self._active_seasons

        if not tier:
            for sid, entry in seasons.items():
                if sid.lower() in self._active_seasons and entry.get("CompetitiveTier"):
                    tier = entry.get("CompetitiveTier")
                    rr = entry.get("RankedRating")
                    current = True
                    break

        peak, peak_sid = 0, ""
        for sid, entry in seasons.items():
            wins_by_tier = entry.get("WinsByTier") or {}
            best = max([int(entry.get("CompetitiveTier") or 0)]
                       + [int(k) for k in wins_by_tier])
            if best > peak:
                peak, peak_sid = best, sid

        act_games = sum(e.get("NumberOfGames", 0) for sid, e in seasons.items()
                        if sid.lower() in self._active_seasons
                        and sid.lower() in self._episodes)

        return {
            "tier": tier,
            "rr": rr,
            "current": current,
            "peak": peak or None,
            "peakAct": self.season_name(peak_sid) if peak_sid else "",
            "actGames": act_games,
        }


    def _ws_variants(self) -> list[dict[str, Any]]:
        assert self.riot.lock is not None
        lk = self.riot.lock
        scheme = "wss" if lk.protocol.lower() == "https" else "ws"
        hdr = {"Authorization": lk.basic_auth}
        base = f"{scheme}://127.0.0.1:{lk.port}"
        return [
            {"name": "wamp", "url": base + "/",
             "kw": {"headers": hdr, "protocols": ("wamp",)}},
            {"name": "nessun subprotocollo", "url": base + "/",
             "kw": {"headers": hdr}},
            {"name": "wamp.2.json", "url": base + "/",
             "kw": {"headers": hdr, "protocols": ("wamp.2.json",)}},
            {"name": "senza slash", "url": base,
             "kw": {"headers": hdr}},
        ]

    async def probe_websocket(self) -> dict[str, Any] | None:
        for v in self._ws_variants():
            try:
                async with self.riot.session.ws_connect(
                    v["url"], ssl=self.riot._local_ssl, timeout=6, **v["kw"]
                ) as ws:
                    await ws.send_str('[5, "OnJsonApiEvent_chat_v4_presences"]')
                    LOG.info("Websocket: variante '%s' accettata", v["name"])
                    return v
            except aiohttp.WSServerHandshakeError as exc:
                LOG.debug("Websocket '%s' -> http %s", v["name"], exc.status)
            except Exception as exc:
                LOG.debug("Websocket '%s' -> %s", v["name"], exc)
        return None


    async def poll_presence(self, interval: float) -> None:
        misses = 0
        absent = 0
        seen_once = False

        async def go_idle(why: str, detail: str = "") -> None:
            if self.state.bridge != "waiting_game":
                if detail:
                    LOG.info("%s (%s). Resto in attesa.", why, detail)
                else:
                    LOG.info("%s Resto in attesa.", why)
                self.state.bridge = "waiting_game"
                self._last_loop_state = ""
                self.state.live = {}
                self.forget_roster()
                await self.push()

        while True:
            try:
                result = await self._read_presence_once()
                misses = 0
                if result == "ok":
                    absent = 0
                    if self._presence_blind and time.time() - self._glz_at > 5:
                        await self.detect_state_remote()
                    if (self._last_loop_state in ("INGAME", "PREGAME")
                            and time.time() - self._roster_at > 5):
                        await self.refresh_roster()
                    if not seen_once:
                        seen_once = True
                        LOG.info("Presenza Valorant agganciata.")
                    if self.state.bridge != "connected":
                        self.state.bridge = "connected"
                        await self.push()
                else:
                    absent += 1
                    if absent == 3:
                        await go_idle("Il Riot Client risponde ma Valorant non e' in presenza.")
            except Exception as exc:
                misses += 1
                absent = 0
                if misses == 3:
                    await go_idle("Client non raggiungibile", short_error(exc))
                if misses >= 3 and misses % 5 == 0:
                    with contextlib.suppress(Exception):
                        if await self.resync_identity():
                            self.state.bridge = "connected"
                            self.state.error = None
                            await self.push()
                            await self.refresh_stats("cambio account")
                            misses = 0
            slow = misses >= 3 or absent >= 3
            await asyncio.sleep(5.0 if slow else interval)


    async def watch_ws(self, variant: dict[str, Any]) -> None:
        quiet = False
        while True:
            try:
                async with self.riot.session.ws_connect(
                    variant["url"], ssl=self.riot._local_ssl, heartbeat=30,
                    **variant["kw"]
                ) as ws:
                    await ws.send_str('[5, "OnJsonApiEvent_chat_v4_presences"]')
                    quiet = False
                    LOG.info("In ascolto sulle presenze")
                    async for msg in ws:
                        if msg.type != aiohttp.WSMsgType.TEXT or not msg.data.strip():
                            continue
                        try:
                            frame = json.loads(msg.data)
                        except json.JSONDecodeError:
                            continue
                        if not (isinstance(frame, list) and len(frame) >= 3):
                            continue
                        payload = frame[2] or {}
                        for pr in (payload.get("data") or {}).get("presences", []):
                            if pr.get("puuid") != self.riot.puuid:
                                continue
                            if pr.get("product") != "valorant":
                                continue
                            self._apply_presence(pr.get("private", ""))
                            await self.push()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if not quiet:
                    LOG.info("Websocket chiuso (%s). Riprovo in sottofondo.", short_error(exc))
                    quiet = True
                await asyncio.sleep(5)

    async def watch_state(self) -> None:
        variant = await self.probe_websocket()
        if variant is None:
            LOG.warning(
                "Nessuna variante websocket accettata da questo client "
                "(build %s). Uso il polling ogni 2s: funziona, con al massimo "
                "2 secondi di ritardo sul cambio di stato.", self.riot.client_version,
            )
            await self.poll_presence(2.0)
        else:
            await asyncio.gather(
                self.watch_ws(variant),
                self.poll_presence(15.0),
            )

    async def watch_log(self) -> None:
        seen = -1
        while True:
            await asyncio.sleep(2)
            if len(LOG_LINES) != seen and self.clients:
                seen = len(LOG_LINES)
                await self.push()

    async def periodic_refresh(self) -> None:
        while True:
            await asyncio.sleep(180)
            if self._last_loop_state in ("MENUS", "", "AWAY"):
                await self.refresh_stats("periodico")


def mock_state() -> State:
    agents = ["Jett", "Reyna", "Omen", "Sova", "Killjoy", "Chamber"]
    maps = ["Ascent", "Haven", "Lotus", "Split", "Sunset", "Abyss"]
    rows = []
    rng = random.Random(7)
    for i in range(10):
        k, d, a = rng.randint(9, 27), rng.randint(8, 21), rng.randint(2, 9)
        won = rng.random() > 0.45
        rows.append({
            "matchId": f"mock-{i}",
            "map": rng.choice(maps),
            "agent": rng.choice(agents),
            "kills": k, "deaths": d, "assists": a,
            "acs": round(rng.uniform(160, 310), 1),
            "rounds": rng.randint(16, 25),
            "shots": {"head": rng.randint(20, 45),
                      "body": rng.randint(70, 130),
                      "leg": rng.randint(3, 14)},
            "won": won,
            "score": [13, rng.randint(4, 11)] if won else [rng.randint(4, 11), 13],
            "startedAt": int((time.time() - i * 5400) * 1000),
            "rrDelta": rng.randint(12, 26) if won else -rng.randint(10, 22),
        })
    s = State(bridge="connected", mock=True)
    s.account = {"name": "Esempio", "tag": "EUW", "region": "eu"}
    s.live = {
        "loopState": "INGAME", "loopLabel": "In partita", "queue": "Competitive",
        "map": "Ascent", "partySize": 2, "provisioning": "Matchmaking",
        "score": [8, 5], "roundsPlayed": 13,
    }
    def mock_player(name, agent, ally, tier, me=False):
        peak = min(tier + rng.randint(0, 4), 27)
        return {
            "puuid": f"mock-{name}", "me": me, "ally": ally, "agent": agent,
            "locked": True, "incognito": False, "level": rng.randint(40, 380),
            "name": name, "tier": tier, "tierName": tier_name(tier),
            "rr": rng.randint(0, 99), "stale": False,
            "peakTier": peak, "peakTierName": tier_name(peak),
            "peakAct": rng.choice(["V26 // ACT II", "V25 // ACT VI",
                                   "EPISODE 9 // ACT III"]),
            "stats": {
                "games": 3,
                "kda": round(rng.uniform(0.8, 2.1), 2),
                "kd": round(rng.uniform(0.7, 1.6), 2),
                "acs": rng.randint(150, 320),
                "hs": round(rng.uniform(15, 38), 1),
                "winRate": rng.choice([0, 33, 50, 67, 100]),
            },
        }

    s.roster = {
        "matchId": "mock-live", "loop": "INGAME",
        "map": "Ascent", "queue": "Competitive", "queueId": "competitive",
        "ffa": False, "enemiesHidden": False, "side": "attacco",
        "allies": [
            mock_player("Esempio#EUW", "Jett", True, 19, me=True),
            mock_player("Vetta#IT1", "Omen", True, 24),
            mock_player("Corvo#900", "Killjoy", True, 19),
            mock_player("Nadir#EUW", "Sova", True, 18),
            mock_player("Brina#TAG", "Sage", True, 17),
        ],
        "enemies": [
            mock_player("Aster#EUW", "Raze", False, 25),
            mock_player("Kobal#77", "Viper", False, 19),
            mock_player("Sirio#IT2", "Chamber", False, 19),
            mock_player("Talpa#EUW", "Skye", False, 18),
            mock_player("Zenit#123", "Cypher", False, 16),
        ],
    }
    s.rank = {
        "tier": 19, "tierName": "Diamond 2", "rr": 62,
        "peakTier": 22, "peakTierName": "Ascendant 2", "peakSeason": "Episodio 7 // Act 3",
        "actWins": 34, "actGames": 61, "maxTier": 27,
    }
    s.matches = rows
    s.recent = Tracker._aggregate(rows)
    s.updated_at = time.time()
    return s


def build_app(tracker: Tracker,
              stop: asyncio.Event | None = None) -> web.Application:
    app = web.Application()

    async def index(_: web.Request) -> web.StreamResponse:
        page = find_index()
        if page is None:
            return web.Response(
                text=MISSING_PAGE.format(a=WEB_DIR / "index.html", b=HERE / "index.html"),
                content_type="text/html",
                status=503,
            )
        resp = web.FileResponse(page)
        resp.headers["Cache-Control"] = "no-store"
        return resp

    async def api_state(_: web.Request) -> web.StreamResponse:
        return web.json_response(tracker.state.to_json())

    async def api_refresh(_: web.Request) -> web.StreamResponse:
        asyncio.create_task(tracker.refresh_stats("richiesta manuale"))
        return web.json_response({"ok": True})

    async def ws_handler(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=25)
        await ws.prepare(request)
        tracker.clients.add(ws)
        LOG.info("Dashboard collegato (%d attivi)", len(tracker.clients))
        try:
            await ws.send_str(json.dumps(tracker.state.to_json()))
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT and msg.data == "refresh":
                    asyncio.create_task(tracker.refresh_stats("dal dashboard"))
        finally:
            tracker.clients.discard(ws)
            LOG.info("Dashboard scollegato (%d attivi)", len(tracker.clients))
        return ws

    async def api_henrik_key(request: web.Request) -> web.StreamResponse:
        with contextlib.suppress(Exception):
            body = await request.json()
            why = await tracker.henrik.adopt(
                str(body.get("key") or ""), tracker.riot.region, tracker.riot.puuid)
            if why in ("", "nuovo"):
                tracker.state.henrik = True
                tracker.state.henrik_key = tracker.henrik.key
                asyncio.create_task(tracker.refresh_stats("chiave nuova"))
                return web.json_response({"ok": True, "note": why})
            return web.json_response({"ok": False, "why": why,
                                      "whyEn": tr_en(why)}, status=400)
        return web.json_response({"ok": False, "why": "richiesta illeggibile",
                                  "whyEn": "unreadable request"}, status=400)

    async def api_quit(_: web.Request) -> web.StreamResponse:
        LOG.info("Chiusura richiesta dal dashboard.")
        if stop is not None:
            asyncio.get_running_loop().call_later(0.3, stop.set)
        return web.json_response({"ok": True})

    app.router.add_post("/api/quit", api_quit)
    app.router.add_post("/api/henrik-key", api_henrik_key)
    app.router.add_get("/", index)
    app.router.add_get("/api/state", api_state)
    app.router.add_post("/api/refresh", api_refresh)
    app.router.add_get("/ws", ws_handler)
    if WEB_DIR.is_dir():
        app.router.add_static("/static", WEB_DIR)
    return app


async def is_our_bridge(session: aiohttp.ClientSession, url: str) -> bool:
    with contextlib.suppress(Exception):
        async with session.get(f"{url}/api/state", timeout=
                               aiohttp.ClientTimeout(total=2)) as r:
            return "bridge" in (await r.json(content_type=None))
    return False


def write_instance_lock(port: int) -> None:
    with contextlib.suppress(Exception):
        INSTANCE_LOCK.parent.mkdir(parents=True, exist_ok=True)
        INSTANCE_LOCK.write_text(json.dumps({"port": port, "pid": os.getpid()}),
                                 encoding="utf-8")


def clear_instance_lock(port: int) -> None:
    with contextlib.suppress(Exception):
        dati = json.loads(INSTANCE_LOCK.read_text(encoding="utf-8"))
        if dati.get("pid") == os.getpid() and dati.get("port") == port:
            INSTANCE_LOCK.unlink()


async def running_instance(session: aiohttp.ClientSession) -> str:
    with contextlib.suppress(Exception):
        dati = json.loads(INSTANCE_LOCK.read_text(encoding="utf-8"))
        porta = int(dati.get("port") or 0)
        if porta:
            url = f"http://127.0.0.1:{porta}"
            if await is_our_bridge(session, url):
                return url
    return ""


def already_open(url: str, open_browser: bool) -> BridgeError:
    riportato = False
    if open_browser:
        with contextlib.suppress(Exception):
            webbrowser.open(url)
            riportato = True
    return BridgeError(
        "Il ponte era gia' aperto in un'altra finestra. "
        + (f"Ti ho riportato il browser su {url}: " if riportato
           else f"Il dashboard e' su {url}: ")
        + "l'altra finestra non va chiusa.",
        "The bridge was already open in another window. "
        + (f"I brought your browser back to {url}: " if riportato
           else f"The dashboard is at {url}: ")
        + "leave that window open.",
    )


async def run(port: int, mock: bool, history: int, open_browser: bool,
              peek: int = PEEK_ACT) -> None:
    timeout = aiohttp.ClientTimeout(total=30)
    connector = aiohttp.TCPConnector(ssl=remote_ssl())
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        riot = RiotClient(session)
        tracker = Tracker(riot, history_size=history, peek=peek)

        if mock:
            tracker.state = mock_state()

        url = f"http://127.0.0.1:{port}"

        acceso = await running_instance(session)
        if acceso:
            raise already_open(acceso, open_browser)

        stop = asyncio.Event()
        app = build_app(tracker, stop)
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        try:
            await web.TCPSite(runner, "127.0.0.1", port).start()
        except OSError as exc:
            await runner.cleanup()
            if await is_our_bridge(session, url):
                raise already_open(url, open_browser) from exc
            raise BridgeError(
                f"La porta {port} e' occupata da un altro programma. "
                f"Avvia con --port 7891 per usarne un'altra."
            ) from exc

        write_instance_lock(port)

        found = index_ui_version()
        if found is None:
            print("\n  ATTENZIONE: index.html non trovato.")
            print(f"  Mettilo in {WEB_DIR / 'index.html'}")
            print(f"  oppure accanto a bridge.py in {HERE / 'index.html'}")
        elif found != UI_VERSION:
            print()
            print("  " + "=" * 66)
            print(f"  ATTENZIONE: index.html e' della versione '{found}', questo")
            print(f"  bridge.py vuole la '{UI_VERSION}'. Hai aggiornato un file solo.")
            print(f"  Sostituisci {find_index()}")
            print("  " + "=" * 66)
        print(f"\n  valo-readout attivo su {url}")
        print("  Ctrl+C per fermare\n")
        if open_browser:
            with contextlib.suppress(Exception):
                webbrowser.open(url)

        tasks: list[asyncio.Task[Any]] = []

        async def boot() -> None:
            first = True
            while True:
                try:
                    await riot.connect()
                    tracker.state.account = {
                        "name": riot.game_name,
                        "tag": riot.game_tag,
                        "region": riot.region,
                    }
                    tracker.state.bridge = "connected"
                    tracker.state.error = None
                    await tracker.load_content()
                    tracker.load_row_cache()
                    tracker.load_peek_cache()
                    await tracker.refresh_stats("avvio")
                    tasks.append(asyncio.create_task(tracker.watch_state()))
                    tasks.append(asyncio.create_task(tracker.periodic_refresh()))
                    tasks.append(asyncio.create_task(tracker.watch_log()))
                    return
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    message = (str(exc) if isinstance(exc, BridgeError)
                               else f"Errore inatteso in avvio: {short_error(exc)}")
                    message_en = (exc.en if isinstance(exc, BridgeError)
                                  else f"Unexpected error at startup: {short_error(exc)}")
                    if first:
                        await tracker.fail(message, message_en)
                        first = False
                    else:
                        LOG.debug("Aggancio non riuscito: %s", short_error(exc))
                await asyncio.sleep(10)

        if not mock:
            tasks.append(asyncio.create_task(boot()))

        try:
            await stop.wait()
        finally:
            for t in tasks:
                t.cancel()
            await runner.cleanup()
            clear_instance_lock(port)


async def diagnose() -> None:
    print()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15),
                                     connector=aiohttp.TCPConnector(ssl=remote_ssl())) as sess:
        riot = RiotClient(sess)
        try:
            riot.lock = Lockfile.read()
            print(f"  lockfile      OK   porta {riot.lock.port}, pid {riot.lock.pid}")
        except BridgeError as exc:
            print(f"  lockfile      NO   {exc}")
            return

        for path in ("/entitlements/v1/token", "/chat/v1/session",
                     "/chat/v4/presences", "/riotclient/region-locale", "/help"):
            try:
                data = await riot.local_get(path)
                extra = ""
                if path == "/chat/v4/presences":
                    n = len((data or {}).get("presences", []))
                    extra = f"  ({n} presenze)"
                elif path == "/help":
                    ev = (data or {}).get("events", {})
                    extra = f"  ({len(ev)} eventi disponibili)"
                print(f"  GET {path:28} OK{extra}")
            except Exception as exc:
                print(f"  GET {path:28} NO   {exc}")

        try:
            await riot.refresh_tokens()
            await riot.load_identity()
            await riot.detect_region()
            await riot.detect_version()
            print(f"  identita      OK   {riot.game_name}#{riot.game_tag}")
            print(f"  regione       OK   {riot.region}/{riot.shard}  build {riot.client_version}")
        except Exception as exc:
            print(f"  identita      NO   {exc}")
            return

        tracker = Tracker(riot)

        print("\n  struttura della presenza:")
        try:
            data = await riot.local_get("/chat/v4/presences")
            entries = (data or {}).get("presences", [])
            print(f"    {len(entries)} presenze in lista")
            for i, pres in enumerate(entries):
                mine = pres.get("puuid") == riot.puuid
                print(f"    [{i}] product={pres.get('product')!r} "
                      f"tua={'SI' if mine else 'no'} chiavi={sorted(pres.keys())}")
                if not mine:
                    continue
                priv = pres.get("private") or ""
                print(f"         private: {len(priv)} caratteri")
                if not priv:
                    print("         vuoto: il client non espone piu' i dettagli qui")
                    continue
                try:
                    pad = "=" * (-len(priv) % 4)
                    blob = json.loads(base64.b64decode(priv + pad))
                except Exception as exc:
                    print(f"         non decodificabile ({exc})")
                    print(f"         inizio grezzo: {priv[:100]}")
                    continue
                print(f"         {len(blob)} campi decodificati:")
                for k in sorted(blob):
                    v = blob[k]
                    if isinstance(v, str):
                        if v == riot.puuid:
                            v = "<il tuo puuid>"
                        elif len(v) > 46:
                            v = v[:46] + "…"
                    print(f"           {k} = {v!r}")
        except Exception as exc:
            print(f"    NO   {short_error(exc)}")

        print("\n  stato dai miei endpoint (solo il mio puuid):")
        for label, url in (
            ("pregame", f"{riot.glz}/pregame/v1/players/{riot.puuid}"),
            ("core-game", f"{riot.glz}/core-game/v1/players/{riot.puuid}"),
        ):
            try:
                d = await riot.remote_get(url)
                print(f"    {label:22} {'in questo stato' if d else 'no (404)'}")
            except Exception as exc:
                print(f"    {label:22} errore: {short_error(exc)}")

        print("\n  handshake websocket, una variante per riga:")
        for v in tracker._ws_variants():
            try:
                async with sess.ws_connect(
                    v["url"], ssl=riot._local_ssl, timeout=6, **v["kw"]
                ) as ws:
                    await ws.send_str('[5, "OnJsonApiEvent_chat_v4_presences"]')
                    print(f"    {v['name']:22} ACCETTATA")
            except aiohttp.WSServerHandshakeError as exc:
                print(f"    {v['name']:22} rifiutata, http {exc.status}")
            except Exception as exc:
                print(f"    {v['name']:22} rifiutata, {type(exc).__name__}: {exc}")

        print("\n  endpoint remoti:")
        for label, url in (
            ("mmr", f"{riot.pd}/mmr/v1/players/{riot.puuid}"),
            ("match-history", f"{riot.pd}/match-history/v1/history/{riot.puuid}?startIndex=0&endIndex=1"),
            ("competitiveupdates", f"{riot.pd}/mmr/v1/players/{riot.puuid}/competitiveupdates?startIndex=0&endIndex=1&queue=competitive"),
        ):
            try:
                d = await riot.remote_get(url)
                print(f"    {label:22} OK{'' if d else '   (risposta vuota)'}")
                if label == "competitiveupdates" and (d or {}).get("Matches"):
                    print(f"      campi: {sorted((d['Matches'][0] or {}).keys())}")
            except Exception as exc:
                print(f"    {label:22} NO   {exc}")
    print()


def main() -> None:
    ap = argparse.ArgumentParser(description="Ponte locale per il dashboard Valorant")
    ap.add_argument("--port", type=int, default=7890)
    ap.add_argument("--mock", action="store_true", help="dati finti, gioco non richiesto")
    ap.add_argument("--history", type=int, default=10,
                    help="righe nella tabella storico (le medie usano tutto l'act)")
    ap.add_argument("--peek", default="act", metavar="N|act",
                    help="partite da leggere per ogni giocatore in lobby per "
                         "kda/acs/win rate: 'act' per tutto l'act in corso "
                         "(default), un numero per le ultime N, 0 per "
                         "disattivare")
    ap.add_argument("--no-browser", action="store_true", help="non aprire il browser")
    ap.add_argument("--diag", action="store_true",
                    help="prova ogni endpoint e stampa cosa risponde, poi esce")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    if sys.stdout is None or sys.stderr is None:
        with contextlib.suppress(OSError):
            STARTUP_LOG.parent.mkdir(parents=True, exist_ok=True)
            if STARTUP_LOG.exists() and STARTUP_LOG.stat().st_size > 1_000_000:
                STARTUP_LOG.unlink()
            stream = open(STARTUP_LOG, "a", encoding="utf-8", buffering=1)
            sys.stdout = sys.stderr = stream

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger().addHandler(UILogHandler())

    if args.diag:
        asyncio.run(diagnose())
        return

    peek = PEEK_ACT if str(args.peek).strip().lower() == "act" else 0
    if peek != PEEK_ACT:
        try:
            peek = max(0, int(args.peek))
        except ValueError:
            sys.exit(f"--peek vuole un numero oppure 'act', non {args.peek!r}")

    try:
        asyncio.run(run(args.port, args.mock, args.history, not args.no_browser,
                        peek))
    except KeyboardInterrupt:
        print("\n  Chiuso.")
    except BridgeError as exc:
        print(f"\n  {exc}\n")
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()

