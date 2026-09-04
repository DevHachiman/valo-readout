# VALO-READOUT

**A Valorant tracker that runs entirely on your own PC.**

It reads your live match from the Riot client, shows who is in the lobby with their rank, peak and averages, and keeps a permanent local archive of your competitive matches — so your history survives even if the third-party archive it borrows from ever disappears.

No account. No login. No server. It opens in your browser at `http://127.0.0.1:7890` and talks to nothing except Riot and, optionally, one free stats archive.

```
Download the valo-readout.exe →  double-click  →  play
```

> [!IMPORTANT]
> **Open the tracker at least once every ~43 competitive matches.**
> Riot only keeps a moving window of your last ~43 matches. Whatever falls out of that window before the tracker sees it is gone — for every tracker on the internet, permanently. [Full explanation below.](#your-archive-the-point-of-running-this-locally)

---

## Contents

- [What it shows](#what-it-shows)
- [Install](#install)
- [The optional API key](#the-optional-api-key)
- [Your archive: the point of running this locally](#your-archive-the-point-of-running-this-locally)
- [Where your data lives](#where-your-data-lives)
- [What it costs your PC](#what-it-costs-your-pc)
- [What you get](#what-you-get)
- [Limitations](#limitations)
- [FAQ](#faq)
- [How it works](#how-it-works)
- [License](#license)

---

## What it shows

### While you play

<img width="1307" height="1242" alt="image" src="https://github.com/user-attachments/assets/3e33a0dd-27c8-4b17-91f3-22f8683bffaf" />

| | |
|---|---|
| **Your side, in agent select** | Attack or defense, before the match loads. The game does not tell you until you are already on the map. Colour coded like the state pill: **red for attack, cyan for defense**. |
| **The full lobby** | Both teams: agent, name, level, current rank, **peak rank**, competitive games this act, and per-player k/d, ACS, headshot and win rate — the rank of every player, which the in-game scoreboard never shows you. |
| **People you've met before** | Anyone you have played with gets a badge. Click it and a box opens in place, listing your last games together: when, the map, the result, and whether they were with you or against you. Ranked only. |
| **Your party in the menus** | Who is in the lobby and which queue you are searching, before the match even starts. |
| **Copy button** | Turns the lobby into plain text you can paste anywhere. |
| **Match state** | Queue and map at a glance. |

### Your own numbers

<img width="1335" height="1080" alt="image" src="https://github.com/user-attachments/assets/8f5bdb0f-c7c6-41da-822e-c242735d72aa" />

- **Rank** — current rank and RR, peak rank with the act it was reached in, and peak RR.
- **Act totals** — wins, losses, win rate, KDA, k/d, ACS, headshot, kills per round, best agent.
- **Recent matches** — with the RR change of each game.
- **Per map** — win rate, k/d, ACS, headshot.
- **Per act** — a table going back as far as your archive reaches, with the peak rank of each act.

### The interface

- **One page.** No menus, no tabs, no settings screen, no login.
- **Every block folds.** Each card has a **−** button, and the layout is remembered for next time.
- **Colours mean one thing each.** Green is a win, red is a loss. A dimmed number means *"computed on fewer matches than the act actually contains"*, with a tooltip saying how many.

---

## Install

### Option 1 — Ready-made executable (easiest)

1. Download `valo-readout.exe` from the **[Releases](../../releases)** page.
2. Double-click and play.

Python is already inside the file; nothing gets installed on your system.

> [!NOTE]
> The first time, Windows will say *"Windows protected your PC"*. That is because the file is not signed with a paid certificate, not because anything is wrong with it. Click **More info → Run anyway**. It asks once.

### Option 2 — From source

**Requires Python 3.11 or newer.**

```bash
git clone <this-repo>
cd valo-readout
pip install -r requirements.txt
python bridge.py
```

The dashboard opens in your browser by itself.

On Windows there are two double-click launchers:

| file | what it does |
|---|---|
| `valo-readout.bat` | Visible console, installs `aiohttp` on first run. Use it when something goes wrong — you see everything. |
| `valo-readout.vbs` | `pythonw.exe`, no console window. The everyday launcher. |

<details>
<summary><b>Command-line flags</b></summary>

```
python bridge.py --port 7890      # change the port
python bridge.py --mock           # sample data, no game needed
python bridge.py --no-browser     # do not open a browser
python bridge.py --diag           # probe every endpoint and print what answers
python bridge.py --peek 0         # do not read other players' match history
```

</details>

<details>
<summary><b>Building your own executable</b></summary>

Run `costruisci.bat` ("build" in Italian). It installs PyInstaller and produces `dist/valo-readout.exe` from the source you can read.

Your file will not be byte-identical to the one in Releases — PyInstaller builds are not reproducible — and that is fine. Use yours.

</details>

### Before the first run

> [!TIP]
> **Launch Valorant at least once before starting the tracker.**
> Your region and shard are read from the game's own log (`%LOCALAPPDATA%\VALORANT\Saved\Logs\ShooterGame.log`). Without that log the tracker asks the Riot client and guesses the shard from a table — usually right, not always.

Keep Valorant running while you use the tracker. With the game closed there is nothing to read.

### Staying up to date

While the tracker is running it asks GitHub every six hours whether a newer release exists. If there is one, a popup tells you what changed and updates it in one click — it downloads, swaps itself and restarts. It only ever downloads from this repository's own release files, and refuses anything oversized.

The check happens **only while the tracker is open**. Closed, it does nothing.

### Closing it properly

Use the **CLOSE** button at the top right.

Closing the browser tab does *not* stop it — the tracker is a program and the page is just its window. Reopen `http://127.0.0.1:7890` to get it back.

---

## The optional API key

**Short version:** the tracker works without a key. A free key just lets it see more matches.

Riot's own endpoints only expose your **last ~43 competitive matches**. Everything older is out of reach. With a free [HenrikDev](https://api.henrikdev.xyz/dashboard/) key the tracker reaches almost the whole act — for you *and* for the other nine players in your lobby.

The tracker opens the key panel on first run; the **KEY** button reopens it. The key is tested before being saved, so a typo tells you immediately.

### How to get one

Free, about two minutes.

1. **Optional:** join the HenrikDev Discord — <https://discord.gg/X3GaVkX2YN>
2. **Open the dashboard and log in** — <https://api.henrikdev.xyz/dashboard/>
   Log in with Discord and authorize it. No separate account to create.
3. **Sidebar → `API Keys` → `Generate New Key`**
4. **Fill in the form:**

   | field | what to put |
   |---|---|
   | **Application Name** | Anything — `valo-readout` does fine |
   | **Description** | One honest line, e.g. *"Personal Valorant stats dashboard, local use only"* |
   | **Game** | Valorant — already selected |
   | **Access Tier** | Each tier shows its rate limit. Pick the free one: **Standard** |
   | **Commercial checkbox** | **Leave it unchecked.** It means *"my app makes money"* and puts you in the paid track. |

5. **Press `Generate Key`.** If the tier was not a reviewed one, the key exists immediately; otherwise the card says *Pending manual review* and you wait.
6. **Copy it into the tracker.** On the key's card, next to **Access Token**, reveal it and copy it. Paste it into the **KEY** panel and save.

Your key is stored in `%LOCALAPPDATA%\valo-readout\henrik.key` and sent to nobody but HenrikDev.

### About the rate limit

It is **per key**, and since v4 of that API one request can cost more than one: the call counts 1, plus 1 for every request the service makes to Riot in the background to answer you. Cached answers cost 1.

This is why the tracker caches hard and spaces its requests out.

> [!WARNING]
> Get your own key rather than borrowing one — two people on one key throttle each other.

---

## Your archive: the point of running this locally

**Riot only keeps a moving window of your last ~43 competitive matches.** Not "the last 43 you can see easily" — the last 43 that exist for anyone to read. Match 44 is not hidden, it is *gone*, for every tracker on the internet, including this one.

**This tracker copies every match it sees into `matches.json` on your disk and never deletes anything from it.** The window keeps moving, your archive keeps growing, and after a while it holds matches Riot itself can no longer show you.

### The catch

The archive can only contain what the tracker actually saw, and Riot's window moves whether you are watching or not.

| what you do | what happens |
|---|---|
| Open it, play 20, open it again | Window slid 43 → 63. It saw them all. **Nothing lost.** |
| Open it, play 60 over five days, open it again | Window slid 43 → 103. Matches 44–60 fell out before it ever looked. **Lost forever.** |

Nothing brings those back. Not this tracker, not the API key, not Riot support.

> [!IMPORTANT]
> **The rule: open the tracker at least once every ~43 competitive matches.**
>
> The easiest way to never think about it again is to **leave it running while you play** — it updates after every match. With an API key the margin is much wider, since the third-party archive reaches back across the whole act.

### Once a match is in the archive

- **It is never deleted.** No cap, no pruning, no expiry. ~400 bytes per match; a year of playing is a few MB.
- **It survives the sources.** Matches only the third-party archive knew about are copied in too, so if that service shuts down tomorrow, what you already had stays readable.
- **It survives act changes and account switching.** Acts accumulate instead of replacing each other, and accounts sit side by side without overwriting.
- **Back it up.** `matches.json` is the one file here you cannot re-download.

---

## Where your data lives

Everything is in `%LOCALAPPDATA%\valo-readout\` and nowhere else:

| file | contents |
|---|---|
| `matches.json` | Your own matches, kept forever, plus the lobbies you have met (last 4,000) |
| `peeked.json` | Matches read for other players (capped at 12,000) |
| `henrik.key` | Your API key, if you gave one |
| `bridge.log` | The log (truncated past 1 MB) |
| `bridge.lock` | Port of the running instance, so a second copy cannot start |

A few MB in total, with a ceiling around fifteen. Delete the folder to reset everything; it rebuilds itself — except `matches.json`, which is the one thing you cannot get back.

It sits deliberately outside OneDrive, so moving to a new PC means copying it by hand.

---

## What it costs your PC

Measured, not claimed.

| | |
|---|---|
| RAM | ~65 MB |
| CPU, idle in menus | 0.0% |
| CPU, average over 22 minutes | 0.006% of the machine |
| Impact on your FPS | none |

The tracker is a **separate program**. It does not overlay the game, does not inject anything into it, does not hook DirectX, and never reads or writes `valorant.exe`'s memory. It talks to the same local HTTP port the Riot client already runs for itself.

Read it on a second monitor, or with alt-tab.

---

## What you get

- ✅ Runs entirely on your own PC
- ✅ No account, no login, no server
- ✅ Free, with no premium tier
- ✅ No ads, no telemetry
- ✅ Attack or defense in agent select
- ✅ Rank, peak and act stats of the whole lobby
- ✅ A badge on anyone you have already played with or against
- ✅ Your party and queue while you are still in the menus
- ✅ Comp history that outlives Riot's ~43-match window
- ✅ Your archive still works if HenrikDev goes down
- ✅ No overlay, no injection, no FPS drop

---

## Limitations

Read this section. Some of these are permanent.

**Data you cannot get, ever**

- **Riot only exposes ~43 recent competitive matches.** Anything older that the tracker never saw, and that the third-party archive does not have, is gone for good. There is no way around this.
- **Which means you have to actually run it.** Play 60 matches without opening it once and the oldest 17 are lost before it gets a chance.
- **The third-party archive is not complete either.** It is not Riot's, and it misses matches. On a 138-match act it had 132. Expect k/d, ACS and headshot to be very good estimates, not official counts.
- **Peak RR of past acts cannot be recovered.** Riot only reports the peak *tier* per act, not the RR. A peak RR appears only when the tracker has actually seen a match at that tier.
- **"Played with before" starts empty and only counts ranked.** It is built from what the tracker itself recorded, so it has nothing to say about lobbies from before you installed it. Riot no longer serves the rosters of old matches, so it cannot be backfilled.

**Things the client simply does not expose**

- **Party detection inside a match is impossible.** You can see your own party in the menus, but not who is duo or trio with whom once the match starts. This was tested against the live client, not assumed: pre-game exposes no party field, core-game exposes no party field, `parties/v1/players` on another player's puuid returns **403**, and `IsAssociated` is `true` for all ten. The party ID only exists in end-of-match details, when it is no longer useful.
- **No official Riot API is used, because none is available.** Riot does not issue personal keys for Valorant, and production keys require an approved professional project plus RSO login. This tracker uses the same read-only endpoints every public tracker uses. They are unofficial and could change or break without warning.

**Platform and practical limits**

- **Windows only.** The core would run anywhere, but the lockfile path, the launchers and the packaging are Windows-specific.
- **PC only.** Every rank, peak and average comes from the PC competitive queue. Console has its own separate queue, which the tracker never reads.
- **One instance at a time.** A second copy will not start; it brings your browser back to the one already running. Two copies would overwrite each other's archive.
- **Antivirus false positives.** PyInstaller programs typically trip 2–8 of 70 engines on VirusTotal with generic names like `Wacatac`. If that bothers you, build it yourself with `costruisci.bat`.
- **Rate limits are real.** Reading a whole act for ten players is a lot of requests. The tracker caches and throttles itself, but hammering refresh will get you temporary `429` responses from Riot.
- **Reading other players costs time.** Lobby averages fill in progressively over a few seconds to a few minutes. Partial results are saved as they arrive.

---

## FAQ

<details>
<summary><b>Is this against Riot's rules? Will I get banned?</b></summary>

It uses the same read-only endpoints as the trackers you already use on the web. It does not read game memory, does not inject anything, does not automate gameplay, and does not touch any Valorant file.

That said, these endpoints are not a public Riot API and Riot makes no promises about them — use it knowing that.

</details>

<details>
<summary><b>Is it a virus?</b></summary>

You cannot verify an `.exe` someone handed you, and you should not pretend otherwise. That is exactly why the full source is here.

Read `bridge.py`, or run `costruisci.bat` and use the file you built yourself. A hash only proves the file is the same one that left the sender — not that it is clean.

</details>

<details>
<summary><b>Do I need the API key?</b></summary>

No. Everything works without it. The key only widens how far back the tracker can see — for you and for the other players in your lobby.

</details>

<details>
<summary><b>What happens if HenrikDev shuts down?</b></summary>

Everything already in `matches.json` stays readable, including the matches that only came from there. The tracker falls back to Riot's own ~43-match window for new data.

</details>

<details>
<summary><b>Will it drop my FPS?</b></summary>

No. It is a separate program with no overlay and no hooks into the game. See [What it costs your PC](#what-it-costs-your-pc).

</details>

<details>
<summary><b>Can I check it from my phone?</b></summary>

No. It listens on `127.0.0.1` only — your own machine, nothing else on the network. That is the trade-off for having no server.

</details>

<details>
<summary><b>Mac or Linux?</b></summary>

Not supported. The core would run, but the lockfile path, the launchers and the packaging are Windows-specific. Valorant is Windows-only anyway.

</details>

<details>
<summary><b>I closed the tab and it's still running.</b></summary>

That is expected — the page is just its window. Reopen `http://127.0.0.1:7890`, then use the **CLOSE** button at the top right to stop it for real.

</details>

---

## How it works

```
Riot client  ──lockfile auth──►  local API   ─┐
                                              ├──►  bridge.py  ──►  browser
Riot servers ──entitlements───►  pd / glz    ─┘      (aiohttp)      (index.html)
                                                          │
HenrikDev archive (optional, needs a key)  ───────────────┘
```

`bridge.py` is a single-file aiohttp server. It authenticates against the local Riot client with the lockfile, gets an entitlements token, and reads from Riot's `pd` and `glz` endpoints. It pushes state to the page over a WebSocket, falling back to 2-second polling on clients that reject the handshake.

`index.html` is a single self-contained file with no external JavaScript.

---

## License

MIT — see [LICENSE](LICENSE). Copyright © 2026 [DevHachiman](https://github.com/DevHachiman).

VALORANT and Riot Games are trademarks or registered trademarks of Riot Games, Inc. This project is not affiliated with, endorsed by, or sponsored by Riot Games, and uses unofficial, read-only endpoints of the Riot client.
