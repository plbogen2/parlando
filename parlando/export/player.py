"""Standalone Single-File HTML5 Audio Player Generator with Web Audio API FFT Spectrum Visualizer."""

import json
import os
from typing import List, Optional
from parlando.core.stitcher import ChapterTimepoint


class HTMLPlayerGenerator:
    """Generates a standalone, zero-dependency HTML5 audio player for rendered audiobooks."""

    @classmethod
    def generate_player_html(
        cls,
        title: str,
        author: str,
        audio_filename: str,
        chapter_timepoints: Optional[List[ChapterTimepoint]] = None,
    ) -> str:
        chapters_data = []
        if chapter_timepoints:
            for tp in chapter_timepoints:
                chapters_data.append({
                    "title": tp.title,
                    "start_sec": tp.start_ms / 1000.0,
                    "end_sec": tp.end_ms / 1000.0,
                    "chapter_index": tp.chapter_index,
                })

        chapters_json = json.dumps(chapters_data)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} - Parlando Audiobook Player</title>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css">
  <style>
    body {{
      background: radial-gradient(circle at 50% 0%, #0f172a 0%, #020617 100%);
      min-height: 100vh;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }}
    .glow-cyan {{
      box-shadow: 0 0 25px rgba(6, 182, 212, 0.15);
    }}
    .glow-cyan:hover {{
      box-shadow: 0 0 35px rgba(6, 182, 212, 0.3);
    }}
  </style>
</head>
<body class="text-slate-100 flex items-center justify-center p-4 min-h-screen">
  <div class="max-w-2xl w-full bg-slate-900/90 backdrop-blur-xl border border-slate-800 rounded-2xl p-6 glow-cyan shadow-2xl">
    
    <div class="text-center mb-6">
      <div class="inline-flex items-center gap-2 px-3 py-1 bg-cyan-950/80 border border-cyan-500/30 rounded-full text-xs font-mono text-cyan-400 mb-3">
        <span class="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></span>
        PARLANDO AUDIO MASTER
      </div>
      <h1 class="text-2xl font-bold text-slate-100 tracking-tight">{title}</h1>
      <p class="text-sm font-medium text-slate-400 mt-1">by {author}</p>
    </div>

    <!-- Web Audio FFT Visualizer -->
    <div class="relative bg-slate-950/80 border border-slate-800/80 rounded-xl p-3 mb-6">
      <canvas id="visualizer" class="w-full h-24 rounded-lg block"></canvas>
    </div>

    <audio id="audio" src="{audio_filename}" preload="metadata"></audio>

    <!-- Progress Scrubber -->
    <div class="mb-4">
      <div class="flex justify-between text-xs font-mono text-slate-400 mb-1">
        <span id="curTime">00:00</span>
        <span id="durTime">00:00</span>
      </div>
      <input type="range" id="seek" min="0" max="100" value="0" step="0.1"
             class="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-400">
    </div>

    <!-- Playback Controls -->
    <div class="flex items-center justify-center gap-4 mb-6">
      <button id="skipBack" class="p-2.5 bg-slate-800/80 hover:bg-slate-700 text-slate-300 rounded-xl transition text-sm">
        -15s
      </button>
      <button id="playBtn" class="px-6 py-3 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-slate-950 font-bold rounded-xl shadow-lg transition flex items-center gap-2 text-base">
        <svg id="playIcon" class="w-5 h-5 fill-current" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
        <span id="playText">Play</span>
      </button>
      <button id="skipFwd" class="p-2.5 bg-slate-800/80 hover:bg-slate-700 text-slate-300 rounded-xl transition text-sm">
        +15s
      </button>
      <select id="speedSel" class="bg-slate-800 border border-slate-700 text-slate-300 text-xs font-mono rounded-xl px-2.5 py-2.5 outline-none">
        <option value="0.75">0.75x</option>
        <option value="1.0" selected>1.0x</option>
        <option value="1.25">1.25x</option>
        <option value="1.5">1.5x</option>
        <option value="2.0">2.0x</option>
      </select>
    </div>

    <!-- Chapter Navigation -->
    <div class="border-t border-slate-800/80 pt-4">
      <h3 class="text-xs font-mono uppercase tracking-wider text-slate-400 mb-3">Chapters</h3>
      <div id="chapterList" class="space-y-1.5 max-h-48 overflow-y-auto pr-1"></div>
    </div>

  </div>

  <script>
    const chapters = {chapters_json};
    const audio = document.getElementById('audio');
    const playBtn = document.getElementById('playBtn');
    const playIcon = document.getElementById('playIcon');
    const playText = document.getElementById('playText');
    const seek = document.getElementById('seek');
    const curTime = document.getElementById('curTime');
    const durTime = document.getElementById('durTime');
    const skipBack = document.getElementById('skipBack');
    const skipFwd = document.getElementById('skipFwd');
    const speedSel = document.getElementById('speedSel');
    const chapterList = document.getElementById('chapterList');
    const canvas = document.getElementById('visualizer');
    const ctx = canvas.getContext('2d');

    let audioCtx, analyser, source, isInit = false;

    function initAudio() {{
      if (isInit) return;
      try {{
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioCtx.createAnalyser();
        analyser.fftSize = 64;
        analyser.smoothingTimeConstant = 0.8;
        source = audioCtx.createMediaElementSource(audio);
        source.connect(analyser);
        analyser.connect(audioCtx.destination);
        isInit = true;
      }} catch (e) {{
        console.warn("AudioContext setup failed:", e);
      }}
    }}

    function resizeCanvas() {{
      canvas.width = canvas.parentElement.clientWidth * window.devicePixelRatio;
      canvas.height = canvas.parentElement.clientHeight * window.devicePixelRatio;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    }}
    window.addEventListener('resize', resizeCanvas);
    resizeCanvas();

    function drawVisualizer() {{
      requestAnimationFrame(drawVisualizer);
      const w = canvas.width / window.devicePixelRatio;
      const h = canvas.height / window.devicePixelRatio;
      ctx.clearRect(0, 0, w, h);

      const numBars = 36;
      const barWidth = (w / numBars) - 2;

      let freqData = new Uint8Array(32);
      if (analyser && !audio.paused) {{
        analyser.getByteFrequencyData(freqData);
      }}

      for (let i = 0; i < numBars; i++) {{
        const fIdx = Math.floor((i / numBars) * freqData.length);
        const val = freqData[fIdx] || 0;
        const barHeight = audio.paused ? 4 : Math.max(4, (val / 255) * h * 0.9);
        const x = i * (barWidth + 2);
        const y = (h - barHeight) / 2;

        const grad = ctx.createLinearGradient(0, y, 0, y + barHeight);
        grad.addColorStop(0, '#22d3ee');
        grad.addColorStop(1, '#0284c7');
        ctx.fillStyle = grad;
        ctx.fillRect(x, y, barWidth, barHeight);
      }}
    }}
    drawVisualizer();

    function fmt(s) {{
      const m = Math.floor(s / 60);
      const sec = Math.floor(s % 60);
      return String(m).padStart(2, '0') + ':' + String(sec).padStart(2, '0');
    }}

    function renderChapters() {{
      chapterList.innerHTML = '';
      if (!chapters || chapters.length === 0) {{
        chapterList.innerHTML = '<div class="text-xs text-slate-500 italic">No embedded chapter marks</div>';
        return;
      }}
      chapters.forEach((ch, i) => {{
        const div = document.createElement('div');
        div.className = 'flex items-center justify-between p-2 rounded-lg bg-slate-800/40 hover:bg-slate-800/80 cursor-pointer text-xs transition border border-slate-800/40';
        div.id = 'chap-' + i;
        div.innerHTML = `
          <span class="font-medium text-slate-200">${{ch.title}}</span>
          <span class="font-mono text-cyan-400 text-xs">${{fmt(ch.start_sec)}}</span>
        `;
        div.onclick = () => {{
          audio.currentTime = ch.start_sec;
          if (audio.paused) togglePlay();
        }};
        chapterList.appendChild(div);
      }});
    }}
    renderChapters();

    function updateActiveChapter() {{
      const t = audio.currentTime;
      chapters.forEach((ch, i) => {{
        const el = document.getElementById('chap-' + i);
        if (el) {{
          if (t >= ch.start_sec && t < (ch.end_sec || Infinity)) {{
            el.classList.add('border-cyan-500/50', 'bg-cyan-950/30');
          }} else {{
            el.classList.remove('border-cyan-500/50', 'bg-cyan-950/30');
          }}
        }}
      }});
    }}

    function togglePlay() {{
      initAudio();
      if (audioCtx && audioCtx.state === 'suspended') audioCtx.resume();
      if (audio.paused) {{
        audio.play();
        playText.textContent = 'Pause';
        playIcon.innerHTML = '<path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>';
      }} else {{
        audio.pause();
        playText.textContent = 'Play';
        playIcon.innerHTML = '<path d="M8 5v14l11-7z"/>';
      }}
    }}

    playBtn.onclick = togglePlay;

    audio.ontimeupdate = () => {{
      if (!isNaN(audio.duration)) {{
        seek.value = (audio.currentTime / audio.duration) * 100;
        curTime.textContent = fmt(audio.currentTime);
        durTime.textContent = fmt(audio.duration);
        updateActiveChapter();
      }}
    }};

    seek.oninput = () => {{
      if (!isNaN(audio.duration)) {{
        audio.currentTime = (seek.value / 100) * audio.duration;
      }}
    }};

    skipBack.onclick = () => {{ audio.currentTime = Math.max(0, audio.currentTime - 15); }};
    skipFwd.onclick = () => {{ audio.currentTime = Math.min(audio.duration, audio.currentTime + 15); }};
    speedSel.onchange = () => {{ audio.playbackRate = parseFloat(speedSel.value); }};
  </script>
</body>
</html>
"""

    @classmethod
    def write_player_file(
        cls,
        output_html_path: str,
        title: str,
        author: str,
        audio_filename: str,
        chapter_timepoints: Optional[List[ChapterTimepoint]] = None,
    ) -> str:
        html = cls.generate_player_html(title, author, audio_filename, chapter_timepoints)
        os.makedirs(os.path.dirname(os.path.abspath(output_html_path)), exist_ok=True)
        with open(output_html_path, "w", encoding="utf-8") as f:
            f.write(html)
        return output_html_path
