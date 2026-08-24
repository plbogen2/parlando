"""Command-Line Interface for Parlando."""

import argparse
import os
import sys
import time

from parlando.config import (
    AudioFormat,
    PACING_PRESETS,
    PacingMode,
    VALID_NEURAL_VOICES,
    VOICE_PROFILES,
)
from parlando.core import normalize_character_input
from parlando.pipeline import AudiobookPipeline, PipelineConfig
from parlando.web import start_web_studio


def create_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="parlando",
        description="Parlando // Studio-Grade Neural Prose & Audiobook Synthesis Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("input", nargs="?", help="Path to manuscript file (.md, .txt, .epub, .pdf, .html) or Web URL (https://...)")
    parser.add_argument("-o", "--output", help="Destination audio master path (.m4b, .mp3, .wav)")
    parser.add_argument("--backend", default="edge", choices=["edge", "openai", "gemini", "mock"], help="Neural voice synthesis backend (default: edge)")
    parser.add_argument("--voice", default="en-US-ChristopherNeural", help="Primary narrator voice (default: en-US-ChristopherNeural)")
    parser.add_argument("--dialogue-voice", help="Global voice override for character dialogue")
    parser.add_argument(
        "-c", "--character",
        action="append",
        dest="characters",
        metavar="SPEC",
        help="Specify character name, gender, and optional voice (e.g. 'Case:male:Puck', 'Linda:female:Aoede', 'Clerk:male')"
    )
    parser.add_argument(
        "--cast",
        help="Path to JSON file or JSON string defining character names, genders, and optional voices"
    )
    parser.add_argument("--pacing", default="normal", choices=[p.value for p in PacingMode], help="Pacing preset (default: normal)")
    parser.add_argument("--speed", type=float, default=1.0, help="Global playback speed multiplier (default: 1.0)")
    parser.add_argument("--format", default="m4b", choices=["m4b", "mp3", "wav"], help="Audio container format (default: m4b)")
    parser.add_argument("--crossfade", type=int, default=35, help="Crossfade overlap in ms (default: 35)")
    parser.add_argument("--model", help="Gemini neural model override (e.g. gemini-2.5-pro-preview-tts)")
    parser.add_argument("--audition", action="store_true", help="Audition mode: synthesize only the first section/excerpt")
    parser.add_argument("--dry-run", action="store_true", help="Inspect and segment manuscript without synthesizing audio")
    parser.add_argument("--no-player", action="store_true", help="Disable generation of standalone HTML5 audio player")
    parser.add_argument("--web", action="store_true", help="Launch the browser studio UI console and REST API daemon")
    parser.add_argument("--port", type=int, default=8765, help="Port for web studio server (default: 8765)")
    parser.add_argument("--host", default="0.0.0.0", help="Host address for web studio server (default: 0.0.0.0)")

    return parser


def main(args=None):
    parser = create_arg_parser()
    parsed = parser.parse_args(args)

    if parsed.web:
        start_web_studio(port=parsed.port, host=parsed.host)
        return 0

    if not parsed.input:
        parser.print_help()
        return 1

    fmt_map = {"m4b": AudioFormat.M4B, "mp3": AudioFormat.MP3, "wav": AudioFormat.WAV}
    audio_format = fmt_map.get(parsed.format.lower(), AudioFormat.M4B)
    pacing_mode = PacingMode(parsed.pacing)

    # Merge character specs from -c / --character and --cast
    cast_input = []
    if parsed.characters:
        cast_input.extend(parsed.characters)
    if parsed.cast:
        cast_input.append(parsed.cast)

    config = PipelineConfig(
        backend=parsed.backend,
        voice=parsed.voice,
        dialogue_voice=parsed.dialogue_voice,
        characters=cast_input if cast_input else None,
        pacing_mode=pacing_mode,
        speed=parsed.speed,
        audio_format=audio_format,
        crossfade_ms=parsed.crossfade,
        audition=parsed.audition,
        model=parsed.model,
        generate_player=not parsed.no_player,
    )

    pipeline = AudiobookPipeline(config)

    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║  PARLANDO // NEURAL PROSE & AUDIOBOOK SYNTHESIS ENGINE               ║")
    print("║  v1.0.0 // Zero-Crossing Direct-to-Waveform Audio Studio             ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")

    if parsed.dry_run:
        from parlando.parsers import DocumentParser
        from parlando.core import GenericSpeakerDetector, NarrativeChunker, SceneAwareVoiceCaster

        doc = DocumentParser.from_file_or_url(parsed.input)
        print(f"\n[DRY RUN] Document: {doc.title} by {doc.author}")
        print(f"  ▸ Total chapters: {doc.total_chapters}")
        print(f"  ▸ Total words:    {doc.total_words}")
        for i, c in enumerate(doc.chapters):
            print(f"    - Chapter {i+1}: {c.title} ({c.word_count} words)")

        chunker = NarrativeChunker()
        detector = GenericSpeakerDetector(predefined_characters=cast_input)
        all_chunks = []
        for chap_idx, chap in enumerate(doc.chapters):
            chap_text = f"# {chap.title}\n\n{chap.content}" if chap.title else chap.content
            all_chunks.extend(chunker.chunk_text(chap_text, chapter_index=chap_idx))
        detector.attribute_chunks(all_chunks)
        voice_map = SceneAwareVoiceCaster.cast_characters(detector.characters, engine_type=parsed.backend, primary_narrator_voice=parsed.voice)

        print("\n[CAST ALLOCATION]")
        print(f"  ▸ Narrator: {voice_map.get('Narrator', parsed.voice)}")
        for char_name, profile in detector.characters.items():
            assigned = voice_map.get(char_name, "Default")
            print(f"  ▸ Character: {char_name:20s} | Gender: {profile.gender:7s} | Lines: {profile.line_count:3d} | Voice: {assigned}")
        return 0

    def _progress_cb(curr, total, sample):
        bar_len = 30
        pct = (curr / max(1, total))
        filled = int(bar_len * pct)
        bar = "█" * filled + "░" * (bar_len - filled)
        sys.stdout.write(f"\r[STREAM] Synthesizing |{bar}| {pct*100:5.1f}% ({curr}/{total})")
        sys.stdout.flush()

    res = pipeline.run(parsed.input, output_path=parsed.output, progress_callback=_progress_cb)
    print("\n\n══════════════════════════════════════════════════════════════════════")
    print("✔ AUDIO MASTER RENDERED SUCCESSFULLY")
    print(f"  ▸ Audio Master:   {res.audio_path}")
    print(f"  ▸ Audio Length:   {res.duration_seconds/60.0:.2f} minutes")
    print(f"  ▸ Total Chunks:   {res.total_chunks}")
    if res.player_path:
        print(f"  ▸ HTML5 Player:   {res.player_path}")
    print(f"  ▸ Render Time:    {res.render_time_seconds:.2f}s")
    if res.characters:
        print("\n  [CAST ALLOCATION]")
        print(f"    - Narrator: {res.voice_map.get('Narrator', parsed.voice)}")
        for char_name, profile in res.characters.items():
            assigned = res.voice_map.get(char_name, "Default")
            print(f"    - {char_name:18s} ({profile.gender:7s}) : {assigned} ({profile.line_count} lines)")
    print("══════════════════════════════════════════════════════════════════════\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
