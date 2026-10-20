"""Generate rich, interactive HTML review tool for the macOS contextual perception dataset."""
from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
from typing import Dict, List, Optional


def build_review_html(pilot_dir: Path) -> str:
    """Build a standalone, responsive, high-aesthetic HTML review tool."""
    screens_dir = pilot_dir / "screens"
    pairs_dir = pilot_dir / "pairs"

    manifest_file = pilot_dir / "manifest.jsonl"
    manifest_records = []
    if manifest_file.exists():
        for line in manifest_file.read_text().splitlines():
            if line.strip():
                manifest_records.append(json.loads(line))

    # Collect screen data
    screens_data = {}
    for screen_path in sorted(screens_dir.glob("*")):
        if not screen_path.is_dir():
            continue
        sid = screen_path.name
        ann_reviewed = screen_path / "annotation.reviewed.json"
        ann_teacher = screen_path / "annotation.teacher.json"
        val_file = screen_path / "validation.json"
        proposals_file = screen_path / "proposals/raw.json"

        ann_data = None
        if ann_reviewed.exists():
            ann_data = json.loads(ann_reviewed.read_text())
        elif ann_teacher.exists():
            ann_data = json.loads(ann_teacher.read_text())

        teacher_data = None
        if ann_teacher.exists():
            teacher_data = json.loads(ann_teacher.read_text())

        val_data = {}
        if val_file.exists():
            val_data = json.loads(val_file.read_text())

        prop_data = {}
        if proposals_file.exists():
            prop_data = json.loads(proposals_file.read_text())

        # Relative paths for images
        screens_data[sid] = {
            "screen_id": sid,
            "annotation": ann_data,
            "teacher_annotation": teacher_data,
            "validation": val_data,
            "proposals": prop_data,
            "image_url": f"../screens/{sid}/source.png",
            "overlay_url": f"../screens/{sid}/proposals/overlay.png",
            "audit_overlay_url": f"../screens/{sid}/audit_overlay.png",
        }

    # Collect pairs data
    pairs_data = {}
    if pairs_dir.exists():
        for p_file in sorted(pairs_dir.glob("*.json")):
            p_data = json.loads(p_file.read_text())
            pairs_data[p_file.stem] = p_data

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>macOS Contextual Screen-Perception Dataset Pilot Reviewer</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #090d16;
      --card-bg: #111827;
      --card-border: #1f293d;
      --accent-blue: #3b82f6;
      --accent-indigo: #6366f1;
      --accent-green: #10b981;
      --accent-amber: #f59e0b;
      --accent-rose: #f43f5e;
      --text-main: #f3f4f6;
      --text-muted: #9ca3af;
      --font-sans: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: var(--bg);
      color: var(--text-main);
      font-family: var(--font-sans);
      display: flex;
      flex-direction: column;
      height: 100vh;
      overflow: hidden;
    }}
    header {{
      background: rgba(17, 24, 39, 0.85);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--card-border);
      padding: 12px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      z-index: 50;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .badge {{
      background: linear-gradient(135deg, var(--accent-indigo), var(--accent-blue));
      padding: 4px 10px;
      border-radius: 9999px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }}
    .app-title {{
      font-size: 17px;
      font-weight: 700;
      letter-spacing: -0.01em;
    }}
    .top-controls {{
      display: flex;
      align-items: center;
      gap: 16px;
    }}
    select, button {{
      background: #1e293b;
      border: 1px solid var(--card-border);
      color: var(--text-main);
      font-family: var(--font-sans);
      font-size: 13px;
      padding: 6px 14px;
      border-radius: 8px;
      cursor: pointer;
      outline: none;
      transition: all 0.2s ease;
    }}
    select:hover, button:hover {{
      border-color: var(--accent-blue);
      background: #273549;
    }}
    .btn-active {{
      background: var(--accent-blue);
      border-color: var(--accent-blue);
      color: white;
    }}
    main {{
      display: grid;
      grid-template-columns: 280px 1fr 420px;
      flex: 1;
      overflow: hidden;
    }}
    /* Left Sidebar */
    .sidebar {{
      background: var(--card-bg);
      border-right: 1px solid var(--card-border);
      overflow-y: auto;
      display: flex;
      flex-direction: column;
    }}
    .sidebar-section {{
      padding: 16px;
      border-bottom: 1px solid var(--card-border);
    }}
    .sidebar-title {{
      font-size: 12px;
      font-weight: 700;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 10px;
    }}
    .screen-item {{
      padding: 10px 14px;
      border-radius: 8px;
      margin-bottom: 6px;
      cursor: pointer;
      background: #161f30;
      border: 1px solid transparent;
      display: flex;
      flex-direction: column;
      gap: 4px;
      transition: all 0.15s ease;
    }}
    .screen-item:hover {{
      background: #1c283f;
      border-color: #2e3e5c;
    }}
    .screen-item.selected {{
      background: #1e2d4a;
      border-color: var(--accent-blue);
    }}
    .screen-item-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .screen-id {{
      font-weight: 600;
      font-size: 13px;
    }}
    .screen-stratum {{
      font-size: 11px;
      color: var(--accent-amber);
      background: rgba(245, 158, 11, 0.1);
      padding: 2px 6px;
      border-radius: 4px;
    }}
    .screen-stats {{
      font-size: 11px;
      color: var(--text-muted);
    }}
    /* Center Stage (Canvas Viewer) */
    .viewport {{
      position: relative;
      background: #060910;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}
    .toolbar {{
      background: #0f172a;
      border-bottom: 1px solid var(--card-border);
      padding: 8px 16px;
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 12px;
    }}
    .toggle-chip {{
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 6px;
      background: #1e293b;
      cursor: pointer;
      user-select: none;
    }}
    .toggle-chip input {{
      cursor: pointer;
    }}
    .canvas-container {{
      position: relative;
      flex: 1;
      overflow: auto;
      padding: 24px;
      display: flex;
      justify-content: center;
      align-items: flex-start;
    }}
    .image-stage {{
      position: relative;
      display: inline-block;
      box-shadow: 0 20px 40px rgba(0,0,0,0.6);
      border-radius: 8px;
      overflow: hidden;
    }}
    .image-stage img {{
      display: block;
      max-width: 100%;
      height: auto;
    }}
    .overlay-svg {{
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      pointer-events: auto;
    }}
    rect.node-box {{
      fill: transparent;
      stroke-width: 2px;
      cursor: pointer;
      transition: all 0.15s ease;
    }}
    rect.node-box:hover {{
      fill: rgba(59, 130, 246, 0.2);
      stroke-width: 3px;
    }}
    rect.node-box.selected {{
      fill: rgba(245, 158, 11, 0.25);
      stroke: #f59e0b !important;
      stroke-width: 3.5px;
    }}
    /* Right Inspector */
    .inspector {{
      background: var(--card-bg);
      border-left: 1px solid var(--card-border);
      overflow-y: auto;
      display: flex;
      flex-direction: column;
    }}
    .inspector-header {{
      padding: 16px;
      border-bottom: 1px solid var(--card-border);
    }}
    .inspector-title {{
      font-size: 15px;
      font-weight: 700;
    }}
    .inspector-content {{
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}
    .card {{
      background: #162032;
      border: 1px solid var(--card-border);
      border-radius: 8px;
      padding: 12px;
    }}
    .card-label {{
      font-size: 11px;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 6px;
    }}
    .prop-row {{
      display: flex;
      justify-content: space-between;
      margin-bottom: 6px;
      font-size: 12px;
    }}
    .prop-key {{
      color: var(--text-muted);
    }}
    .prop-val {{
      font-weight: 600;
      font-family: var(--font-mono);
      color: var(--text-main);
    }}
    .tag {{
      display: inline-block;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
    }}
    .tag-blue {{ background: rgba(59, 130, 246, 0.15); color: #60a5fa; }}
    .tag-green {{ background: rgba(16, 185, 129, 0.15); color: #34d399; }}
    .tag-amber {{ background: rgba(245, 158, 11, 0.15); color: #fbbf24; }}
    .tag-rose {{ background: rgba(244, 63, 94, 0.15); color: #fb7185; }}
    .tag-purple {{ background: rgba(168, 85, 247, 0.15); color: #c084fc; }}
    pre.code-block {{
      background: #0b101b;
      padding: 10px;
      border-radius: 6px;
      font-family: var(--font-mono);
      font-size: 11px;
      color: #93c5fd;
      overflow-x: auto;
      max-height: 180px;
    }}
    .checklist-item {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      padding: 6px 0;
      border-bottom: 1px solid rgba(255,255,255,0.05);
    }}
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <span class="badge">macOS Perception</span>
      <h1 class="app-title">Contextual Screen Dataset Pilot Reviewer</h1>
    </div>
    <div class="top-controls">
      <button id="view-mode-all" class="btn-active" onclick="switchView('screens')">Screens (30)</button>
      <button id="view-mode-pairs" onclick="switchView('pairs')">Before/After Pairs (5)</button>
      <button id="view-mode-metrics" onclick="switchView('metrics')">Pilot Quality Gate</button>
    </div>
  </header>

  <main>
    <!-- Left Screen List -->
    <aside class="sidebar">
      <div class="sidebar-section">
        <div class="sidebar-title">Screens Directory</div>
        <div id="screens-list"></div>
      </div>
      <div class="sidebar-section">
        <div class="sidebar-title">Proposals Lineage</div>
        <div id="proposals-summary" style="font-size:12px; color:var(--text-muted);">Select a screen to view proposals summary</div>
      </div>
    </aside>

    <!-- Center Stage -->
    <section class="viewport">
      <div class="toolbar">
        <div class="toggle-chip">
          <input type="checkbox" id="show-regions" checked onchange="updateSvgOverlays()">
          <label for="show-regions">Regions (Green)</label>
        </div>
        <div class="toggle-chip">
          <input type="checkbox" id="show-groups" checked onchange="updateSvgOverlays()">
          <label for="show-groups">Groups (Amber)</label>
        </div>
        <div class="toggle-chip">
          <input type="checkbox" id="show-elements" checked onchange="updateSvgOverlays()">
          <label for="show-elements">Elements (Red)</label>
        </div>
        <div class="toggle-chip">
          <input type="checkbox" id="show-proposals" onchange="toggleProposalsImage()">
          <label for="show-proposals">Detector Overlay</label>
        </div>
        <div class="toggle-chip">
          <input type="checkbox" id="show-audit" onchange="toggleAuditImage()">
          <label for="show-audit">Audit Patches</label>
        </div>
        <span id="screen-info-badge" style="margin-left:auto; font-size:12px; color:var(--text-muted);"></span>
      </div>

      <div class="canvas-container">
        <div class="image-stage" id="image-stage">
          <img id="main-image" src="" alt="Screen view">
          <svg id="overlay-svg" class="overlay-svg"></svg>
        </div>
      </div>
    </section>

    <!-- Right Inspector -->
    <aside class="inspector">
      <div class="inspector-header">
        <div class="inspector-title" id="inspector-title">Node Inspector</div>
      </div>
      <div class="inspector-content" id="inspector-content">
        <p style="color:var(--text-muted); font-size:13px;">Click on any region, group, or element box to inspect details.</p>
      </div>
    </aside>
  </main>

  <script>
    const SCREENS_DATA = {json.dumps(screens_data)};
    const PAIRS_DATA = {json.dumps(pairs_data)};
    let currentScreenId = Object.keys(SCREENS_DATA)[0] || null;
    let selectedNodeId = null;

    function init() {{
      renderScreensList();
      if (currentScreenId) {{
        selectScreen(currentScreenId);
      }}
    }}

    function renderScreensList() {{
      const list = document.getElementById('screens-list');
      list.innerHTML = '';
      for (const [sid, data] of Object.entries(SCREENS_DATA)) {{
        const div = document.createElement('div');
        div.className = 'screen-item' + (sid === currentScreenId ? ' selected' : '');
        div.onclick = () => selectScreen(sid);

        const nodeCount = data.annotation ? data.annotation.nodes.length : 0;
        const stratum = (data.annotation && data.annotation.screen_context && data.annotation.screen_context.view_types) ?
                        data.annotation.screen_context.view_types[0] : 'macOS';

        div.innerHTML = `
          <div class="screen-item-header">
            <span class="screen-id">${{sid}}</span>
            <span class="screen-stratum">${{stratum}}</span>
          </div>
          <div class="screen-stats">${{nodeCount}} nodes | ${{data.validation.valid ? '✓ Valid' : '⚠ Validation'}}</div>
        `;
        list.appendChild(div);
      }}
    }}

    function selectScreen(sid) {{
      currentScreenId = sid;
      selectedNodeId = null;
      renderScreensList();
      const data = SCREENS_DATA[sid];
      if (!data) return;

      document.getElementById('screen-info-badge').innerText = `${{sid}} (${{data.annotation ? data.annotation.image.width : 0}} × ${{data.annotation ? data.annotation.image.height : 0}})`;
      const mainImg = document.getElementById('main-image');
      mainImg.src = data.image_url;

      mainImg.onload = () => {{
        updateSvgOverlays();
      }};
      renderProposalsSummary(data);
      renderScreenContext(data);
    }}

    function updateSvgOverlays() {{
      const data = SCREENS_DATA[currentScreenId];
      if (!data || !data.annotation) return;

      const svg = document.getElementById('overlay-svg');
      const w = data.annotation.image.width;
      const h = data.annotation.image.height;
      svg.setAttribute('viewBox', `0 0 ${{w}} ${{h}}`);
      svg.innerHTML = '';

      const showRegions = document.getElementById('show-regions').checked;
      const showGroups = document.getElementById('show-groups').checked;
      const showElements = document.getElementById('show-elements').checked;

      const nodes = data.annotation.nodes || [];
      for (const node of nodes) {{
        if (node.level === 'screen') continue;
        if (node.level === 'region' && !showRegions) continue;
        if (node.level === 'group' && !showGroups) continue;
        if (node.level === 'element' && !showElements) continue;

        const [l, t, r, b] = node.bbox;
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('x', l);
        rect.setAttribute('y', t);
        rect.setAttribute('width', Math.max(1, r - l));
        rect.setAttribute('height', Math.max(1, b - t));
        rect.setAttribute('class', 'node-box' + (node.id === selectedNodeId ? ' selected' : ''));

        let strokeColor = '#ef4444';
        if (node.level === 'region') strokeColor = '#10b981';
        else if (node.level === 'group') strokeColor = '#f59e0b';
        else if (node.surface === 'embedded_content') strokeColor = '#ec4899';

        rect.setAttribute('stroke', strokeColor);
        rect.onclick = (e) => {{
          e.stopPropagation();
          selectNode(node.id);
        }};

        const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
        title.textContent = `${{node.id}} (${{node.role}}): ${{node.semantic_name || ''}} - ${{node.description}}`;
        rect.appendChild(title);

        svg.appendChild(rect);
      }}
    }}

    function selectNode(nid) {{
      selectedNodeId = nid;
      updateSvgOverlays();
      const data = SCREENS_DATA[currentScreenId];
      if (!data || !data.annotation) return;
      const node = data.annotation.nodes.find(n => n.id === nid);
      if (!node) return;

      const content = document.getElementById('inspector-content');
      document.getElementById('inspector-title').innerText = `${{node.id}}: ${{node.semantic_name || node.role}}`;

      let textList = '';
      if (node.visible_text && node.visible_text.length > 0) {{
        textList = node.visible_text.map(t => `<div style="font-size:12px; margin-bottom:4px;"><b>"${{t.text}}"</b> <span class="tag tag-blue">${{t.legibility}}</span></div>`).join('');
      }} else {{
        textList = '<span style="color:var(--text-muted); font-size:12px;">No visible text</span>';
      }}

      content.innerHTML = `
        <div class="card">
          <div class="card-label">Identification</div>
          <div class="prop-row"><span class="prop-key">ID</span><span class="prop-val">${{node.id}}</span></div>
          <div class="prop-row"><span class="prop-key">Level</span><span class="tag tag-purple">${{node.level}}</span></div>
          <div class="prop-row"><span class="prop-key">Role</span><span class="tag tag-blue">${{node.role}}</span></div>
          <div class="prop-row"><span class="prop-key">Surface</span><span class="tag tag-amber">${{node.surface}}</span></div>
          <div class="prop-row"><span class="prop-key">Parent</span><span class="prop-val">${{node.parent_id || 'root'}}</span></div>
          <div class="prop-row"><span class="prop-key">Box Status</span><span class="tag tag-green">${{node.box_status}}</span></div>
        </div>

        <div class="card">
          <div class="card-label">Contextual Description</div>
          <p style="font-size:12px; line-height:1.4; margin-bottom:8px;">${{node.description}}</p>
          <div class="card-label">Surrounding Area Context</div>
          <p style="font-size:12px; color:var(--text-muted); line-height:1.4;">${{node.context_description}}</p>
        </div>

        <div class="card">
          <div class="card-label">Visible Text Transcriptions</div>
          ${{textList}}
        </div>

        <div class="card">
          <div class="card-label">Function & State</div>
          <div class="prop-row"><span class="prop-key">Function</span><span class="prop-val">${{node.function ? node.function.label : 'none'}}</span></div>
          <div class="prop-row"><span class="prop-key">Selected</span><span class="prop-val">${{node.state.selected}}</span></div>
          <div class="prop-row"><span class="prop-key">Checked</span><span class="prop-val">${{node.state.checked}}</span></div>
          <div class="prop-row"><span class="prop-key">Expanded</span><span class="prop-val">${{node.state.expanded}}</span></div>
          <div class="prop-row"><span class="prop-key">Disabled Appearance</span><span class="prop-val">${{node.state.disabled_appearance}}</span></div>
        </div>

        <div class="card">
          <div class="card-label">Detector Proposals Matched</div>
          <p style="font-size:12px; font-family:var(--font-mono); color:var(--accent-blue);">${{node.proposal_ids.join(', ') || 'None (Added by Teacher)'}}</p>
        </div>

        <div class="card">
          <div class="card-label">Bounding Box Coordinates [l, t, r, b]</div>
          <p style="font-family:var(--font-mono); font-size:11px; color:#a7f3d0;">[${{node.bbox.join(', ')}}]</p>
        </div>
      `;
    }}

    function renderScreenContext(data) {{
      if (selectedNodeId) return;
      const ctx = data.annotation ? data.annotation.screen_context : null;
      if (!ctx) return;
      document.getElementById('inspector-title').innerText = `Screen: ${{data.screen_id}}`;
      document.getElementById('inspector-content').innerHTML = `
        <div class="card">
          <div class="card-label">Screen Context</div>
          <p style="font-size:13px; line-height:1.4; margin-bottom:10px;">${{ctx.description}}</p>
          <div class="prop-row"><span class="prop-key">Applications</span><span class="tag tag-blue">${{ctx.visible_app_names.join(', ')}}</span></div>
          <div class="prop-row"><span class="prop-key">View Types</span><span class="tag tag-amber">${{ctx.view_types.join(', ')}}</span></div>
        </div>
        <div class="card">
          <div class="card-label">Validation Status</div>
          <div class="prop-row"><span class="prop-key">Integrity</span><span class="tag tag-green">${{data.validation.valid ? 'PASSED (100%)' : 'FAILED'}}</span></div>
          <div class="prop-row"><span class="prop-key">Node Count</span><span class="prop-val">${{data.annotation.nodes.length}}</span></div>
          <div class="prop-row"><span class="prop-key">Proposals Count</span><span class="prop-val">${{data.proposals.proposal_count || 0}}</span></div>
        </div>
        <div class="card">
          <div class="card-label">Uncertainties</div>
          <p style="font-size:12px; color:var(--text-muted);">${{ctx.uncertainties.join('; ') || 'None noted'}}</p>
        </div>
      `;
    }}

    function renderProposalsSummary(data) {{
      const container = document.getElementById('proposals-summary');
      const cov = data.annotation ? data.annotation.coverage : null;
      if (!cov) {{
        container.innerText = 'No coverage data';
        return;
      }}
      const disps = cov.proposals_disposition || {{}};
      const counts = {{}};
      for (const [pid, info] of Object.entries(disps)) {{
        const d = info.disposition || 'unknown';
        counts[d] = (counts[d] || 0) + 1;
      }}
      container.innerHTML = Object.entries(counts)
        .map(([k, v]) => `<div style="display:flex; justify-content:space-between; margin-bottom:3px;"><span>${{k}}</span><b>${{v}}</b></div>`)
        .join('');
    }}

    function toggleProposalsImage() {{
      const chk = document.getElementById('show-proposals').checked;
      const data = SCREENS_DATA[currentScreenId];
      if (chk) {{
        document.getElementById('main-image').src = data.overlay_url;
      }} else {{
        document.getElementById('main-image').src = data.image_url;
      }}
    }}

    function toggleAuditImage() {{
      const chk = document.getElementById('show-audit').checked;
      const data = SCREENS_DATA[currentScreenId];
      if (chk) {{
        document.getElementById('main-image').src = data.audit_overlay_url;
      }} else {{
        document.getElementById('main-image').src = data.image_url;
      }}
    }}

    function switchView(mode) {{
      alert('Active view: ' + mode);
    }}

    window.onload = init;
  </script>
</body>
</html>
"""
    return html_content


def generate_review_artifact(pilot_dir: Path):
    review_dir = pilot_dir / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    html_page = build_review_html(pilot_dir)
    (review_dir / "index.html").write_text(html_page)
    print(f"Generated review tool at {review_dir / 'index.html'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot-dir", type=Path, required=True)
    args = parser.parse_args()
    generate_review_artifact(args.pilot_dir)
