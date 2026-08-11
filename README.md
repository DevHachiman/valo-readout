# VALO-READOUT

A Valorant tracker that runs entirely on your own PC.

It reads your live match from the Riot client, shows who is in the lobby with
their rank, peak and averages, and keeps a permanent local archive of your
competitive matches so your history survives even if the third-party archive
it borrows from ever disappears.

No account, no login, no server. It opens in your browser at
`http://127.0.0.1:7890` and talks to nothing except Riot and, optionally, one
free stats archive.

---

## What it shows
**While you play**
<img width="1095" height="627" alt="Screenshot 2026-08-11 194048" src="https://github.com/user-attachments/assets/b0c2e6b6-c9bb-4af1-8920-4dfa2adc1c9d" />
<img width="1111" height="773" alt="Screenshot 2026-08-11 194156" src="https://github.com/user-attachments/assets/2bba333a-6f5f-4700-b722-e358444cc043" />

- **Your side — attack or defense — during agent select**, before the match
  loads. The game itself does not tell you until you are already on the map;
  the tracker tells you while you are still choosing an agent, so you can pick

  for the half you are actually about to play. It is colour-coded the same way
  as the state pill: **red for attack, cyan for defense**.
- Match state (menus, agent select, in game), queue and map
- Both teams: agent, name, level, current rank, **peak rank**, and per-player
  k/d, ACS, headshot and win rate for the current act — the rank of every
  player, which the in-game scoreboard never shows you
- Party colours are *not* shown, and cannot be — see [Limitations](#limitations)

**Your own numbers**
<img width="1150" height="1191" alt="Screenshot 2026-08-11 193821" src="https://github.com/user-attachments/assets/44db6c86-8aaa-4fe8-bb4f-a299a09eab6f" />
- Current rank, RR, peak rank with the act it was reached in, and peak RR
- Act totals: wins, losses, win rate, KDA, k/d, ACS, headshot, kills per round,
  best agent
- Recent match history with the RR change of each game
- Per-map breakdown: win rate, k/d, ACS, headshot
- A per-act table going back as far as your archive reaches, with the peak rank
  of each act

**What it costs you: nothing**

This matters as much as the numbers, so it is measured, not claimed.

| | |
|---|---|
| RAM | ~65 MB |
| CPU, idle in menus | 0.0% |
| CPU, average over 22 minutes | 0.006% of the machine |
| Impact on your FPS | none |

The tracker is a **separate program**. It does not overlay the game, does not
inject anything into it, does not hook DirectX, and never reads or writes
`valorant.exe`'s memory. It talks to the same local HTTP port the Riot client
already runs for its own use. Valorant cannot tell the difference between
playing with it open and playing without it, and neither can your frame rate.

You read it on a second monitor, or with alt-tab. Nothing covers the game.

**The interface**

- **One page.** No menus, no tabs, no settings screen, no login, no onboarding.
  Everything is visible at once.
- **Every block folds.** Each card has a **−** button; press it and the card
  collapses to its title. Fold away what you do not care about and the layout
  is remembered for next time.
- **Nothing to learn.** Top to bottom: the lobby (only while you are in one),
  your rank, recent matches, maps, acts. Colours mean one thing each — green is
  a win, red a loss, and a dimmed number means "computed on fewer matches than
  the act actually contains", with a tooltip saying how many.

---

## Install

There are two ways. Pick one.

### 1. Ready-made executable (easiest)

1. Download `valo-readout.zip` from the **Releases** page.
2. Unzip it anywhere.
3. Double-click `valo-readout.exe`.

That is all. Python is already inside the file; nothing gets installed on your
system.

The first time, Windows will say *"Windows protected your PC"*. This happens
because the file is not signed with a paid certificate, not because anything is
wrong with it. Click **More info → Run anyway**. It asks once.

### 2. From source (manual)

Use this if you would rather run code you can read, or you are not on Windows
and want to adapt it.

**Requirements:** Python 3.11 or newer.

```bash
git clone <this-repo>
cd valo-readout
pip install -r requirements.txt
python bridge.py
```

The dashboard opens in your browser by itself.

On Windows there are two double-click launchers in the repo:

| file | what it does |
|---|---|
| `valo-readout.bat` | runs the bridge in a visible console. Installs `aiohttp` for you on first run. Use this one when something goes wrong — you see everything. |
| `valo-readout.vbs` | runs it with `pythonw.exe`, no console window at all. This is the everyday launcher. |

**Useful flags**

```
python bridge.py --port 7890      # change the port
python bridge.py --mock           # sample data, no game needed
python bridge.py --no-browser     # do not open a browser
python bridge.py --diag           # probe every endpoint and print what answers
python bridge.py --peek 0         # do not read other players' match history
```

### Building your own executable

```
costruisci.bat
```

It installs PyInstaller and produces `dist/valo-readout.exe` on your machine,
from the source you can read. Your file will not be byte-identical to the one
in Releases — PyInstaller builds are not reproducible — and that is fine. Use
yours.

### Before the first run

**Launch Valorant at least once before you start the tracker.** Your region and
shard are read out of the game's own log file
(`%LOCALAPPDATA%\VALORANT\Saved\Logs\ShooterGame.log`, from the
`glz-<region>-1.<shard>.a.pvp.net` line it writes). If that log has never
existed, the tracker falls back to asking the Riot client for your region and
guessing the shard from a table — usually right, not always.

Keep Valorant running while you use it. The tracker reads from the live client;
with the game closed there is nothing to read.

### Closing it properly

Use the **CLOSE** button at the top right. That actually stops the bridge.

Closing the browser tab does **not** stop it — the tracker is a program, and
the page is just its window. If you close the tab and want it back, reopen
`http://127.0.0.1:7890`.

---

## The optional API key

Riot's own endpoints only expose your **last ~43 competitive matches**.
Everything older is out of reach.

With a free [HenrikDev](https://api.henrikdev.xyz/dashboard/) key, the tracker
reaches almost the whole act — for you *and* for the other nine players in your
lobby. Without a key it still works, just on fewer matches.

The tracker opens the key panel by itself on first run. The **KEY** button at
the top reopens it whenever you want. The key is tested before it is saved, so
a typo tells you immediately.

### How to get one

It is free and takes about two minutes.

**1. Join the HenrikDev Discord** — <https://discord.gg/X3GaVkX2YN>

Optional. 

**2. Open the dashboard and log in** — <https://api.henrikdev.xyz/dashboard/>

Log in with Discord and authorize it. There is no separate account to create.

**3. Sidebar → `API Keys` → `Generate New Key`**

**4. Fill in the form**

| field | what to put |
|---|---|
| **Application Name** | anything — `valo-readout` does fine |
| **Description** | one honest line, e.g. *"Personal Valorant stats dashboard, local use only"* |
| **Game** | Valorant — already selected |
| **Access Tier** | each tier shows its rate limit next to its name. Pick the free one [Standard] |
| **Commercial checkbox** | **leave it unchecked.** It means *"my app makes money"*, and ticking it puts you in the paid track. |

**5. Press `Generate Key`**

If the tier was not a reviewed one, the key exists immediately. If it was, the
card says *Pending manual review* and you wait.

**6. Copy it into the tracker**

On the key's card, next to **Access Token**, use the eye button to reveal it
and the copy button to copy it. Paste it into the tracker's **KEY** panel and
save. It is stored in `%LOCALAPPDATA%\valo-readout\henrik.key` on your machine
and sent to nobody but HenrikDev.

### About the rate limit

The limit is per key, and since v4 of that API **one request can cost more than
one**: the call itself counts 1, plus 1 for every request the service has to
make to Riot in the background to answer you. Cached answers cost only 1. This
is why the tracker caches aggressively and spaces its own requests out.

Get your own key rather than borrowing someone's — two people on one key throttle
each other.

---

## Your archive: the point of running this locally

This is the part that makes a local tracker worth having, so read it.

**Riot only keeps a moving window of your last ~43 competitive matches.** Not
"the last 43 you can see easily" — the last 43 that exist for anyone to read.
Match 44 is not hidden, it is *gone*, for every tracker on the internet,
including this one.

**This tracker copies every match it sees into `matches.json` on your disk, and
never deletes anything from it.** So the window keeps moving and your archive
keeps growing. After a while the archive holds matches that Riot itself can no
longer show you, and it keeps holding them for as long as you keep the file.

### The catch, with numbers

The archive can only contain what the tracker actually saw. Riot's window
moves whether you are watching it or not.

**Good — you lose nothing:**

```
Monday    you open the tracker      Riot's window: matches 1-43     archive: 43
          you play 20 matches       window slides to 21-63
Tuesday   you open the tracker      it sees 21-63; 44-63 are new    archive: 63
```

The 20 new matches were still inside the window when the tracker looked. All
saved.

**Bad — you lose 17 matches, permanently:**

```
Monday    you open the tracker      window: matches 1-43            archive: 43
          over five days you
          play 60 matches           window slides to 61-103
Saturday  you open the tracker      it sees 61-103 only             archive: 103
                                    matches 44-60 fell out of the
                                    window before it ever looked -> lost forever
```

Nothing can bring 44–60 back. Not this tracker, not the API key, not Riot
support. They are simply not stored anywhere anymore.

### The rule

> **Open the tracker at least once every ~43 competitive matches.**

The easiest way to never think about it again is to **just leave it running
while you play**. It updates after every match, so the gap between what it has
seen and what you have played is never more than one game.

**With an API key the margin is much wider** — the third-party archive reaches
back across the whole act rather than 43 matches, so forgetting for a week
usually costs you nothing. Without a key, the 43-match rule is the whole story.

### And once it is in the archive

- **It is not deleted, ever.** No cap, no pruning, no expiry. ~400 bytes per
  match; a year of playing is a few MB.
- **It survives the sources.** Matches that only the third-party archive knew
  about are copied in too, so if that service shuts down tomorrow, everything
  you already had stays readable.
- **It survives act changes.** A new act starts a new set of totals; the old
  act stays in the archive exactly as it was. Acts accumulate — they do not
  replace each other.
- **It survives account switching.** Accounts sit side by side in the same
  file. Switching never overwrites another account's history.
- **Back it up.** `matches.json` is the one file here you cannot re-download.
  Copy it to a new PC by hand, and copy it somewhere safe now and then.

---

## Where your data lives

Everything is in `%LOCALAPPDATA%\valo-readout\` and nowhere else:

| file | contents |
|---|---|
| `matches.json` | your own matches, kept forever (~400 bytes each) |
| `peeked.json` | matches read for other players (capped at 12,000) |
| `henrik.key` | your API key, if you gave one |
| `bridge.log` | the log (truncated past 1 MB) |
| `bridge.lock` | port of the running instance, so a second copy cannot start |

A few MB in total, with a ceiling around fifteen. Delete the folder to reset
everything; it rebuilds itself — except `matches.json`, which is the one thing
you cannot get back. It sits deliberately outside OneDrive, so moving to a new
PC means copying it by hand.

---

## Strengths

- **Fully local.** Listens on `127.0.0.1` only. Nothing is reachable from
  outside your machine, and no data leaves it except the requests to Riot and,
  if you enable it, the stats archive.
- **Never touches your password.** It authenticates with the lockfile — the
  temporary credential Riot's own client writes for itself. It does not read
  game memory and does not modify any Valorant file.
- **Your history is yours, and it only grows.** Every match the tracker sees is
  written to a local archive that is never pruned, so it outlives Riot's
  43-match window. Matches known only to the third-party archive are copied in
  as well, so the day that service shuts down, what you already had stays
  readable. On a real account this took the archive from 45 matches to **746
  across 27 acts**. See [Your archive](#your-archive-the-point-of-running-this-locally).
- **Free where it counts, in agent select.** You know whether you are starting
  on attack or defense while you are still picking, and you see every player's
  rank and peak — two things the game keeps from you.
- **Costs nothing to run.** ~65 MB of RAM and effectively no CPU (measured:
  0.006% over 22 minutes). No overlay, no injection, no hook — your frame rate
  is untouched.
- **Simple on purpose.** One page, no menus, no login. Every card folds with
  one button and the layout is remembered.
- **Exact where it can be.** Wins, losses and win rate come from Riot's own
  seasonal counter, so they are correct even for matches nobody can read
  anymore.
- **Honest where it cannot be.** k/d, ACS and headshot can only be computed on
  matches actually read. When those are a minority of the act, the numbers are
  shown dimmed with a tooltip saying how many matches they rest on.
- **Multi-account.** Switch Riot account and the tracker follows, keeping each
  account's archive separate.
- **Survives being offline.** The bridge starts before the game, waits for it,
  and reconnects on its own when you switch account or restart the client.
- **No install, no telemetry, no account.**

---

## Limitations

Read this section. Some of these are permanent.

- **Windows only.** The core would run anywhere, but the lockfile path, the
  launchers and the packaging are Windows-specific.
- **Riot only exposes ~43 recent competitive matches.** Anything older that the
  tracker never saw, and that the third-party archive does not have, is gone
  for good. There is no way around this.
- **Which means you have to actually run it.** The archive is permanent, but it
  can only keep what it saw. Play 60 matches without opening the tracker once
  and the oldest 17 are lost before it ever gets a chance — see
  [Your archive](#your-archive-the-point-of-running-this-locally) for the
  arithmetic. Leaving it running while you play removes the problem entirely.
- **The third-party archive is not complete either.** It is not Riot's, and it
  misses matches. On a 138-match act it had 132. Expect k/d, ACS and headshot
  to be very good estimates, not official counts.
- **Party detection is impossible.** You cannot see who is duo/trio with whom
  during a match. This was tested against the live client, not assumed:
  pre-game exposes no party field, core-game exposes no party field,
  `parties/v1/players` on another player's puuid returns **403**, and
  `IsAssociated` is `true` for all ten players. The party ID only exists in
  end-of-match details, when it is no longer useful.
- **Peak RR of past acts cannot be recovered.** Riot only reports the peak
  *tier* per act, not the RR. The tracker shows a peak RR only when it has
  actually seen a match at that tier.
- **No official Riot API is used, because none is available.** Riot does not
  issue personal keys for Valorant, and production keys require an approved
  professional project plus RSO login. This tracker uses the same read-only
  endpoints every public tracker uses. They are unofficial and could change or
  break without warning.
- **One instance at a time.** A second copy will not start; it brings your
  browser back to the one already running. This is deliberate — two copies
  would overwrite each other's archive.
- **Antivirus false positives.** Programs packaged with PyInstaller typically
  trip 2–8 of 70 engines on VirusTotal with generic names like `Wacatac`. If
  that bothers you, build it yourself with `costruisci.bat`.
- **Rate limits are real.** Reading a whole act for ten players is a lot of
  requests. The tracker caches aggressively and throttles itself, but hammering
  refresh will get you temporary `429` responses from Riot.
- **Reading other players costs time.** Averages for the lobby fill in
  progressively over a few seconds to a few minutes, depending on how many
  matches each player has. Partial results are saved as they arrive.

---

## Is this against the rules? Is it a virus?

It uses the same read-only endpoints as the trackers you already use on the
web. It does not read game memory, does not inject anything, does not automate
gameplay, and does not touch any Valorant file. That said, these endpoints are
not a public Riot API and Riot makes no promises about them — use it knowing
that.

As for the executable: you cannot verify an `.exe` someone handed you, and you
should not pretend otherwise. That is exactly why the full source is here.
Read `bridge.py`, or run `costruisci.bat` and use the file you built yourself.
A hash only proves the file is the same one that left the sender — not that it
is clean.

---

## How it works

```
Riot client  ──lockfile auth──►  local API   ─┐
                                              ├──►  bridge.py  ──►  browser
Riot servers ──entitlements───►  pd / glz    ─┘      (aiohttp)      (index.html)
                                                          │
HenrikDev archive (optional, needs a key)  ───────────────┘
```

`bridge.py` is a single-file aiohttp server. It authenticates against the local
Riot client with the lockfile, gets an entitlements token, and reads from
Riot's `pd` and `glz` endpoints. It pushes state to the page over a WebSocket,
falling back to 2-second polling on clients that reject the WebSocket
handshake. `index.html` is a single self-contained file with no external
JavaScript.

---

## License

MIT — see [LICENSE](LICENSE). Copyright © 2026
[DevHachiman](https://github.com/DevHachiman).

VALORANT and Riot Games are trademarks or registered trademarks of Riot Games,
Inc. This project is not affiliated with, endorsed by, or sponsored by Riot
Games, and uses unofficial, read-only endpoints of the Riot client.
