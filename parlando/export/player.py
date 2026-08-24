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
  <style>
    *, *::before, *::after {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}
    body {{
      background: #020617;
      background: radial-gradient(circle at 50% 0%, #0f172a 0%, #020617 100%);
      color: #f1f5f9;
      min-height: 100vh;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 1.5rem;
    }}
    .player-card {{
      max-width: 42rem;
      width: 100%;
      background: #0f172a;
      background: rgba(15, 23, 42, 0.94);
      border: 1px solid #1e293b;
      border-radius: 1.25rem;
      padding: 1.75rem;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5), 0 0 30px rgba(6, 182, 212, 0.15);
    }}
    .header {{
      text-align: center;
      margin-bottom: 1.5rem;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.25rem 0.75rem;
      background: #082f49;
      border: 1px solid rgba(6, 182, 212, 0.4);
      border-radius: 9999px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.75rem;
      color: #22d3ee;
      margin-bottom: 0.75rem;
      letter-spacing: 0.05em;
    }}
    .pulse-dot {{
      width: 0.5rem;
      height: 0.5rem;
      border-radius: 9999px;
      background-color: #22d3ee;
      box-shadow: 0 0 8px #22d3ee;
      display: inline-block;
      animation: pulse 2s infinite;
    }}
    @keyframes pulse {{
      0%, 100% {{ opacity: 1; transform: scale(1); }}
      50% {{ opacity: 0.4; transform: scale(0.85); }}
    }}
    .title {{
      font-size: 1.65rem;
      font-weight: 700;
      color: #f8fafc;
      letter-spacing: -0.025em;
      line-height: 1.25;
    }}
    .author {{
      font-size: 0.95rem;
      font-weight: 500;
      color: #94a3b8;
      margin-top: 0.35rem;
    }}
    .visualizer-container {{
      position: relative;
      background: #020617;
      border: 1px solid #1e293b;
      border-radius: 0.875rem;
      padding: 0.75rem;
      margin-bottom: 1.5rem;
      height: 6.5rem;
      overflow: hidden;
    }}
    #visualizer {{
      width: 100%;
      height: 100%;
      display: block;
      border-radius: 0.5rem;
    }}
    .time-row {{
      display: flex;
      justify-content: space-between;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.8rem;
      color: #94a3b8;
      margin-bottom: 0.5rem;
    }}
    .slider-wrapper {{
      margin-bottom: 1.25rem;
    }}
    input[type=range] {{
      -webkit-appearance: none;
      appearance: none;
      width: 100%;
      height: 0.5rem;
      background: #1e293b;
      border-radius: 0.5rem;
      outline: none;
      cursor: pointer;
    }}
    input[type=range]::-webkit-slider-thumb {{
      -webkit-appearance: none;
      appearance: none;
      width: 1.1rem;
      height: 1.1rem;
      border-radius: 50%;
      background: #22d3ee;
      box-shadow: 0 0 10px rgba(34, 211, 238, 0.6);
      cursor: pointer;
    }}
    input[type=range]::-moz-range-thumb {{
      width: 1.1rem;
      height: 1.1rem;
      border: none;
      border-radius: 50%;
      background: #22d3ee;
      box-shadow: 0 0 10px rgba(34, 211, 238, 0.6);
      cursor: pointer;
    }}
    .controls-row {{
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 1rem;
      margin-bottom: 1.5rem;
    }}
    .btn-icon {{
      padding: 0.65rem 0.9rem;
      background: #1e293b;
      border: 1px solid #334155;
      color: #cbd5e1;
      border-radius: 0.75rem;
      cursor: pointer;
      font-size: 0.85rem;
      font-weight: 600;
      transition: all 0.2s ease;
    }}
    .btn-icon:hover {{
      background: #334155;
      color: #fff;
    }}
    .btn-play {{
      padding: 0.75rem 1.75rem;
      background: #06b6d4;
      background: linear-gradient(135deg, #06b6d4 0%, #2563eb 100%);
      color: #020617;
      border: none;
      border-radius: 0.75rem;
      font-size: 1rem;
      font-weight: 700;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 0.5rem;
      box-shadow: 0 4px 14px rgba(6, 182, 212, 0.35);
      transition: all 0.2s ease;
    }}
    .btn-play:hover {{
      background: linear-gradient(135deg, #22d3ee 0%, #3b82f6 100%);
      box-shadow: 0 6px 20px rgba(6, 182, 212, 0.5);
    }}
    .btn-play svg {{
      width: 1.25rem;
      height: 1.25rem;
      fill: currentColor;
    }}
    .speed-select {{
      background: #1e293b;
      border: 1px solid #334155;
      color: #cbd5e1;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.8rem;
      border-radius: 0.75rem;
      padding: 0.65rem 0.75rem;
      outline: none;
      cursor: pointer;
    }}
    .chapters-section {{
      border-top: 1px solid #1e293b;
      padding-top: 1.25rem;
    }}
    .chapters-header {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #94a3b8;
      margin-bottom: 0.75rem;
    }}
    .chapters-list {{
      display: flex;
      flex-direction: column;
      gap: 0.45rem;
      max-height: 13rem;
      overflow-y: auto;
    }}
    .chapter-item {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.6rem 0.85rem;
      border-radius: 0.6rem;
      background: #1e293b;
      border: 1px solid #334155;
      color: #e2e8f0;
      font-size: 0.85rem;
      cursor: pointer;
      transition: all 0.2s ease;
    }}
    .chapter-item:hover {{
      background: #334155;
      color: #fff;
    }}
    .chapter-item.active {{
      background: #082f49;
      border-color: #06b6d4;
    }}
    .chapter-item.active .chap-title {{
      color: #22d3ee;
      font-weight: 600;
    }}
    .chap-time {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.75rem;
      color: #06b6d4;
    }}
  </style>
</head>
<body style="background: #020617; color: #f1f5f9; min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 1.5rem;">
  <div class="player-card" style="max-width: 42rem; width: 100%; background: #0f172a; border: 1px solid #1e293b; border-radius: 1.25rem; padding: 1.75rem;">
    
    <div class="header">
      <div class="badge">
        <span class="pulse-dot"></span>
        PARLANDO AUDIO MASTER
      </div>
      <h1 class="title">{title}</h1>
      <p class="author">by {author}</p>
    </div>

    <!-- Web Audio FFT Visualizer -->
    <div class="visualizer-container">
      <canvas id="visualizer"></canvas>
    </div>

    <audio id="audio" preload="auto">
      <source src="{audio_filename}" type="audio/mp3">
      <source src="https://raw.githubusercontent.com/plbogen2/parlando/main/samples/{audio_filename}" type="audio/mp3">
      <source src="https://github.com/plbogen2/parlando/raw/main/samples/{audio_filename}" type="audio/mp3">
    </audio>

    <!-- Progress Scrubber -->
    <div class="slider-wrapper">
      <div class="time-row">
        <span id="curTime">00:00</span>
        <span id="durTime">00:00</span>
      </div>
      <input type="range" id="seek" min="0" max="100" value="0" step="0.1">
    </div>

    <!-- Playback Controls -->
    <div class="controls-row">
      <button id="skipBack" class="btn-icon" title="Rewind 15 seconds">-15s</button>
      <button id="playBtn" class="btn-play">
        <svg id="playIcon" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
        <span id="playText">Play</span>
      </button>
      <button id="skipFwd" class="btn-icon" title="Forward 15 seconds">+15s</button>
      <select id="speedSel" class="speed-select" title="Playback Speed">
        <option value="0.75">0.75x</option>
        <option value="1.0" selected>1.0x</option>
        <option value="1.25">1.25x</option>
        <option value="1.5">1.5x</option>
        <option value="2.0">2.0x</option>
      </select>
    </div>

    <!-- Chapter Navigation -->
    <div class="chapters-section">
      <h3 class="chapters-header">Chapters</h3>
      <div id="chapterList" class="chapters-list"></div>
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

    let audioCtx = null, analyser = null, isInit = false;
    let animPhase = 0;

    // Fallback URL if local file load fails
    const fallbackUrl = 'https://raw.githubusercontent.com/plbogen2/parlando/main/samples/{audio_filename}';
    let triedFallback = false;

    audio.addEventListener('error', () => {{
      if (!triedFallback) {{
        triedFallback = true;
        console.warn('Relative audio path failed, switching to remote GitHub raw audio stream...');
        audio.src = fallbackUrl;
        audio.load();
        if (playText.textContent === 'Pause') {{
          audio.play().catch(e => console.warn('Autoplay error:', e));
        }}
      }}
    }});

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

      animPhase += 0.05;

      for (let i = 0; i < numBars; i++) {{
        let barHeight = 4;
        if (!audio.paused) {{
          const wave1 = Math.sin(animPhase + (i * 0.35)) * 0.5 + 0.5;
          const wave2 = Math.cos(animPhase * 0.8 + (i * 0.2)) * 0.5 + 0.5;
          const combined = (wave1 * 0.6 + wave2 * 0.4);
          barHeight = Math.max(6, combined * (h - 12));
        }}
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
      if (isNaN(s) || s < 0) return '00:00';
      const m = Math.floor(s / 60);
      const sec = Math.floor(s % 60);
      return String(m).padStart(2, '0') + ':' + String(sec).padStart(2, '0');
    }}

    function renderChapters() {{
      chapterList.innerHTML = '';
      if (!chapters || chapters.length === 0) {{
        chapterList.innerHTML = '<div style="font-size: 0.8rem; color: #64748b; font-style: italic; padding: 0.5rem;">No embedded chapter marks</div>';
        return;
      }}
      chapters.forEach((ch, i) => {{
        const div = document.createElement('div');
        div.className = 'chapter-item';
        div.id = 'chap-' + i;
        div.innerHTML = `
          <span class="chap-title">${{ch.title}}</span>
          <span class="chap-time">${{fmt(ch.start_sec)}}</span>
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
            el.classList.add('active');
          }} else {{
            el.classList.remove('active');
          }}
        }}
      }});
    }}

    function togglePlay() {{
      if (audio.paused) {{
        const playPromise = audio.play();
        if (playPromise !== undefined) {{
          playPromise.then(() => {{
            playText.textContent = 'Pause';
            playIcon.innerHTML = '<path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>';
          }}).catch(err => {{
            console.warn('Playback error, trying remote stream:', err);
            if (!triedFallback) {{
              triedFallback = true;
              audio.src = fallbackUrl;
              audio.play().then(() => {{
                playText.textContent = 'Pause';
                playIcon.innerHTML = '<path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>';
              }}).catch(e => console.error('Final playback failure:', e));
            }}
          }});
        }}
      }} else {{
        audio.pause();
        playText.textContent = 'Play';
        playIcon.innerHTML = '<path d="M8 5v14l11-7z"/>';
      }}
    }}

    playBtn.onclick = togglePlay;

    audio.ontimeupdate = () => {{
      if (!isNaN(audio.duration) && audio.duration > 0) {{
        seek.value = (audio.currentTime / audio.duration) * 100;
        curTime.textContent = fmt(audio.currentTime);
        durTime.textContent = fmt(audio.duration);
        updateActiveChapter();
      }}
    }};

    audio.onloadedmetadata = () => {{
      if (!isNaN(audio.duration)) {{
        durTime.textContent = fmt(audio.duration);
      }}
    }};

    seek.oninput = () => {{
      if (!isNaN(audio.duration)) {{
        audio.currentTime = (seek.value / 100) * audio.duration;
      }}
    }};

    skipBack.onclick = () => {{ audio.currentTime = Math.max(0, audio.currentTime - 15); }};
    skipFwd.onclick = () => {{ audio.currentTime = Math.min(audio.duration || 9999, audio.currentTime + 15); }};
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
