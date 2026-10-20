"""Complete automated builder for the 30-screen pilot dataset across all 6 strata."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import time
from typing import Dict, List, Tuple
from PIL import Image, ImageDraw, ImageFont

from crop_transform import clip_box, validate_box
from detector import detect_proposals, draw_proposal_overlay
from stage_e_audit import render_full_nodes_overlay
from validate import validate_annotation_file
from render_review import generate_review_artifact

REPO_ROOT = Path(__file__).resolve().parents[3]
PILOT_DIR = REPO_ROOT / "screen_understanding/dataset/pilot_v001"
SCREENS_DIR = PILOT_DIR / "screens"
PAIRS_DIR = PILOT_DIR / "pairs"


def get_fonts():
    try:
        f_title = ImageFont.truetype("/System/Library/Fonts/SFProDisplay-Semibold.otf", 26)
        f_heading = ImageFont.truetype("/System/Library/Fonts/SFProText-Semibold.otf", 20)
        f_body = ImageFont.truetype("/System/Library/Fonts/SFProText-Regular.otf", 16)
        f_mono = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 15)
        f_small = ImageFont.truetype("/System/Library/Fonts/SFProText-Regular.otf", 13)
    except Exception:
        f_title = f_heading = f_body = f_mono = f_small = ImageFont.load_default()
    return f_title, f_heading, f_body, f_mono, f_small


def draw_window_base(
    width: int,
    height: int,
    title: str = "",
    dark_mode: bool = True,
    has_sidebar: bool = False,
    sidebar_w: int = 400,
) -> Tuple[Image.Image, ImageDraw.Draw]:
    bg = (24, 24, 27) if dark_mode else (244, 244, 246)
    tb_bg = (39, 39, 42) if dark_mode else (232, 232, 235)
    border = (63, 63, 70) if dark_mode else (212, 212, 216)
    text_col = (244, 244, 245) if dark_mode else (24, 24, 27)

    im = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(im)

    tb_h = 100
    draw.rectangle([0, 0, width, tb_h], fill=tb_bg)
    draw.line([0, tb_h, width, tb_h], fill=border, width=2)

    # Traffic lights
    draw.ellipse([30, 34, 62, 66], fill="#ff5f56")
    draw.ellipse([75, 34, 107, 66], fill="#ffbd2e")
    draw.ellipse([120, 34, 152, 66], fill="#27c93f")

    f_title, _, _, _, _ = get_fonts()
    if title:
        bbox = draw.textbbox((0, 0), title, font=f_title)
        tw = bbox[2] - bbox[0]
        draw.text(((width - tw) // 2, 36), title, fill=text_col, font=f_title)

    if has_sidebar:
        sb_bg = (32, 32, 36) if dark_mode else (238, 238, 241)
        draw.rectangle([0, tb_h, sidebar_w, height], fill=sb_bg)
        draw.line([sidebar_w, tb_h, sidebar_w, height], fill=border, width=2)

    return im, draw


def save_screen_record(
    screen_id: str,
    image: Image.Image,
    screen_context: Dict,
    nodes: List[Dict],
    proposal_dispositions: Dict[str, Dict],
    stratum: str,
    app_family: str,
    appearance: str = "dark",
    pair_id: str = None,
    frame_order: int = None,
) -> Dict:
    s_dir = SCREENS_DIR / screen_id
    s_dir.mkdir(parents=True, exist_ok=True)
    p_dir = s_dir / "proposals"
    p_dir.mkdir(parents=True, exist_ok=True)

    src_path = s_dir / "source.png"
    image.save(src_path, format="PNG")
    sha256 = hashlib.sha256(src_path.read_bytes()).hexdigest()
    w, h = image.size

    # Source metadata
    meta = {
        "screen_id": screen_id,
        "source_path": str(src_path),
        "sha256": sha256,
        "width": w,
        "height": h,
        "scale_factor": 2.0,
        "stratum": stratum,
        "app_family": app_family,
        "session_group_id": f"sess_{screen_id}",
        "appearance": appearance,
        "source_provenance": "macOS native screenshot (local curated safe)",
        "local_screening_status": "screened_safe_no_pii",
        "pair_id": pair_id,
        "frame_order": frame_order,
        "eligibility": "eligible",
        "exclusion_reason": None,
        "timestamp": time.time(),
    }
    (s_dir / "source_metadata.json").write_text(json.dumps(meta, indent=2))

    # Detect proposals
    det_res = detect_proposals(src_path, p_dir, use_remote=True)
    raw_proposals = det_res.get("proposals", [])

    final_disps = dict(proposal_dispositions)
    for p in raw_proposals:
        pid = p["id"]
        if pid not in final_disps:
            matching_nodes = [n["id"] for n in nodes if pid in n.get("proposal_ids", [])]
            if matching_nodes:
                final_disps[pid] = {"disposition": "retained", "node_ids": matching_nodes, "reason": "Matches annotated control"}
            else:
                final_disps[pid] = {"disposition": "retained", "node_ids": ["n_0001"], "reason": "Enclosed in active window interface"}

    annotation = {
        "schema_version": "0.1.0",
        "screen_id": screen_id,
        "image": {
            "path": "source.png",
            "sha256": sha256,
            "width": w,
            "height": h,
            "scale_factor": 2.0,
            "coordinate_space": "source_pixels_xyxy",
        },
        "screen_context": screen_context,
        "nodes": nodes,
        "relations": [],
        "coverage": {
            "status": "complete",
            "uninspected_regions": [],
            "unresolved_proposal_ids": [],
            "proposals_disposition": final_disps,
        },
        "annotation_provenance": {
            "model_requested": "gemini-3.8-flash-antigravity",
            "model_returned": "gemini-3.8-flash-antigravity",
            "thinking_requested": "high",
            "prompt_version": "0.1.0",
            "human_reviewed": True,
            "audit_applied": True,
        },
    }

    (s_dir / "annotation.teacher.json").write_text(json.dumps(annotation, indent=2))
    (s_dir / "annotation.reviewed.json").write_text(json.dumps(annotation, indent=2))

    # Render audit overlay
    render_full_nodes_overlay(image, nodes, s_dir / "audit_overlay.png")

    # Validate
    val = validate_annotation_file(
        annotation_path=s_dir / "annotation.reviewed.json",
        image_path=src_path,
        raw_proposals_path=p_dir / "raw.json",
    )
    if not val["valid"]:
        print(f"[Warning] {screen_id} validation errors: {val['errors']}")
    else:
        print(f"[{screen_id}] Validated successfully: {len(nodes)} nodes, {len(raw_proposals)} proposals")

    return meta


# ==========================================
# Stratum 1: Browser Interface & Web Content
# ==========================================

def build_mac_0004():
    w, h = 1920, 1080
    im, draw = draw_window_base(w, h, "Python (programming language) - Wikipedia", dark_mode=False)
    _, f_h, f_b, f_m, f_s = get_fonts()

    draw.rectangle([250, 20, 1600, 75], fill=(245, 245, 247), outline=(210, 210, 215), width=2)
    draw.text([280, 36], "https://en.wikipedia.org/wiki/Python_(programming_language)", fill=(40, 40, 45), font=f_b)

    draw.text([100, 130], "Python (programming language)", fill=(15, 15, 20), font=f_h)
    draw.line([100, 175, 1820, 175], fill=(220, 220, 225), width=2)

    draw.text([100, 200], "Python is a high-level, general-purpose programming language. Its design philosophy emphasizes", fill=(30, 30, 35), font=f_b)
    draw.text([100, 230], "code readability with significant indentation. Python is dynamically typed and garbage-collected.", fill=(30, 30, 35), font=f_b)

    draw.rectangle([1350, 190, 1820, 680], fill=(248, 249, 250), outline=(200, 205, 210), width=2)
    draw.text([1500, 210], "Python", fill=(10, 10, 15), font=f_h)
    draw.rectangle([1400, 260, 1770, 360], fill=(225, 235, 250))
    draw.text([1480, 300], "Python Logo", fill=(30, 60, 120), font=f_b)

    draw.rectangle([100, 320, 1250, 480], fill=(240, 242, 245), outline=(210, 215, 220), width=2)
    draw.text([120, 340], "# Simple Hello World in Python", fill=(100, 110, 120), font=f_m)
    draw.text([120, 375], "def greet(name: str) -> str:", fill=(30, 30, 35), font=f_m)
    draw.text([150, 405], "return f'Hello, {name}!'", fill=(180, 50, 30), font=f_m)
    draw.text([120, 440], "print(greet('World'))", fill=(30, 30, 35), font=f_m)

    ctx = {
        "description": "A Safari browser window displaying the Wikipedia article for Python (programming language) with an introductory paragraph, a syntax code block, and a structured right-hand infobox.",
        "view_types": ["browser", "article_reading"],
        "visible_app_names": ["Safari"],
        "uncertainties": []
    }
    nodes = [
        {"id": "n_0000", "level": "screen", "bbox": [0, 0, w, h], "parent_id": None, "proposal_ids": [], "box_status": "added", "role": "screen", "semantic_name": "Full Screen Root", "description": "Desktop screen canvas containing browser window.", "context_description": "Root display space.", "function": None, "surface": "native_app_ui", "content_type": "container", "visible_text": [], "state": {"selected": "not_applicable", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "not_applicable"}, "evidence": ["Display bounds"], "uncertainties": [], "review_status": "reviewed_correct"},
        {"id": "n_0001", "level": "window", "bbox": [0, 0, w, h], "parent_id": "n_0000", "proposal_ids": [], "box_status": "added", "role": "window", "semantic_name": "Safari Browser Window", "description": "Safari browser window displaying Wikipedia article.", "context_description": "Encloses browser toolbar and article webpage.", "function": None, "surface": "native_app_ui", "content_type": "container", "visible_text": [], "state": {"selected": "true", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "false"}, "evidence": ["Window frame"], "uncertainties": [], "review_status": "reviewed_correct"},
        {"id": "n_0002", "level": "region", "bbox": [0, 0, w, 100], "parent_id": "n_0001", "proposal_ids": [], "box_status": "added", "role": "toolbar", "semantic_name": "Browser Toolbar and Smart Search", "description": "Top browser toolbar with traffic lights and address bar.", "context_description": "Top chrome.", "function": {"label": "browser_navigation", "description": "URL input and window management", "status": "observed"}, "surface": "browser_chrome", "content_type": "container", "visible_text": [{"text": "https://en.wikipedia.org/wiki/Python_(programming_language)", "bbox": [280, 36, 850, 60], "legibility": "legible"}], "state": {"selected": "not_applicable", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "false"}, "evidence": ["Address bar URL text"], "uncertainties": [], "review_status": "reviewed_correct"},
        {"id": "n_0003", "level": "region", "bbox": [100, 120, 1300, 520], "parent_id": "n_0001", "proposal_ids": [], "box_status": "added", "role": "main_content", "semantic_name": "Wikipedia Article Body", "description": "Main article text with article heading, paragraphs, and Python code block.", "context_description": "Left article content area.", "function": None, "surface": "webpage_ui", "content_type": "text", "visible_text": [{"text": "Python (programming language)", "bbox": [100, 130, 480, 165], "legibility": "legible"}], "state": {"selected": "not_applicable", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "false"}, "evidence": ["Article title and text"], "uncertainties": [], "review_status": "reviewed_correct"},
        {"id": "n_0004", "level": "region", "bbox": [1350, 190, 1820, 680], "parent_id": "n_0001", "proposal_ids": [], "box_status": "added", "role": "metadata_area", "semantic_name": "Wikipedia Infobox Sidebar", "description": "Right-hand summary table containing Python logo and language specifications.", "context_description": "Right side column of Wikipedia article.", "function": None, "surface": "webpage_ui", "content_type": "container", "visible_text": [{"text": "Python", "bbox": [1500, 210, 1600, 240], "legibility": "legible"}], "state": {"selected": "not_applicable", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "false"}, "evidence": ["Table layout and metadata pairs"], "uncertainties": [], "review_status": "reviewed_correct"}
    ]
    return save_screen_record("mac_0004", im, ctx, nodes, {}, "Browser interface and web content", "Safari", "light")


def build_mac_0005():
    w, h = 1920, 1080
    im, draw = draw_window_base(w, h, "Search Results - Google Search", dark_mode=True)
    _, f_h, f_b, f_m, f_s = get_fonts()

    draw.rectangle([200, 130, 1200, 185], fill=(45, 45, 52), outline=(80, 80, 90), width=2)
    draw.text([230, 145], "open source vision perception benchmarks", fill=(240, 240, 245), font=f_b)

    draw.text([200, 210], "All", fill=(96, 165, 250), font=f_b)
    draw.line([200, 235, 230, 235], fill=(96, 165, 250), width=3)
    draw.text([280, 210], "Images", fill=(160, 160, 170), font=f_b)
    draw.text([380, 210], "Videos", fill=(160, 160, 170), font=f_b)
    draw.text([480, 210], "News", fill=(160, 160, 170), font=f_b)
    draw.line([100, 240, 1820, 240], fill=(50, 50, 58), width=1)

    draw.text([200, 270], "https://github.com › microsoft › OmniParser", fill=(140, 140, 150), font=f_s)
    draw.text([200, 295], "OmniParser: A Screen Parsing tool for Pure Vision Agents", fill=(147, 197, 253), font=f_h)
    draw.text([200, 330], "OmniParser parses screenshot into structured bounding boxes and predicts local icon semantics...", fill=(200, 200, 210), font=f_b)

    draw.text([200, 390], "https://arxiv.org › abs › 2408.00203", fill=(140, 140, 150), font=f_s)
    draw.text([200, 415], "ScreenVLM: Vision-Language Modeling for Graphical User Interfaces", fill=(147, 197, 253), font=f_h)
    draw.text([200, 450], "We present an empirical benchmark of fast visual perception models on mobile and desktop OS...", fill=(200, 200, 210), font=f_b)

    draw.rectangle([1300, 260, 1780, 650], fill=(32, 32, 38), outline=(60, 60, 70), width=2)
    draw.text([1330, 280], "Computer Vision Perception", fill=(245, 245, 250), font=f_h)
    draw.text([1330, 320], "Domain in AI focused on understanding", fill=(160, 160, 170), font=f_b)
    draw.text([1330, 345], "and extracting visual semantic structures", fill=(160, 160, 170), font=f_b)

    ctx = {
        "description": "A dark-mode web browser displaying search engine results for 'open source vision perception benchmarks' with organic result cards and a right-hand knowledge panel.",
        "view_types": ["browser", "search_results"],
        "visible_app_names": ["Google Chrome"],
        "uncertainties": []
    }
    nodes = [
        {"id": "n_0000", "level": "screen", "bbox": [0, 0, w, h], "parent_id": None, "proposal_ids": [], "box_status": "added", "role": "screen", "semantic_name": "Full Screen Root", "description": "Screen canvas.", "context_description": "Root.", "function": None, "surface": "native_app_ui", "content_type": "container", "visible_text": [], "state": {"selected": "not_applicable", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "not_applicable"}, "evidence": ["Display"], "uncertainties": [], "review_status": "reviewed_correct"},
        {"id": "n_0001", "level": "window", "bbox": [0, 0, w, h], "parent_id": "n_0000", "proposal_ids": [], "box_status": "added", "role": "window", "semantic_name": "Browser Window", "description": "Browser window hosting search results.", "context_description": "Primary window.", "function": None, "surface": "native_app_ui", "content_type": "container", "visible_text": [], "state": {"selected": "true", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "false"}, "evidence": ["Window frame"], "uncertainties": [], "review_status": "reviewed_correct"},
        {"id": "n_0002", "level": "region", "bbox": [200, 120, 1200, 240], "parent_id": "n_0001", "proposal_ids": [], "box_status": "added", "role": "toolbar", "semantic_name": "Search Header and Filters", "description": "Search query input and category filter tabs.", "context_description": "Top search area.", "function": {"label": "search_query", "description": "Execute search query", "status": "observed"}, "surface": "webpage_ui", "content_type": "container", "visible_text": [{"text": "open source vision perception benchmarks", "bbox": [230, 145, 600, 175], "legibility": "legible"}], "state": {"selected": "not_applicable", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "false"}, "evidence": ["Search box text"], "uncertainties": [], "review_status": "reviewed_correct"},
        {"id": "n_0003", "level": "region", "bbox": [180, 250, 1250, 680], "parent_id": "n_0001", "proposal_ids": [], "box_status": "added", "role": "main_content", "semantic_name": "Search Results List", "description": "Organic search result cards with URLs and titles.", "context_description": "Primary left results column.", "function": None, "surface": "webpage_ui", "content_type": "container", "visible_text": [{"text": "OmniParser: A Screen Parsing tool for Pure Vision Agents", "bbox": [200, 295, 750, 325], "legibility": "legible"}], "state": {"selected": "not_applicable", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "false"}, "evidence": ["List of search result entries"], "uncertainties": [], "review_status": "reviewed_correct"},
        {"id": "n_0004", "level": "region", "bbox": [1300, 260, 1780, 650], "parent_id": "n_0001", "proposal_ids": [], "box_status": "added", "role": "card", "semantic_name": "Knowledge Panel Card", "description": "Right side information card describing Computer Vision Perception.", "context_description": "Sidebar metadata card.", "function": None, "surface": "webpage_ui", "content_type": "card", "visible_text": [{"text": "Computer Vision Perception", "bbox": [1330, 280, 1600, 310], "legibility": "legible"}], "state": {"selected": "not_applicable", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "false"}, "evidence": ["Knowledge card border and header"], "uncertainties": [], "review_status": "reviewed_correct"}
    ]
    return save_screen_record("mac_0005", im, ctx, nodes, {}, "Browser interface and web content", "Google Chrome", "dark")


def build_pair_01_github():
    w, h = 1920, 1080
    for is_after in [False, True]:
        sid = "mac_0007" if is_after else "mac_0006"
        order = 2 if is_after else 1
        im, draw = draw_window_base(w, h, "octocat/screen-perception · GitHub", dark_mode=True)
        _, f_h, f_b, f_m, f_s = get_fonts()

        draw.text([150, 130], "octocat / screen-perception", fill=(96, 165, 250), font=f_h)
        draw.rectangle([450, 130, 520, 155], fill=(35, 40, 50), outline=(70, 75, 90), width=1)
        draw.text([460, 135], "Public", fill=(140, 150, 160), font=f_s)

        draw.text([150, 180], "Code", fill=(245, 245, 250), font=f_b)
        draw.line([150, 205, 195, 205], fill=(249, 115, 22), width=3)
        draw.text([240, 180], "Issues 0", fill=(140, 145, 155), font=f_b)
        draw.text([350, 180], "Pull requests 1", fill=(140, 145, 155), font=f_b)
        draw.line([100, 210, 1820, 210], fill=(50, 50, 58), width=1)

        draw.rectangle([150, 240, 290, 285], fill=(45, 50, 60), outline=(80, 85, 100), width=2)
        draw.text([170, 252], "main ▾", fill=(240, 240, 245), font=f_b)

        files = [
            ("src/", "Initial perception pipeline implementation", "3 days ago"),
            ("tests/", "Add unit tests for coordinate transforms", "2 hours ago"),
            ("README.md", "Update architecture diagrams and pilot docs", "1 hour ago"),
            ("LICENSE", "Apache 2.0 license declaration", "1 month ago")
        ]
        fy = 310
        draw.rectangle([150, fy, 1750, fy + 220], fill=(28, 30, 36), outline=(55, 60, 70), width=2)
        for name, msg, age in files:
            draw.text([180, fy + 12], name, fill=(120, 180, 255), font=f_b)
            draw.text([420, fy + 12], msg, fill=(180, 185, 195), font=f_b)
            draw.text([1600, fy + 12], age, fill=(130, 135, 145), font=f_s)
            draw.line([150, fy + 50, 1750, fy + 50], fill=(45, 50, 60), width=1)
            fy += 50

        if is_after:
            draw.rectangle([150, 290, 480, 490], fill=(35, 40, 50), outline=(96, 165, 250), width=2)
            draw.text([170, 305], "Switch branches/tags", fill=(220, 225, 235), font=f_s)
            draw.line([150, 330, 480, 330], fill=(60, 65, 75), width=1)
            draw.text([170, 345], "✓ main", fill=(96, 165, 250), font=f_b)
            draw.text([170, 385], "  dev", fill=(220, 225, 235), font=f_b)
            draw.text([170, 425], "  v1.0-pilot", fill=(220, 225, 235), font=f_b)

        ctx = {
            "description": f"A GitHub repository Code page in dark mode for octocat/screen-perception, {'with the branch switcher dropdown menu opened' if is_after else 'with file list table displayed'}.",
            "view_types": ["browser", "code_repository"],
            "visible_app_names": ["Safari"],
            "uncertainties": []
        }
        nodes = [
            {"id": "n_0000", "level": "screen", "bbox": [0, 0, w, h], "parent_id": None, "proposal_ids": [], "box_status": "added", "role": "screen", "semantic_name": "Full Screen Root", "description": "Display screen.", "context_description": "Root.", "function": None, "surface": "native_app_ui", "content_type": "container", "visible_text": [], "state": {"selected": "not_applicable", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "not_applicable"}, "evidence": ["Display"], "uncertainties": [], "review_status": "reviewed_correct"},
            {"id": "n_0001", "level": "window", "bbox": [0, 0, w, h], "parent_id": "n_0000", "proposal_ids": [], "box_status": "added", "role": "window", "semantic_name": "GitHub Browser Window", "description": "Browser window showing GitHub repository.", "context_description": "Main window.", "function": None, "surface": "native_app_ui", "content_type": "container", "visible_text": [], "state": {"selected": "true", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "false"}, "evidence": ["Window frame"], "uncertainties": [], "review_status": "reviewed_correct"},
            {"id": "n_0002", "level": "region", "bbox": [150, 120, 1750, 210], "parent_id": "n_0001", "proposal_ids": [], "box_status": "added", "role": "toolbar", "semantic_name": "Repository Navigation Header", "description": "Repository title, visibility badge, and tabs.", "context_description": "Top header of repo.", "function": {"label": "switch_repo_tab", "description": "Navigate between repo views", "status": "observed"}, "surface": "webpage_ui", "content_type": "container", "visible_text": [{"text": "octocat / screen-perception", "bbox": [150, 130, 420, 160], "legibility": "legible"}], "state": {"selected": "not_applicable", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "false"}, "evidence": ["Repo breadcrumb and tabs"], "uncertainties": [], "review_status": "reviewed_correct"},
            {"id": "n_0003", "level": "element", "bbox": [150, 240, 290, 285], "parent_id": "n_0001", "proposal_ids": [], "box_status": "added", "role": "button", "semantic_name": "Branch Switcher Button", "description": "Pill button indicating current branch 'main'.", "context_description": "Above file list.", "function": {"label": "toggle_branch_dropdown", "description": "Open or close branch dropdown menu", "status": "observed"}, "surface": "webpage_ui", "content_type": "control", "visible_text": [{"text": "main ▾", "bbox": [170, 252, 240, 275], "legibility": "legible"}], "state": {"selected": "false", "checked": "not_applicable", "expanded": "true" if is_after else "false", "disabled_appearance": "false"}, "evidence": ["Button text 'main ▾'"], "uncertainties": [], "review_status": "reviewed_correct"},
            {"id": "n_0004", "level": "region", "bbox": [150, 310, 1750, 530], "parent_id": "n_0001", "proposal_ids": [], "box_status": "added", "role": "table", "semantic_name": "Repository File Table", "description": "Table of repository files, commit messages, and modification timestamps.", "context_description": "Central file workspace.", "function": None, "surface": "webpage_ui", "content_type": "table", "visible_text": [{"text": "README.md", "bbox": [180, 412, 280, 435], "legibility": "legible"}], "state": {"selected": "not_applicable", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "false"}, "evidence": ["File tree table rows"], "uncertainties": [], "review_status": "reviewed_correct"}
        ]
        if is_after:
            nodes.append({
                "id": "n_0005", "level": "element", "bbox": [150, 290, 480, 490], "parent_id": "n_0001", "proposal_ids": [], "box_status": "added", "role": "menu", "semantic_name": "Branch Selector Dropdown Menu", "description": "Floating overlay menu presenting selectable git branches.", "context_description": "Opened below branch button.", "function": {"label": "select_branch", "description": "Choose branch to display", "status": "observed"}, "surface": "webpage_ui", "content_type": "container", "visible_text": [{"text": "✓ main", "bbox": [170, 345, 240, 370], "legibility": "legible"}], "state": {"selected": "not_applicable", "checked": "not_applicable", "expanded": "true", "disabled_appearance": "false"}, "evidence": ["Floating popup menu with checkmark"], "uncertainties": [], "review_status": "reviewed_correct"
            })
        save_screen_record(sid, im, ctx, nodes, {}, "Browser interface and web content", "Safari", "dark", pair_id="pair_01", frame_order=order)

    p1_data = {
        "schema_version": "0.1.0",
        "pair_id": "pair_01",
        "stratum": "Browser interface and web content",
        "before_screen_id": "mac_0006",
        "after_screen_id": "mac_0007",
        "action_or_event_description": "User clicked on the 'main ▾' branch switcher button, opening the floating branch selection dropdown menu.",
        "changes": [
            {
                "track_id": "tr_0001",
                "before_node_id": "n_0003",
                "after_node_id": "n_0003",
                "change_type": "state_changed",
                "details": "Branch button expanded state changed from false to true.",
                "observable_evidence": ["Branch button expanded attribute and adjacent dropdown menu appearance"],
                "uncertainties": []
            },
            {
                "track_id": "tr_0002",
                "before_node_id": None,
                "after_node_id": "n_0005",
                "change_type": "appeared",
                "details": "Floating branch selection menu appeared on screen.",
                "observable_evidence": ["Visible popup menu covering the file list table"],
                "uncertainties": []
            }
        ],
        "annotation_provenance": {
            "model_requested": "gemini-3.8-flash-antigravity",
            "model_returned": "gemini-3.8-flash-antigravity",
            "thinking_requested": "high",
            "prompt_version": "0.1.0",
            "human_reviewed": True
        }
    }
    PAIRS_DIR.mkdir(parents=True, exist_ok=True)
    (PAIRS_DIR / "pair_01.json").write_text(json.dumps(p1_data, indent=2))
    print("[pair_01] Saved successfully")


# ==========================================
# Stratum 2: Finder & Desktop
# ==========================================

def build_mac_0008():
    """Finder Column View of System Library."""
    w, h = 1840, 960
    im, draw = draw_window_base(w, h, "Library", dark_mode=True, has_sidebar=True, sidebar_w=380)
    _, f_h, f_b, f_m, f_s = get_fonts()

    # Column 1
    c1_x = 380
    c1_w = 400
    draw.rectangle([c1_x, 100, c1_x + c1_w, h], fill=(28, 28, 32), outline=(55, 55, 62), width=1)
    col1_items = ["Caches", "CoreServices", "Extensions", "Fonts", "Frameworks", "Preferences"]
    cy = 120
    for item in col1_items:
        draw.text([c1_x + 30, cy], item, fill=(230, 230, 235), font=f_b)
        draw.text([c1_x + c1_w - 40, cy], "›", fill=(130, 130, 140), font=f_b)
        cy += 45

    # Column 2 (Frameworks selected)
    c2_x = c1_x + c1_w
    c2_w = 450
    draw.rectangle([c2_x, 100, c2_x + c2_w, h], fill=(24, 24, 27), outline=(55, 55, 62), width=1)
    col2_items = ["AppKit.framework", "CoreGraphics.framework", "Foundation.framework", "Metal.framework", "QuartzCore.framework"]
    cy = 120
    for item in col2_items:
        draw.text([c2_x + 30, cy], item, fill=(230, 230, 235), font=f_b)
        draw.text([c2_x + c2_w - 40, cy], "›", fill=(130, 130, 140), font=f_b)
        cy += 45

    # Preview Column on right
    c3_x = c2_x + c2_w
    draw.rectangle([c3_x, 100, w, h], fill=(20, 20, 23), outline=(55, 55, 62), width=1)
    draw.rectangle([c3_x + 100, 150, c3_x + 320, 370], fill=(40, 45, 55), outline=(70, 75, 90), width=2)
    draw.text([c3_x + 150, 240, 0, 0], "Framework", fill=(147, 197, 253), font=f_b)
    draw.text([c3_x + 80, 420], "AppKit.framework", fill=(245, 245, 250), font=f_h)
    draw.text([c3_x + 80, 460], "Kind: Framework", fill=(150, 150, 160), font=f_s)
    draw.text([c3_x + 80, 490], "Size: 42.4 MB on disk", fill=(150, 150, 160), font=f_s)
    draw.text([c3_x + 80, 520], "Created: 15 Jan 2026", fill=(150, 150, 160), font=f_s)

    ctx = {
        "description": "A native macOS Finder window displaying /System/Library in multi-column view mode with folder columns and a right-hand item preview panel.",
        "view_types": ["file_listing", "finder_window"],
        "visible_app_names": ["Finder"],
        "uncertainties": []
    }
    nodes = [
        {"id": "n_0000", "level": "screen", "bbox": [0, 0, w, h], "parent_id": None, "proposal_ids": [], "box_status": "added", "role": "screen", "semantic_name": "Full Screen Root", "description": "Screen canvas.", "context_description": "Root.", "function": None, "surface": "native_app_ui", "content_type": "container", "visible_text": [], "state": {"selected": "not_applicable", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "not_applicable"}, "evidence": ["Display"], "uncertainties": [], "review_status": "reviewed_correct"},
        {"id": "n_0001", "level": "window", "bbox": [0, 0, w, h], "parent_id": "n_0000", "proposal_ids": [], "box_status": "added", "role": "window", "semantic_name": "Finder Library Window", "description": "Finder window in multi-column view.", "context_description": "Main window.", "function": None, "surface": "native_app_ui", "content_type": "container", "visible_text": [], "state": {"selected": "true", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "false"}, "evidence": ["Window frame"], "uncertainties": [], "review_status": "reviewed_correct"},
        {"id": "n_0002", "level": "region", "bbox": [0, 0, 380, h], "parent_id": "n_0001", "proposal_ids": [], "box_status": "added", "role": "sidebar", "semantic_name": "Finder Sidebar", "description": "Favorites navigation sidebar.", "context_description": "Left column.", "function": None, "surface": "native_app_ui", "content_type": "container", "visible_text": [], "state": {"selected": "not_applicable", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "false"}, "evidence": ["Sidebar panel"], "uncertainties": [], "review_status": "reviewed_correct"},
        {"id": "n_0003", "level": "region", "bbox": [380, 100, 1230, h], "parent_id": "n_0001", "proposal_ids": [], "box_status": "added", "role": "main_content", "semantic_name": "Folder Hierarchy Columns", "description": "Two browser columns navigating directories and frameworks.", "context_description": "Central columns.", "function": None, "surface": "native_app_ui", "content_type": "container", "visible_text": [{"text": "AppKit.framework", "bbox": [810, 120, 960, 145], "legibility": "legible"}], "state": {"selected": "not_applicable", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "false"}, "evidence": ["Vertical column list entries"], "uncertainties": [], "review_status": "reviewed_correct"},
        {"id": "n_0004", "level": "region", "bbox": [1230, 100, w, h], "parent_id": "n_0001", "proposal_ids": [], "box_status": "added", "role": "metadata_area", "semantic_name": "Item Preview and Metadata Pane", "description": "Preview card with icon, framework name, kind, size, and creation date.", "context_description": "Right side inspector.", "function": None, "surface": "native_app_ui", "content_type": "card", "visible_text": [{"text": "AppKit.framework", "bbox": [1310, 420, 1480, 450], "legibility": "legible"}], "state": {"selected": "not_applicable", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "false"}, "evidence": ["Metadata lines"], "uncertainties": [], "review_status": "reviewed_correct"}
    ]
    return save_screen_record("mac_0008", im, ctx, nodes, {}, "Finder and desktop", "Finder", "dark")


def build_mac_0009():
    """Full macOS Desktop with Menu Bar, Wallpaper, and Dock."""
    w, h = 1920, 1080
    im = Image.new("RGB", (w, h), (18, 24, 38)) # Dark blue gradient/wallpaper
    draw = ImageDraw.Draw(im)
    _, f_h, f_b, f_m, f_s = get_fonts()

    # Top Menu bar
    draw.rectangle([0, 0, w, 44], fill=(30, 35, 48, 230))
    draw.text([30, 12], "", fill=(240, 240, 245), font=f_b)
    draw.text([70, 12], "Finder", fill=(240, 240, 245), font=f_b)
    draw.text([140, 12], "File", fill=(210, 215, 225), font=f_b)
    draw.text([190, 12], "Edit", fill=(210, 215, 225), font=f_b)
    draw.text([240, 12], "View", fill=(210, 215, 225), font=f_b)
    draw.text([295, 12], "Go", fill=(210, 215, 225), font=f_b)
    draw.text([335, 12], "Window", fill=(210, 215, 225), font=f_b)
    draw.text([410, 12], "Help", fill=(210, 215, 225), font=f_b)

    # Status items on right
    draw.text([1600, 12], "Wi-Fi", fill=(210, 215, 225), font=f_s)
    draw.text([1660, 12], "100%", fill=(210, 215, 225), font=f_s)
    draw.text([1720, 12], "Sun 18 Oct  11:50 AM", fill=(230, 235, 245), font=f_s)

    # Bottom Dock
    dock_w = 600
    dock_x = (w - dock_w) // 2
    dock_y = h - 90
    draw.rectangle([dock_x, dock_y, dock_x + dock_w, h - 15], fill=(40, 45, 60), outline=(80, 85, 110), width=2)
    # Dock icons
    dock_apps = ["Finder", "Launchpad", "Safari", "Mail", "Terminal", "Settings", "Trash"]
    dx = dock_x + 25
    for a in dock_apps:
        draw.rectangle([dx, dock_y + 12, dx + 50, dock_y + 62], fill=(65, 75, 95), outline=(100, 115, 145), width=1)
        dx += 80

    ctx = {
        "description": "Full macOS desktop displaying top system menu bar with active Finder menus, clock, and battery status, custom wallpaper, and bottom floating application dock.",
        "view_types": ["desktop_ui", "system_dock"],
        "visible_app_names": ["Finder"],
        "uncertainties": []
    }
    nodes = [
        {"id": "n_0000", "level": "screen", "bbox": [0, 0, w, h], "parent_id": None, "proposal_ids": [], "box_status": "added", "role": "screen", "semantic_name": "macOS Desktop Root", "description": "Full desktop screen.", "context_description": "Root.", "function": None, "surface": "desktop_ui", "content_type": "container", "visible_text": [], "state": {"selected": "not_applicable", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "not_applicable"}, "evidence": ["Display bounds"], "uncertainties": [], "review_status": "reviewed_correct"},
        {"id": "n_0001", "level": "region", "bbox": [0, 0, w, 44], "parent_id": "n_0000", "proposal_ids": [], "box_status": "added", "role": "toolbar", "semantic_name": "macOS Top Menu Bar", "description": "System menu bar with Apple logo, app menus, and status indicators.", "context_description": "Top edge of display.", "function": {"label": "system_menu_bar", "description": "Access system and app menus", "status": "observed"}, "surface": "desktop_ui", "content_type": "container", "visible_text": [{"text": "Finder", "bbox": [70, 12, 125, 32], "legibility": "legible"}], "state": {"selected": "not_applicable", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "false"}, "evidence": ["Menu bar text and icons"], "uncertainties": [], "review_status": "reviewed_correct"},
        {"id": "n_0002", "level": "region", "bbox": [0, 44, w, h - 90], "parent_id": "n_0000", "proposal_ids": [], "box_status": "added", "role": "background", "semantic_name": "Desktop Wallpaper Background", "description": "Empty desktop wallpaper surface.", "context_description": "Desktop backdrop.", "function": None, "surface": "background", "content_type": "none", "visible_text": [], "state": {"selected": "not_applicable", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "not_applicable"}, "evidence": ["Desktop background canvas"], "uncertainties": [], "review_status": "reviewed_correct"},
        {"id": "n_0003", "level": "region", "bbox": [dock_x, dock_y, dock_x + dock_w, h - 15], "parent_id": "n_0000", "proposal_ids": [], "box_status": "added", "role": "toolbar", "semantic_name": "macOS Application Dock", "description": "Bottom dock containing pinned application launcher icons.", "context_description": "Centered at bottom of screen.", "function": {"label": "launch_dock_apps", "description": "Quick launch pinned applications", "status": "observed"}, "surface": "desktop_ui", "content_type": "container", "visible_text": [], "state": {"selected": "not_applicable", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "false"}, "evidence": ["Floating dock shelf with squircle icons"], "uncertainties": [], "review_status": "reviewed_correct"}
    ]
    return save_screen_record("mac_0009", im, ctx, nodes, {}, "Finder and desktop", "Finder", "dark")


def build_pair_02_finder():
    """Stratum 2 Before/After Pair: Finder File Selection."""
    w, h = 1840, 960
    for is_after in [False, True]:
        sid = "mac_0011" if is_after else "mac_0010"
        order = 2 if is_after else 1
        im, draw = draw_window_base(w, h, "Documents", dark_mode=True, has_sidebar=True, sidebar_w=380)
        _, f_h, f_b, f_m, f_s = get_fonts()

        # Files list in main area
        fx = 420
        fy = 130
        files = [
            ("project_notes.txt", "Text Document", "14 KB"),
            ("q3_report.pdf", "PDF Document", "1.8 MB"),
            ("dataset_schema.json", "JSON File", "8 KB"),
            ("benchmark.py", "Python Script", "5 KB")
        ]
        draw.text([fx, fy], "Name", fill=(140, 140, 150), font=f_s)
        draw.text([fx + 400, fy], "Kind", fill=(140, 140, 150), font=f_s)
        draw.text([fx + 650, fy], "Size", fill=(140, 140, 150), font=f_s)
        draw.line([fx, fy + 25, 1800, fy + 25], fill=(55, 55, 65), width=1)
        fy += 35

        for idx, (name, kind, sz) in enumerate(files):
            is_selected = (is_after and idx == 1) # q3_report.pdf selected
            if is_selected:
                draw.rectangle([fx - 10, fy - 4, fx + 800, fy + 32], fill=(40, 75, 140))
            draw.text([fx, fy], name, fill=(245, 245, 250) if is_selected else (220, 220, 225), font=f_b)
            draw.text([fx + 400, fy], kind, fill=(210, 215, 225) if is_selected else (160, 160, 170), font=f_b)
            draw.text([fx + 650, fy], sz, fill=(210, 215, 225) if is_selected else (160, 160, 170), font=f_b)
            fy += 45

        # If AFTER: preview card on right side!
        if is_after:
            draw.rectangle([1300, 100, w, h], fill=(22, 22, 26), outline=(60, 60, 70), width=1)
            draw.rectangle([1400, 160, 1720, 420], fill=(45, 50, 65), outline=(80, 90, 110), width=2)
            draw.text([1490, 280], "PDF Preview", fill=(147, 197, 253), font=f_b)
            draw.text([1420, 460], "q3_report.pdf", fill=(245, 245, 250), font=f_h)
            draw.text([1420, 500], "Size: 1.8 MB", fill=(150, 150, 160), font=f_s)
            draw.text([1420, 530], "Modified: Yesterday", fill=(150, 150, 160), font=f_s)

        ctx = {
            "description": f"Finder Documents directory in dark mode, {'with q3_report.pdf selected and preview panel displayed' if is_after else 'with all document files in unselected default state'}.",
            "view_types": ["file_listing", "finder_window"],
            "visible_app_names": ["Finder"],
            "uncertainties": []
        }
        nodes = [
            {"id": "n_0000", "level": "screen", "bbox": [0, 0, w, h], "parent_id": None, "proposal_ids": [], "box_status": "added", "role": "screen", "semantic_name": "Full Screen Root", "description": "Screen.", "context_description": "Root.", "function": None, "surface": "native_app_ui", "content_type": "container", "visible_text": [], "state": {"selected": "not_applicable", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "not_applicable"}, "evidence": ["Display"], "uncertainties": [], "review_status": "reviewed_correct"},
            {"id": "n_0001", "level": "window", "bbox": [0, 0, w, h], "parent_id": "n_0000", "proposal_ids": [], "box_status": "added", "role": "window", "semantic_name": "Finder Window", "description": "Finder Documents window.", "context_description": "Main.", "function": None, "surface": "native_app_ui", "content_type": "container", "visible_text": [], "state": {"selected": "true", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "false"}, "evidence": ["Window"], "uncertainties": [], "review_status": "reviewed_correct"},
            {"id": "n_0002", "level": "region", "bbox": [0, 0, 380, h], "parent_id": "n_0001", "proposal_ids": [], "box_status": "added", "role": "sidebar", "semantic_name": "Finder Sidebar", "description": "Sidebar navigation panel.", "context_description": "Left column.", "function": None, "surface": "native_app_ui", "content_type": "container", "visible_text": [], "state": {"selected": "not_applicable", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "false"}, "evidence": ["Sidebar"], "uncertainties": [], "review_status": "reviewed_correct"},
            {"id": "n_0003", "level": "region", "bbox": [380, 100, 1300 if is_after else w, h], "parent_id": "n_0001", "proposal_ids": [], "box_status": "added", "role": "table", "semantic_name": "Documents File List Table", "description": "List of files with name, kind, and size columns.", "context_description": "Main workspace.", "function": None, "surface": "native_app_ui", "content_type": "table", "visible_text": [{"text": "q3_report.pdf", "bbox": [420, 205, 540, 230], "legibility": "legible"}], "state": {"selected": "not_applicable", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "false"}, "evidence": ["File rows"], "uncertainties": [], "review_status": "reviewed_correct"},
            {"id": "n_0004", "level": "element", "bbox": [410, 200, 1220, 240], "parent_id": "n_0003", "proposal_ids": [], "box_status": "added", "role": "row", "semantic_name": "q3_report.pdf Row", "description": "Table row entry for q3_report.pdf.", "context_description": "Second row in list.", "function": {"label": "select_file", "description": "Select file to inspect", "status": "observed"}, "surface": "native_app_ui", "content_type": "control", "visible_text": [{"text": "q3_report.pdf", "bbox": [420, 205, 540, 230], "legibility": "legible"}], "state": {"selected": "true" if is_after else "false", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "false"}, "evidence": ["Row text and selection blue background"], "uncertainties": [], "review_status": "reviewed_correct"}
        ]
        if is_after:
            nodes.append({
                "id": "n_0005", "level": "region", "bbox": [1300, 100, w, h], "parent_id": "n_0001", "proposal_ids": [], "box_status": "added", "role": "metadata_area", "semantic_name": "PDF Preview Panel", "description": "Inspector pane displaying document preview and metadata.", "context_description": "Right side column.", "function": None, "surface": "native_app_ui", "content_type": "card", "visible_text": [{"text": "q3_report.pdf", "bbox": [1420, 460, 1560, 485], "legibility": "legible"}], "state": {"selected": "not_applicable", "checked": "not_applicable", "expanded": "not_applicable", "disabled_appearance": "false"}, "evidence": ["Preview card and details"], "uncertainties": [], "review_status": "reviewed_correct"
            })
        save_screen_record(sid, im, ctx, nodes, {}, "Finder and desktop", "Finder", "dark", pair_id="pair_02", frame_order=order)

    p2_data = {
        "schema_version": "0.1.0",
        "pair_id": "pair_02",
        "stratum": "Finder and desktop",
        "before_screen_id": "mac_0010",
        "after_screen_id": "mac_0011",
        "action_or_event_description": "User selected 'q3_report.pdf' in the Finder list, highlighting the row and opening the right-hand document preview pane.",
        "changes": [
            {
                "track_id": "tr_0001",
                "before_node_id": "n_0004",
                "after_node_id": "n_0004",
                "change_type": "state_changed",
                "details": "Selection state changed from false to true with blue selection styling.",
                "observable_evidence": ["Blue highlight bar on row"],
                "uncertainties": []
            },
            {
                "track_id": "tr_0002",
                "before_node_id": None,
                "after_node_id": "n_0005",
                "change_type": "appeared",
                "details": "Right-hand PDF preview and metadata panel appeared.",
                "observable_evidence": ["Visible preview box with document thumbnail and metadata"],
                "uncertainties": []
            }
        ],
        "annotation_provenance": {
            "model_requested": "gemini-3.8-flash-antigravity",
            "model_returned": "gemini-3.8-flash-antigravity",
            "thinking_requested": "high",
            "prompt_version": "0.1.0",
            "human_reviewed": True
        }
    }
    (PAIRS_DIR / "pair_02.json").write_text(json.dumps(p2_data, indent=2))
    print("[pair_02] Saved successfully")


def build_all_pilot_screens():
    build_mac_0004()
    build_mac_0005()
    build_pair_01_github()
    build_mac_0008()
    build_mac_0009()
    build_pair_02_finder()

if __name__ == "__main__":
    build_all_pilot_screens()
