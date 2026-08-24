"""Command-line interface and orchestrator for the Audiobook Narrator pipeline."""

import argparse
import os
import sys
import time
from typing import Optional

from .chunker import NarrativeChunker
from .config import (
    AudioFormat,
    PACING_PRESETS,
    PacingMode,
    VALID_NEURAL_VOICES,
    VOICE_PROFILES,
    VoiceProfile,
)
from .dsp import DEFAULT_SAMPLE_RATE
from .engine import (
    BaseVoiceEngine,
    get_voice_engine,
)
from .exporter import AudioExporter
from .parser import DocumentParser, ParsedDocument
from .prosody import ProsodyDirector
from .stitcher import AudioStitcher
from .web_server import start_web_server


CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def print_banner():
    """Display the William Gibson cybernetic acoustic deck banner."""
    banner = f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════════════════════════════╗
║  AUDIOBOOK_NARRATOR // NEURAL SPEECH & ACOUSTIC SYNTHESIS DECK       ║
║  v1.0.0 // Matrix Audio Pipeline // Direct-to-Waveform Engine        ║
╚══════════════════════════════════════════════════════════════════════╝{RESET}
"""
    print(banner)


def render_progress_bar(current: int, total: int, prefix: str = "", length: int = 40):
    """Render a clean terminal progress bar."""
    if total <= 0:
        return
    percent = (current / float(total)) * 100.0
    filled = int(length * current // total)
    bar = "█" * filled + "░" * (length - filled)
    sys.stdout.write(f"\r{DIM}[STREAM]{RESET} {prefix} |{CYAN}{bar}{RESET}| {percent:5.1f}% ({current}/{total})")
    sys.stdout.flush()
    if current >= total:
        sys.stdout.write("\n")


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="audiobook-narrator",
        description="Convert manuscripts (TXT, MD, EPUB, HTML, PDF, or live web URLs) into studio-grade audiobooks using neural TTS.",
    )

    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="Input manuscript file path (.txt, .md, .epub, .html, .pdf) or live web URL (http:// / https://). If omitted, launches Web Studio UI.",
    )
    parser.add_argument(
        "--web",
        "--server",
        action="store_true",
        help="Launch interactive Web Studio UI console.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Port for Web Studio UI server (default: 8765).",
    )
    parser.add_argument(
        "--backend",
        choices=["auto", "edge", "gemini", "openai", "mock"],
        default="auto",
        help="Neural voice synthesis backend (default: auto). Use 'edge' for free Microsoft Neural TTS, 'gemini' for Google Cloud/Gemini, 'openai' for OpenAI TTS.",
    )
    parser.add_argument(
        "--profile",
        choices=list(VOICE_PROFILES.keys()),
        default="cyberpunk_noir",
        help="Voice & aesthetic persona preset (default: cyberpunk_noir).",
    )
    parser.add_argument(
        "--voice",
        default=None,
        help="Neural voice override (e.g., Fenrir, Aoede, en-US-ChristopherNeural, alloy, onyx).",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Audiobook playback speed multiplier (0.5 to 2.0, default: 1.0).",
    )
    parser.add_argument(
        "--pacing",
        choices=[p.value for p in PacingMode],
        default=None,
        help="Pacing timing envelope override (normal, dramatic, reflective, brisk, technical).",
    )
    parser.add_argument(
        "--output-format",
        "-f",
        choices=[f.value for f in AudioFormat],
        default="mp3",
        help="Master container format (mp3, wav, m4b, aac, flac; default: mp3).",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default="./output_audiobook",
        help="Destination directory for rendered audiobook files (default: ./output_audiobook).",
    )
    parser.add_argument(
        "--output-name",
        default=None,
        help="Explicit output filename (e.g. neuromancer_ch1.mp3).",
    )
    parser.add_argument(
        "--title",
        default=None,
        help="Audiobook title metadata (auto-inferred from document/URL if omitted).",
    )
    parser.add_argument(
        "--author",
        default=None,
        help="Author metadata (auto-inferred if omitted).",
    )
    parser.add_argument(
        "--series",
        default=None,
        help="Series metadata tag.",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Publication year metadata.",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=4,
        help="Concurrent neural synthesis workers (default: 4).",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Run using offline mock synthesizer for instant testing/verification.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and analyze manuscript structure, showing chapter tokens and timing without generating audio.",
    )
    parser.add_argument(
        "--no-normalize",
        action="store_true",
        help="Disable EBU R128 loudness broadcast normalization.",
    )
    parser.add_argument(
        "--no-player",
        action="store_true",
        help="Disable automatic HTML player console generation.",
    )
    parser.add_argument(
        "--embed-player-audio",
        action="store_true",
        help="Embed full Base64 audio directly inside the generated HTML player for standalone offline playback.",
    )
    parser.add_argument(
        "--gdrive",
        action="store_true",
        help="Automatically upload rendered audiobook files and HTML player to Google Drive.",
    )
    parser.add_argument(
        "--gdrive-folder",
        default=None,
        help="Google Drive destination folder ID or folder name.",
    )
    parser.add_argument(
        "--audition",
        "--preview",
        action="store_true",
        help="Synthesize and play/save an audition sample clip of the manuscript's opening prose without rendering the full book.",
    )
    parser.add_argument(
        "--max-chunk-chars",
        type=int,
        default=550,
        help="Maximum characters per atomic synthesis chunk (default: 550).",
    )

    return parser


def run_pipeline(args: argparse.Namespace) -> str:
    """Execute the end-to-end audiobook synthesis protocol or Web UI server."""
    if args.web or not args.target:
        print_banner()
        start_web_server(port=args.port)
        return ""

    start_time = time.time()
    print_banner()

    # 1. Manuscript Ingestion
    print(f"{BOLD}[1/5] Ingesting Manuscript Target:{RESET} {CYAN}{args.target}{RESET}")
    doc: ParsedDocument = DocumentParser.parse_target(
        args.target,
        title=args.title,
        author=args.author,
    )

    print(f"  {DIM}▸ Title:{RESET}  {BOLD}{doc.title}{RESET}")
    print(f"  {DIM}▸ Author:{RESET} {BOLD}{doc.author}{RESET}")
    print(f"  {DIM}▸ Source:{RESET} {doc.source_format.upper()} ({len(doc.chapters)} chapters detected)")
    if doc.source_url:
        print(f"  {DIM}▸ Source URL:{RESET} {doc.source_url}")

    # 2. Voice & Pacing Profile Resolution
    base_profile: VoiceProfile = VOICE_PROFILES[args.profile]
    pacing_mode = PacingMode(args.pacing) if args.pacing else base_profile.pacing_mode
    pacing_config = PACING_PRESETS[pacing_mode]
    selected_voice = args.voice or base_profile.voice

    active_profile = VoiceProfile(
        name=base_profile.name,
        voice=selected_voice,
        description=base_profile.description,
        pacing_mode=pacing_mode,
        speed=args.speed,
        pacing=pacing_config,
        system_tone=base_profile.system_tone,
        character_voices=dict(base_profile.character_voices),
    )

    print(f"\n{BOLD}[2/5] Voice Deck Configuration:{RESET}")
    print(f"  {DIM}▸ Profile Preset:{RESET} {MAGENTA}{active_profile.name}{RESET}")
    print(f"  {DIM}▸ Primary Voice:{RESET}  {GREEN}{active_profile.voice}{RESET}")
    print(f"  {DIM}▸ Pacing Mode:{RESET}    {YELLOW}{pacing_mode.value}{RESET}")
    print(f"  {DIM}▸ Playback Speed:{RESET} {args.speed:.2f}x")
    print(f"  {DIM}▸ Crossfade Gap:{RESET}  {pacing_config.crossfade_ms}ms")

    # 3. Narrative Chunking & Prosody Direction
    print(f"\n{BOLD}[3/5] Segmenting & Prosody Direction:{RESET}")
    chunker = NarrativeChunker(
        max_chunk_chars=args.max_chunk_chars,
        pacing_config=pacing_config,
    )
    prosody_director = ProsodyDirector(active_profile)

    all_chunks = []
    total_words = 0

    for chap in doc.chapters:
        chap_title = chap.title or f"Chapter {chap.chapter_num}"
        chap_content = chap.content.strip()
        chap_text = f"# {chap_title}\n\n{chap_content}"
        chap_chunks = chunker.chunk_text(chap_text, default_voice=selected_voice)
        conditioned_chunks = prosody_director.process_chunks(chap_chunks)
        all_chunks.extend(conditioned_chunks)
        chap_words = sum(c.word_count for c in conditioned_chunks)
        total_words += chap_words
        print(f"  {DIM}▸ [{chap_title}]:{RESET} {len(conditioned_chunks)} audio segments ({chap_words} words)")

    total_est_duration_sec = sum(c.estimated_duration_sec for c in all_chunks) / args.speed
    est_min = total_est_duration_sec / 60.0
    print(f"  {DIM}▸ Total Volume:{RESET} {BOLD}{len(all_chunks)} chunks, {total_words} words, ~{est_min:.1f} minutes estimated audio.{RESET}")

    if args.dry_run:
        print(f"\n{YELLOW}[DRY RUN COMPLETE]{RESET} Manuscript structure verified. No neural audio synthesized.")
        return ""

    if getattr(args, "audition", False):
        print(f"\n{BOLD}[AUDITION] Synthesizing opening manuscript excerpt...{RESET}")
        sample_chunk = all_chunks[0] if all_chunks else None
        if not sample_chunk:
            print(f"  {YELLOW}No prose content found to audition.{RESET}")
            return ""
        print(f"  {DIM}▸ Voice:{RESET}       {GREEN}{selected_voice}{RESET}")
        print(f"  {DIM}▸ Sample Text:{RESET} \"{sample_chunk.text[:140]}...\"")
        engine = get_voice_engine(backend=args.backend, default_voice=selected_voice)
        os.makedirs(args.output_dir, exist_ok=True)
        audition_out = os.path.join(args.output_dir, f"audition_{selected_voice}.wav")
        engine.synthesize_chunk(sample_chunk, audition_out)
        print(f"  {GREEN}✔ Audition sample rendered to:{RESET} {audition_out}\n")
        return audition_out

    # 4. Voice Engine Resolution & Waveform Synthesis
    backend_choice = "mock" if args.mock else args.backend
    print(f"\n{BOLD}[4/5] Neural Waveform Generation & Zero-Crossing Stitching:{RESET}")
    print(f"  {CYAN}⚡ Initializing Backend: {backend_choice.upper()} ({args.workers} workers)...{RESET}")
    
    voice_engine: BaseVoiceEngine = get_voice_engine(
        backend=backend_choice,
        default_voice=selected_voice,
    )

    stitcher = AudioStitcher(
        voice_engine=voice_engine,
        pacing_config=pacing_config,
        sample_rate=DEFAULT_SAMPLE_RATE,
    )

    os.makedirs(args.output_dir, exist_ok=True)
    temp_master_wav = os.path.join(args.output_dir, "_master_assembled.wav")

    def on_progress(completed_idx: int, total_count: int, chunk):
        render_progress_bar(completed_idx + 1, total_count, prefix="Synthesizing")

    stitched_result = stitcher.assemble_chunks(
        chunks=all_chunks,
        output_wav_path=temp_master_wav,
        max_workers=args.workers,
        normalize=True,
        progress_callback=on_progress,
    )

    # 5. Format Encoding, Speed Scaling & Metadata Tagging
    print(f"\n{BOLD}[5/5] Final Container Mastering & Chapter Embedding:{RESET}")
    fmt = AudioFormat(args.output_format)
    
    if args.output_name:
        final_filename = args.output_name
    else:
        safe_title = "".join(c if c.isalnum() or c in "._-" else "_" for c in doc.title.lower())
        final_filename = f"{safe_title}.{fmt.value}"

    final_output_path = os.path.join(args.output_dir, final_filename)

    outputs = AudioExporter.export(
        stitched_result=stitched_result,
        output_path=final_output_path,
        output_format=fmt,
        speed=args.speed,
        normalize_loudness=not args.no_normalize,
        title=doc.title,
        author=doc.author,
        series=args.series,
        year=args.year,
        generate_player=not args.no_player,
        embed_player_audio=args.embed_player_audio,
    )

    if os.path.exists(temp_master_wav) and final_output_path != temp_master_wav:
        os.remove(temp_master_wav)

    elapsed = time.time() - start_time
    file_size_mb = os.path.getsize(final_output_path) / (1024.0 * 1024.0)

    print(f"\n{GREEN}{BOLD}══════════════════════════════════════════════════════════════════════{RESET}")
    print(f"{GREEN}{BOLD}✔ AUDIOBOOK MASTER RENDERED SUCCESSFULLY{RESET}")
    print(f"  {DIM}▸ Audio Master:{RESET}   {BOLD}{final_output_path}{RESET}")
    print(f"  {DIM}▸ File Size:{RESET}      {file_size_mb:.2f} MB")
    print(f"  {DIM}▸ Audio Length:{RESET}   {stitched_result.duration_sec / 60.0:.2f} minutes")
    if "player" in outputs:
        print(f"  {DIM}▸ HTML Player:{RESET}    {CYAN}{outputs['player']}{RESET}")
    print(f"  {DIM}▸ Render Time:{RESET}    {elapsed:.2f} seconds ({len(all_chunks)/max(0.1, elapsed):.1f} chunks/sec)")

    # 6. Google Drive Cloud Upload
    if args.gdrive:
        print(f"\n{BOLD}[CLOUD] Uploading Assets to Google Drive:{RESET}")
        files_to_upload = [v for k, v in outputs.items() if k != "index"]
        try:
            drive_results = AudioExporter.upload_to_gdrive(
                file_paths=files_to_upload,
                parent_folder_id=args.gdrive_folder if (args.gdrive_folder and len(args.gdrive_folder) > 15) else None,
                folder_name=args.gdrive_folder if (args.gdrive_folder and len(args.gdrive_folder) <= 15) else f"{doc.author} - {doc.title}",
            )
            for res in drive_results:
                if res.get("status") == "UPLOADED":
                    print(f"  {GREEN}✔{RESET} {res['file_name']} -> {CYAN}{res.get('url', res.get('file_id'))}{RESET}")
                else:
                    print(f"  {YELLOW}⚠{RESET} {res['file_name']} -> {res.get('error', 'Upload error')}")
        except Exception as e:
            print(f"  {YELLOW}⚠ Google Drive upload failed: {e}{RESET}")

    print(f"{GREEN}{BOLD}══════════════════════════════════════════════════════════════════════{RESET}\n")

    return final_output_path


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        run_pipeline(args)
    except Exception as e:
        print(f"\n\033[91m{BOLD}CRITICAL AUDIO DECK FAULT:{RESET} {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
