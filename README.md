# 🎭 Parlando (`parlando`)

[![CI](https://github.com/plbogen2/parlando/actions/workflows/ci.yml/badge.svg)](https://github.com/plbogen2/parlando/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![Companion: Marginalia](https://img.shields.io/badge/companion-Marginalia-emerald.svg)](https://github.com/plbogen2/marginalia)

**Parlando** (Italian: *“speaking”* — musical and theatrical recitation delivered with the natural cadence of speech) is a studio-grade neural prose synthesis and audio engineering engine. 

Designed specifically for fiction writers, long-form manuscripts, and online articles, Parlando transforms raw prose into fluid, broadcast-mastered audiobooks with multi-character dialogue isolation, intelligent punctuation pacing, zero-crossing DSP stitching, and interactive Web Audio players.

Parlando operates as a standalone CLI tool, a containerized REST microservice, and the official speech synthesis companion for **[Marginalia](https://github.com/plbogen2/marginalia)**.

---

## ⚡ Architecture Pipeline

```
                                  ┌────────────────────────┐
                                  │   Manuscript Ingest    │
                                  │ (TXT, MD, EPUB, URLs)  │
                                  └───────────┬────────────┘
                                              │
                                  ┌───────────▼────────────┐
                                  │   Narrative Chunker    │
                                  │ (Dialogue & Headings)  │
                                  └───────────┬────────────┘
                                              │
                                  ┌───────────▼────────────┐
                                  │    Prosody Director    │
                                  │  (Pacing & Envelopes)  │
                                  └───────────┬────────────┘
                                              │
                                  ┌───────────▼────────────┐
                                  │  Pluggable Neural TTS  │
                                  │ (Edge / OAI / Gemini)  │
                                  └───────────┬────────────┘
                                              │
                                  ┌───────────▼────────────┐
                                  │ Audio DSP & Stitcher   │
                                  │ (Zero-Crossing + Fade) │
                                  └───────────┬────────────┘
                                              │
                                  ┌───────────▼────────────┐
                                  │  EBU R128 Mastering    │
                                  │ (M4B / MP3 / Chapters) │
                                  └───────────┬────────────┘
                                              │
                                  ┌───────────▼────────────┐
                                  │ Standalone Web Player  │
                                  │  (HTML5 + FFT Visual)  │
                                  └────────────────────────┘
```

---

## 🎧 Listen to Real Sample Output

Experience Parlando's neural prosody, multi-character dialogue isolation, and zero-crossing DSP in action synthesizing William Gibson's *Chiba City Blues* (*Neuromancer* Chapters 1 & 2):

<audio controls src="https://github.com/plbogen2/parlando/raw/main/samples/chiba_city_blues.mp3">
  <a href="https://github.com/plbogen2/parlando/raw/main/samples/chiba_city_blues.mp3">▶ <b>Play / Download MP3 (2.10 min)</b></a>
</audio>

* 🔊 **Direct Audio Stream**: [**Play `chiba_city_blues.mp3` (2.10 min)**](https://github.com/plbogen2/parlando/raw/main/samples/chiba_city_blues.mp3) *(19 narrative chunks, multi-speaker Gemini neural audio attribution: `Fenrir` Narrator + `Puck` Case + `Aoede` Linda Lee + `Charon` Hotel Clerk)*
* 🌐 **Interactive Web Player**: [**Launch Web Player Online**](https://htmlpreview.github.io/?https://github.com/plbogen2/parlando/blob/main/samples/chiba_city_blues_player.html) or open [`samples/chiba_city_blues_player.html`](samples/chiba_city_blues_player.html) *(Features chapter scrubbing, speed controls, and real-time spectrum visualizer with 100% self-contained embedded audio)*
* 📄 **Source Manuscript**: [`samples/neuromancer_sample.md`](samples/neuromancer_sample.md)

#### Synthesized using Google Gemini Studio Voice:
```bash
parlando samples/neuromancer_sample.md \
  -o samples/chiba_city_blues.mp3 \
  --format mp3 \
  --engine gemini \
  --voice Fenrir \
  --pacing dramatic
```
*(With character voice attributions: `Case` -> `Puck`, `Linda Lee` -> `Aoede`, `Hotel Clerk` -> `Charon`)*

---

## 🚀 Key Features

### 1. Narrative-Aware Prose Chunking & Dialogue Isolation
* **Dialogue Differentiation**: Automatically isolates spoken character dialogue (`“...”`, `"..."`) from narrator exposition, allowing character voice assignment and gender attribution.
* **Contraction-Safe Segmentation**: Preserves word-internal apostrophes (`don't`, `Manfred's`, `we've`, `I'm`) to eliminate phonetic stuttering and chopped acoustic artifacts.
* **Semantic Rhythm & Micro-Pauses**: Dynamically calculates pause durations based on punctuation syntax (`.` -> 220ms, `...` -> 370ms, `—` -> 320ms, dialogue turnarounds -> 400ms, paragraph transitions -> 650ms, chapter breaks -> 1,200ms).

### 2. Zero-Crossing Alignment & Crossfading DSP
* **Pure Python Signal Processing**: Custom 16-bit PCM waveform assembler with zero heavy audio library dependencies.
* **Zero DC Offset & Pop Removal**: Searches local waveform bounds for exact sign changes (zero-crossings) before splicing, eliminating speaker pops and transducer clicks.
* **Equal-Power Crossfades**: Applies smooth sinusoidal crossfading between consecutive speech bursts.
* **Chunk Checkpointing**: Resumable `.chunk_cache` allows long multi-hour novels to resume instantly without re-synthesizing rendered paragraphs.

### 3. Multi-Source Ingestion & Smart Scraping
* **Manuscripts**: Plain text (`.txt`), Markdown (`.md` with YAML frontmatter), EPUB (`.epub`), PDF (`.pdf`), and HTML files.
* **Live Web Scraping**: Ingests online fiction and articles directly from URLs (e.g. Baen Books, Infinity Plus, Project Gutenberg, news/blog posts) with automated boilerplate removal, multi-table prose assembly, and anchor fragment targeting (`#Chapter2`).
* **Multi-Chapter Splitting**: Detects inline section headers and Roman numeral breaks, formatting each section as a discrete chapter track.

### 4. Pluggable Voice Backends
* **Edge-TTS (`--backend edge`)** *(Default)*: Free, zero-setup Microsoft Neural TTS voices (`en-US-ChristopherNeural`, `en-US-GuyNeural`, `en-GB-SoniaNeural`, `en-US-JennyNeural`). No API keys or accounts required.
* **OpenAI TTS (`--backend openai`)**: High-definition OpenAI voices (`tts-1-hd` with `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`).
* **Gemini / Cloud TTS (`--backend gemini`)**: Google Cloud / Gemini neural voice deck (`Fenrir`, `Aoede`, `Puck`, `Charon`, `Kore`, `Leda`).
* **Mock Engine (`--backend mock`)**: Fast, offline synthetic harmonic engine for headless testing and CI/CD pipelines.

### 5. Broadcast Mastering & Embedded Chapter Marks
* **M4B & MP3 Containers**: Encodes to standard audiobook `.m4b` (AAC) or `.mp3` with embedded ID3v2/MP4 chapter timepoint marks.
* **ITU-R BS.1770-4 / EBU R128 Normalization**: Masters output to standard audiobook loudness targets (-16 LUFS, -1.5 dBFS true peak).

### 6. Interactive Web Audio Studio & Standalone Player
* **Browser Studio UI** (`parlando --web`): Full-featured dark-mode console with live audio auditioning, progress bar telemetry, and chapter inspection.
* **Real Web Audio FFT Visualizer**: Real-time 40-bar frequency spectrum analyzer powered by HTML5 `AudioContext` + `AnalyserNode`.
* **Standalone Single-File Player**: Automatically outputs a standalone, zero-dependency `<title>_player.html` audio player with interactive chapter scrubbing and speed controls.

---

## 📦 Installation

### From Source
```bash
git clone https://github.com/plbogen2/parlando.git
cd parlando
pip install -e .
```

### Dependencies
* **Python**: `3.9+`
* **System**: `ffmpeg` (recommended for M4B chapter embedding and broadcast loudness mastering)
  ```bash
  # Debian / Ubuntu
  sudo apt install ffmpeg

  # macOS
  brew install ffmpeg
  ```

---

## 🖥️ Usage Guide

### 1. Launch the Interactive Web Studio
Launch the browser studio on port `8765`:
```bash
parlando --web --port 8765
```
Open **`http://localhost:8765`** to drag-and-drop manuscripts, paste text, scrape URLs, audition voices, and monitor live synthesis.

---

### 2. Command Line Synthesizer

#### Convert a Markdown / Text Manuscript to an M4B Audiobook:
```bash
parlando novel.md -o audiobook.m4b --voice en-US-ChristopherNeural --pacing dramatic
```

#### Synthesize Directly from a Web URL:
```bash
parlando https://www.infinityplus.co.uk/stories/colderwar.htm \
  -o colder_war.m4b \
  --voice en-US-GuyNeural \
  --pacing cinematic
```

#### Fast Excerpt Auditioning (First ~1,000 words):
```bash
parlando novel.epub --audition --voice en-GB-SoniaNeural
```

#### Export as MP3 with Custom Pacing:
```bash
parlando chapter1.txt -o chapter1.mp3 --format mp3 --speed 1.05 --crossfade 40
```

---

## ⚙️ CLI Reference

| Flag | Default | Description |
| :--- | :--- | :--- |
| `input` | *(Required)* | Filepath (`.md`, `.txt`, `.epub`, `.pdf`, `.html`) or web URL (`https://...`). |
| `-o, --output` | Auto-derived | Destination audio master path (`.m4b`, `.mp3`, `.wav`). |
| `--backend` | `edge` | Synthesis engine: `edge`, `openai`, `gemini`, or `mock`. |
| `--voice` | `en-US-ChristopherNeural` | Primary narrator neural voice name. |
| `--dialogue-voice` | None | Dedicated voice override for character dialogue. |
| `--pacing` | `normal` | Pacing preset: `normal`, `brisk`, `dramatic`, `cinematic`, `contemplative`. |
| `--speed` | `1.0` | Global playback speed multiplier (`0.5x` – `2.0x`). |
| `--format` | `m4b` | Container format: `m4b` (chaptered AAC), `mp3` (ID3v2), or `wav`. |
| `--crossfade` | `35` | Zero-crossing crossfade overlap duration in milliseconds. |
| `--audition` | `False` | Auditioning mode: synthesizes only the first section/excerpt. |
| `--dry-run` | `False` | Analyzes chapter breakdown and word counts without synthesizing audio. |
| `--web` | `False` | Launches the interactive browser studio and REST API daemon. |
| `--port` | `8765` | Port for the web studio server. |

---

## 🐳 Docker & Microservice Deployment

Parlando can be run as a standalone container or as a companion sidecar for **Marginalia**:

```bash
docker build -t parlando .
docker run -p 8765:8765 parlando
```

### Docker Compose Sidecar Example
```yaml
services:
  marginalia:
    build: .
    ports:
      - "3000:3000"
    depends_on:
      - tts

  tts:
    build: ./parlando
    ports:
      - "8765:8765"
    restart: unless-stopped
```

---

## 🧪 Testing

Parlando includes a comprehensive test suite covering DSP crossfades, contraction-safe parsing, HTML cleaning, and mock end-to-end integration:

```bash
python3 run_tests.py
```

---

## 📄 License

Parlando is open-source software licensed under the **[MIT License](LICENSE)**.
Created by **Dr. Paul Logasa Bogen II**.
