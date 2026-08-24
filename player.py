"""HTML5 Audio Player generator for standalone and web-hosted audiobook playback."""

import base64
import json
import os
from typing import Dict, List, Optional
from .stitcher import StitchedAudioResult


class HTMLPlayerGenerator:
    """Generates modern, interactive HTML5 player consoles with chapter navigation & waveforms."""

    @classmethod
    def generate(
        cls,
        stitched_result: StitchedAudioResult,
        audio_file_path: str,
        output_html_path: str,
        title: str,
        author: str,
        embed_audio: bool = False,
        voice_info: str = "Neural TTS",
    ) -> str:
        """Generate a self-contained HTML audio player for the audiobook."""
        chapters_data = []

        if stitched_result.chapter_timepoints:
            for idx, ch in enumerate(stitched_result.chapter_timepoints):
                m = int(ch.start_time_sec // 60)
                s = int(ch.start_time_sec % 60)
                time_str = f"{m:02d}:{s:02d}"
                dur = ch.end_time_sec - ch.start_time_sec
                dur_m = int(dur // 60)
                dur_s = int(dur % 60)
                dur_str = f"{dur_m:02d}:{dur_s:02d}"

                chapters_data.append({
                    "index": idx,
                    "title": ch.title,
                    "start_sec": ch.start_time_sec,
                    "timestamp": time_str,
                    "duration": dur_str,
                    "duration_sec": dur,
                })
        else:
            total_sec = stitched_result.duration_sec
            m = int(total_sec // 60)
            s = int(total_sec % 60)
            chapters_data.append({
                "index": 0,
                "title": title,
                "start_sec": 0,
                "timestamp": "00:00",
                "duration": f"{m:02d}:{s:02d}",
                "duration_sec": total_sec,
            })

        # Resolve audio source
        audio_src = ""
        if embed_audio and os.path.exists(audio_file_path):
            with open(audio_file_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            ext = os.path.splitext(audio_file_path)[1].lower().replace(".", "")
            mime = f"audio/{ext}" if ext in ["mp3", "wav", "aac", "flac"] else "audio/mp4"
            audio_src = f"data:{mime};base64,{b64}"
        else:
            # Relative path for standard web hosting
            audio_src = os.path.basename(audio_file_path)

        chapters_json = json.dumps(chapters_data)
        total_duration_min = stitched_result.duration_sec / 60.0

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} // Neural Audiobook Player</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css">
  <style>
    body {{ background-color: #020617; color: #f8fafc; font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }}
    .bg-slate-950 {{ background-color: #020617; }}
    .bg-slate-900 {{ background-color: #0f172a; }}
    .border-slate-800 {{ border-color: #1e293b; }}
    .border-slate-700 {{ border-color: #334155; }}
    .text-slate-400 {{ color: #94a3b8; }}
    .bg-cyan-950 {{ background-color: #083344; }}
    .border-cyan-800 {{ border-color: #155e75; }}
    .border-cyan-500 {{ border-color: #06b6d4; }}
    .text-cyan-300 {{ color: #67e8f9; }}
    .text-cyan-400 {{ color: #22d3ee; }}
    .accent-cyan-400 {{ accent-color: #22d3ee; }}
  </style>
</head>
<body class="bg-slate-950 text-gray-100 font-sans antialiased p-4 min-h-screen flex items-center justify-center">
  <div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-2xl max-w-2xl w-full backdrop-blur-md">
    
    <!-- Header -->
    <div class="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
      <div class="flex items-center space-x-3">
        <div class="w-3 h-3 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_8px_#22d3ee]"></div>
        <div>
          <h1 class="text-base font-bold tracking-wider uppercase text-gray-100 flex items-center gap-2">
            {title}
          </h1>
          <p class="text-xs text-slate-400 font-mono">{author} • {voice_info} • {len(chapters_data)} Chapters</p>
        </div>
      </div>
      <span class="text-xs font-mono px-2.5 py-1 rounded bg-cyan-950/70 text-cyan-300 border border-cyan-800/60">
        {total_duration_min:.1f} MIN
      </span>
    </div>

    <!-- Active Visualizer Bar -->
    <div class="relative bg-black/60 border border-cyan-950 rounded-xl overflow-hidden mb-4 h-24 flex items-center justify-center">
      <canvas id="visualizer" class="w-full h-full"></canvas>
      <div id="status-bar" class="absolute top-2 left-3 text-[10px] font-mono text-cyan-400/90 uppercase tracking-widest pointer-events-none flex items-center gap-2">
        <span class="inline-block w-2 h-2 rounded-full bg-cyan-400 animate-ping"></span>
        <span id="status-text">PLAYER READY // {title.upper()}</span>
      </div>
      <div id="timer-badge" class="absolute bottom-2 right-3 text-[10px] font-mono text-cyan-300 bg-black/70 px-2 py-0.5 rounded border border-cyan-900/50">
        00:00 / 00:00
      </div>
    </div>

    <!-- Chapter Navigation List -->
    <div class="space-y-2 mb-4 max-h-56 overflow-y-auto pr-1" id="chapter-list">
      <!-- Injected dynamically -->
    </div>

    <!-- Main Controller -->
    <div class="bg-slate-950/60 rounded-xl p-4 border border-slate-800/80">
      <div class="flex items-center justify-between mb-2.5">
        <div>
          <div id="active-title" class="font-bold text-xs text-gray-200">{chapters_data[0]['title']}</div>
          <div id="active-desc" class="text-[10px] text-slate-400 font-mono mt-0.5">EBU R128 Broadcast Normalized • Studio Master</div>
        </div>
        
        <!-- Speed Buttons -->
        <div class="flex items-center space-x-1">
          <button onclick="changeSpeed(0.85)" class="speed-btn px-2 py-0.5 text-[10px] rounded bg-slate-900 border border-slate-700 hover:border-cyan-500 font-mono">0.85x</button>
          <button onclick="changeSpeed(1.0)" class="speed-btn active px-2 py-0.5 text-[10px] rounded bg-cyan-950 border border-cyan-500 text-cyan-300 font-mono">1.0x</button>
          <button onclick="changeSpeed(1.15)" class="speed-btn px-2 py-0.5 text-[10px] rounded bg-slate-900 border border-slate-700 hover:border-cyan-500 font-mono">1.15x</button>
          <button onclick="changeSpeed(1.3)" class="speed-btn px-2 py-0.5 text-[10px] rounded bg-slate-900 border border-slate-700 hover:border-cyan-500 font-mono">1.3x</button>
        </div>
      </div>

      <!-- Scrubber -->
      <div class="space-y-1 mb-3">
        <input type="range" id="seek-bar" min="0" max="100" value="0" step="0.1" 
               class="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400">
      </div>

      <div class="flex items-center justify-between pt-1">
        <div class="flex items-center space-x-2.5">
          <button onclick="prevChapter()" title="Previous Chapter" class="p-2 rounded-lg bg-slate-900 border border-slate-800 hover:border-cyan-500 text-xs font-mono text-cyan-300 flex items-center gap-1">
            ⏮ Prev
          </button>

          <button id="main-play-btn" onclick="togglePlay()" class="p-3.5 rounded-full bg-cyan-500 hover:bg-cyan-400 text-black font-bold shadow-[0_0_15px_rgba(34,211,238,0.5)] transition-transform active:scale-95">
            <svg id="play-icon" class="w-4 h-4 fill-current" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
            <svg id="pause-icon" class="w-4 h-4 fill-current hidden" viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>
          </button>

          <button onclick="nextChapter()" title="Next Chapter" class="p-2 rounded-lg bg-slate-900 border border-slate-800 hover:border-cyan-500 text-xs font-mono text-cyan-300 flex items-center gap-1">
            Next ⏭
          </button>
        </div>

        <div class="text-right text-[10px] font-mono text-slate-400">
          <div>FILE: <span class="text-cyan-300 font-bold">{os.path.basename(audio_file_path)}</span></div>
        </div>
      </div>
    </div>

    <audio id="audio-core" preload="auto" src="{audio_src}"></audio>
  </div>

  <script>
    const chapters = {chapters_json};
    let activeIndex = 0;
    const audio = document.getElementById('audio-core');
    const playIcon = document.getElementById('play-icon');
    const pauseIcon = document.getElementById('pause-icon');
    const statusText = document.getElementById('status-text');
    const timerBadge = document.getElementById('timer-badge');
    const activeTitle = document.getElementById('active-title');
    const seekBar = document.getElementById('seek-bar');
    const chapterList = document.getElementById('chapter-list');

    chapters.forEach((ch, idx) => {{
      const card = document.createElement('div');
      card.id = `card-${{idx}}`;
      card.className = `p-2.5 rounded-xl border transition-all cursor-pointer flex items-center justify-between ${{
        idx === 0 
          ? 'bg-cyan-950/40 border-cyan-500 text-cyan-200 shadow-[0_0_10px_rgba(6,182,212,0.15)]' 
          : 'bg-slate-950/40 border-slate-800 text-slate-300 hover:border-cyan-800/80 hover:bg-slate-950/60'
      }}`;
      card.onclick = () => selectChapter(idx);

      card.innerHTML = `
        <div class="flex items-center space-x-3">
          <button class="play-indicator w-6 h-6 rounded-full bg-cyan-900/60 border border-cyan-700/60 flex items-center justify-center text-cyan-300 text-[10px] shadow-inner">
            ${{idx === 0 ? '●' : '▶'}}
          </button>
          <div>
            <div class="font-bold text-xs text-gray-200">${{ch.title}}</div>
            <div class="text-[10px] text-slate-400 font-mono mt-0.5">Starts at ${{ch.timestamp}}</div>
          </div>
        </div>
        <div class="text-right font-mono text-[10px] text-cyan-400/90">
          ${{ch.duration}}
        </div>
      `;
      chapterList.appendChild(card);
    }});

    function formatTime(seconds) {{
      if (isNaN(seconds)) return '00:00';
      const m = Math.floor(seconds / 60);
      const s = Math.floor(seconds % 60);
      return `${{m < 10 ? '0' : ''}}${{m}}:${{s < 10 ? '0' : ''}}${{s}}`;
    }}

    function selectChapter(idx) {{
      activeIndex = idx;
      const ch = chapters[idx];

      chapters.forEach((item, i) => {{
        const el = document.getElementById(`card-${{i}}`);
        if (el) {{
          el.className = 'p-2.5 rounded-xl border transition-all cursor-pointer flex items-center justify-between bg-slate-950/40 border-slate-800 text-slate-300 hover:border-cyan-800/80 hover:bg-slate-950/60';
          el.querySelector('.play-indicator').innerHTML = '▶';
        }}
      }});

      const activeEl = document.getElementById(`card-${{idx}}`);
      if (activeEl) {{
        activeEl.className = 'p-2.5 rounded-xl border transition-all cursor-pointer flex items-center justify-between bg-cyan-950/40 border-cyan-500 text-cyan-200 shadow-[0_0_10px_rgba(6,182,212,0.15)]';
        activeEl.querySelector('.play-indicator').innerHTML = '●';
      }}

      activeTitle.innerText = ch.title;
      audio.currentTime = ch.start_sec;
      audio.play().then(() => {{
        playIcon.classList.add('hidden');
        pauseIcon.classList.remove('hidden');
        statusText.innerText = `STREAMING // ${{ch.title.toUpperCase()}}`;
        startVisualizer();
      }}).catch(e => console.log('Autoplay handled:', e));
    }}

    function togglePlay() {{
      if (audio.paused) {{
        audio.play().then(() => {{
          playIcon.classList.add('hidden');
          pauseIcon.classList.remove('hidden');
          statusText.innerText = `STREAMING // ${{chapters[activeIndex].title.toUpperCase()}}`;
          startVisualizer();
        }}).catch(err => console.error("Playback error:", err));
      }} else {{
        audio.pause();
        playIcon.classList.remove('hidden');
        pauseIcon.classList.add('hidden');
        statusText.innerText = "[PAUSED] — STANDBY";
      }}
    }}

    function prevChapter() {{
      if (activeIndex > 0) selectChapter(activeIndex - 1);
    }}

    function nextChapter() {{
      if (activeIndex < chapters.length - 1) selectChapter(activeIndex + 1);
    }}

    function changeSpeed(speed) {{
      audio.playbackRate = speed;
      document.querySelectorAll('.speed-btn').forEach(b => {{
        if (parseFloat(b.innerText) === speed) {{
          b.className = 'speed-btn active px-2 py-0.5 text-[10px] rounded bg-cyan-950 border border-cyan-500 text-cyan-300 font-mono';
        }} else {{
          b.className = 'speed-btn px-2 py-0.5 text-[10px] rounded bg-slate-900 border border-slate-700 hover:border-cyan-500 font-mono';
        }}
      }});
    }}

    audio.addEventListener('timeupdate', () => {{
      if (!isNaN(audio.duration) && audio.duration > 0) {{
        const pct = (audio.currentTime / audio.duration) * 100;
        seekBar.value = pct;
        timerBadge.innerText = `${{formatTime(audio.currentTime)}} / ${{formatTime(audio.duration)}}`;
        
        for (let i = chapters.length - 1; i >= 0; i--) {{
          if (audio.currentTime >= chapters[i].start_sec) {{
            if (activeIndex !== i) {{
              activeIndex = i;
              activeTitle.innerText = chapters[i].title;
              chapters.forEach((_, k) => {{
                const el = document.getElementById(`card-${{k}}`);
                if (el) {{
                  el.className = k === i 
                    ? 'p-2.5 rounded-xl border transition-all cursor-pointer flex items-center justify-between bg-cyan-950/40 border-cyan-500 text-cyan-200 shadow-[0_0_10px_rgba(6,182,212,0.15)]'
                    : 'p-2.5 rounded-xl border transition-all cursor-pointer flex items-center justify-between bg-slate-950/40 border-slate-800 text-slate-300 hover:border-cyan-800/80 hover:bg-slate-950/60';
                  el.querySelector('.play-indicator').innerHTML = k === i ? '●' : '▶';
                }}
              }});
            }}
            break;
          }}
        }}
      }}
    }});

    seekBar.addEventListener('input', () => {{
      if (!isNaN(audio.duration)) {{
        audio.currentTime = (seekBar.value / 100) * audio.duration;
      }}
    }});

    // Real Web Audio API Frequency Spectrum Visualizer
    const canvas = document.getElementById('visualizer');
    const ctx = canvas.getContext('2d');
    let audioCtx = null;
    let analyser = null;
    let dataArray = null;

    function resizeCanvas() {{
      canvas.width = canvas.parentElement.clientWidth;
      canvas.height = canvas.parentElement.clientHeight;
    }}
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    function initWebAudio() {{
      if (!audioCtx) {{
        try {{
          const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
          if (AudioCtxClass) {{
            audioCtx = new AudioCtxClass();
            analyser = audioCtx.createAnalyser();
            analyser.fftSize = 64;
            analyser.smoothingTimeConstant = 0.8;
            const source = audioCtx.createMediaElementSource(audio);
            source.connect(analyser);
            analyser.connect(audioCtx.destination);
            dataArray = new Uint8Array(analyser.frequencyBinCount);
          }}
        }} catch (e) {{
          console.warn("Web Audio API initialization:", e);
        }}
      }}
      if (audioCtx && audioCtx.state === 'suspended') {{
        audioCtx.resume();
      }}
    }}

    function startVisualizer() {{
      initWebAudio();
      function draw() {{
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        const isPlaying = !audio.paused;
        const numBars = 40;
        const barWidth = canvas.width / numBars;

        if (analyser && isPlaying && dataArray) {{
          analyser.getByteFrequencyData(dataArray);
          for (let i = 0; i < numBars; i++) {{
            const dataIdx = Math.min(dataArray.length - 1, Math.floor((i / numBars) * dataArray.length));
            const val = dataArray[dataIdx] / 255.0;
            const h = Math.max(3, val * (canvas.height * 0.85));
            const x = i * barWidth;
            const y = (canvas.height - h) / 2;

            const grad = ctx.createLinearGradient(0, y, 0, y + h);
            grad.addColorStop(0, '#22d3ee');
            grad.addColorStop(1, '#0891b2');
            ctx.fillStyle = grad;

            ctx.beginPath();
            if (ctx.roundRect) {{
              ctx.roundRect(x + 1, y, Math.max(1, barWidth - 2), h, 2);
            }} else {{
              ctx.rect(x + 1, y, Math.max(1, barWidth - 2), h);
            }}
            ctx.fill();
          }}
        }} else {{
          // Standby baseline
          ctx.fillStyle = '#1e293b';
          for (let i = 0; i < numBars; i++) {{
            const h = 4;
            const x = i * barWidth;
            const y = (canvas.height - h) / 2;
            ctx.fillRect(x + 1, y, Math.max(1, barWidth - 2), h);
          }}
        }}
        requestAnimationFrame(draw);
      }}
      draw();
    }}
    startVisualizer();
    window.addEventListener('click', initWebAudio, {{ once: true }});
    window.addEventListener('keydown', initWebAudio, {{ once: true }});
  </script>
</body>
</html>
"""

        with open(output_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return output_html_path
