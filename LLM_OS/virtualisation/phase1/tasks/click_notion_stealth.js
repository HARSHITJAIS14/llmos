/**
 * Task: Click the "Library" Tab in Notion
 *
 * Description:
 * 1. Activates Notion, finds the real visible window.
 * 2. Takes ONE full snapshot.
 * 3. DFS drills every truncated node to expand the tree in-memory.
 * 4. Saves ONE complete, fully-expanded, pretty-printed JSON tree.
 * 5. Greps that JSON for the "Library" button's bounds.
 * 6. Fires a physical blind coordinate click at the center of the button.
 *
 * Output:
 *   experiments/notion_dfs/notion_full_tree.json — the single complete tree
 *
 * Usage:
 *   node click_notion_library.js
 */

const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const AGENT = '/Users/harshit/Desktop/YC/agent-desktop/npm/bin/agent-desktop.js';
const OUT_DIR = '/Users/harshit/Desktop/YC/LLM_OS/experiments/notion_dfs';
const MAX_DRILL = 20;
let drillCount = 0;
let snapshotId = null;

function runJSON(args) {
    const r = spawnSync(AGENT, args, { encoding: 'utf8', timeout: 30000 });
    try { return JSON.parse(r.stdout); } catch { return null; }
}

function shell(cmd) {
    spawnSync('sh', ['-c', cmd], { encoding: 'utf8' });
}

function findByNativeId(node, value) {
    if (node.native_id?.value === value) return node;
    for (const child of node.children || []) {
        const found = findByNativeId(child, value);
        if (found) return found;
    }
    return null;
}

// DFS: expand every truncated node in-place. No individual saves.
function dfs(node) {
    if (drillCount >= MAX_DRILL) return;
    if (!node.ref_id) return;

    if (node.children_count > 0 && (!node.children || node.children.length === 0)) {
        process.stdout.write(`  [${drillCount + 1}/${MAX_DRILL}] ${node.ref_id} ... `);
        drillCount++;
        const result = runJSON(['snapshot', '--root', node.ref_id, '--snapshot', snapshotId, '-i', '--include-bounds']);
        if (result?.ok && result.data?.tree) {
            node.children = result.data.tree.children || [];
            console.log(`✅ ${node.children.length} children`);
        } else {
            console.log(`❌ ${result?.error?.code || 'FAILED'}`);
        }
    }

    for (const child of node.children || []) {
        dfs(child);
    }
}

function main() {
    // 1. Activate Notion
    console.log('Activating Notion...');
    shell(`osascript -e 'tell application "Notion" to activate'`);
    shell('sleep 2');

    // 2. Find the real window (visible+focused, with a real page title)
    const listResult = runJSON(['list-windows', '--app', 'Notion']);
    if (!listResult?.ok) { console.error('Could not list Notion windows.'); process.exit(1); }

    const windows = listResult.data;
    const target =
        windows.find(w => w.visible && w.is_focused) ||
        windows.find(w => w.visible) ||
        windows.find(w => w.is_focused) ||
        windows[0];

    if (!target) { console.error('No Notion window found.'); process.exit(1); }
    console.log(`Window: ${target.id} — "${target.title}"`);

    // 3. Full initial snapshot
    console.log('Taking full snapshot...');
    const snap = runJSON(['snapshot', '--window-id', target.id, '-i', '--include-bounds']);
    if (!snap?.ok) { console.error('Snapshot failed:', snap?.error?.message); process.exit(1); }

    snapshotId = snap.data.snapshot_id;
    const root = snap.data.tree;
    console.log(`Snapshot: ${snapshotId}\n`);

    // 4. DFS — expand all truncated nodes in-memory
    console.log('Expanding tree (DFS)...');
    const notionApp = findByNativeId(root, 'notion-app');
    if (notionApp) {
        console.log(`  Found notion-app at ${notionApp.ref_id}`);
        dfs(notionApp);
    } else {
        dfs(root);
    }
    console.log(`  Done. ${drillCount} drill-downs used.\n`);

    // 5. Save ONE fully expanded tree
    fs.mkdirSync(OUT_DIR, { recursive: true });
    const outPath = path.join(OUT_DIR, 'notion_full_tree.json');
    fs.writeFileSync(outPath, JSON.stringify(snap, null, 2));
    console.log(`Saved → ${outPath}\n`);

    // 6. Grep the saved file for ALL nodes matching "Library" (any role)
    console.log('Searching for all nodes containing "Library"...');
    const grep = spawnSync('python3', ['-c', `
import json
d = json.load(open("${outPath}"))
results = []
def walk(n, depth=0):
    name = n.get("name", "") or ""
    value = n.get("value", "") or ""
    if "Library" in name or "Library" in value:
        results.append({
            "ref_id": n.get("ref_id"),
            "role": n.get("role"),
            "name": name,
            "value": value,
            "bounds": n.get("bounds"),
            "states": n.get("states", []),
            "available_actions": n.get("available_actions", []),
            "depth": depth
        })
    for c in n.get("children") or []:
        walk(c, depth+1)
walk(d["data"]["tree"])
print(json.dumps(results, indent=2))
print(f"\\nTotal matches: {len(results)}")
`], { encoding: 'utf8' });

    console.log(grep.stdout);
    if (grep.stderr) console.error('grep stderr:', grep.stderr);

    // Parse and pick the Library button
    let matches = [];
    try { matches = JSON.parse(grep.stdout.split('\nTotal')[0]); } catch {}

    if (matches.length === 0) {
        console.error('No "Library" nodes found in tree at all.');
        process.exit(1);
    }

    let lib = matches.find(m => m.role === 'button' && m.name === 'Library');
    if (!lib) { console.error('No Library button in matches.'); process.exit(1); }

    console.log(`\nLibrary button: ${lib.ref_id}`);
    console.log(`  bounds: ${JSON.stringify(lib.bounds)}`);
    console.log(`  states: ${JSON.stringify(lib.states)}`);

    // 7. If offscreen or zero-height, scroll it into view first
    const isOffscreen = (lib.states || []).includes('offscreen') ||
                        lib.bounds?.height === 0 || lib.bounds?.width === 0;

    if (isOffscreen) {
        console.log('\n⚠️  Library is offscreen. Scrolling into view...');
        const scrollResult = runJSON(['scroll-to', lib.ref_id]);
        console.log('ScrollTo response:', JSON.stringify(scrollResult, null, 2));

        if (!scrollResult?.ok) {
            console.error('ScrollTo failed:', scrollResult?.error?.message);
            console.log('Trying ScrollTo with --snapshot flag...');
            const scrollResult2 = runJSON(['scroll-to', lib.ref_id, '--snapshot', snapshotId]);
            console.log('ScrollTo response:', JSON.stringify(scrollResult2, null, 2));
        }

        // Wait for scroll animation
        shell('sleep 1');

        // 8. Re-snapshot and re-DFS to get fresh bounds
        console.log('\nRe-snapshotting after scroll...');
        const snap2 = runJSON(['snapshot', '--window-id', target.id, '-i', '--include-bounds']);
        if (!snap2?.ok) { console.error('Re-snapshot failed:', snap2?.error?.message); process.exit(1); }

        snapshotId = snap2.data.snapshot_id;
        const root2 = snap2.data.tree;
        drillCount = 0;

        const notionApp2 = findByNativeId(root2, 'notion-app');
        if (notionApp2) { dfs(notionApp2); } else { dfs(root2); }

        // Save updated tree
        fs.writeFileSync(outPath, JSON.stringify(snap2, null, 2));
        console.log(`Updated tree saved → ${outPath}`);

        // Re-grep for Library with fresh bounds
        const grep2 = spawnSync('python3', ['-c', `
import json
d = json.load(open("${outPath}"))
def walk(n):
    name = n.get("name", "") or ""
    if name == "Library" and n.get("role") == "button":
        print(json.dumps({"ref_id": n.get("ref_id"), "bounds": n.get("bounds"), "states": n.get("states", [])}, indent=2))
    for c in n.get("children") or []:
        walk(c)
walk(d["data"]["tree"])
`], { encoding: 'utf8' });

        const found2 = grep2.stdout.trim();
        if (found2) {
            lib = JSON.parse(found2);
            console.log('Fresh Library bounds:', JSON.stringify(lib, null, 2));
        } else {
            console.error('Library not found after scroll.');
            process.exit(1);
        }
    }

    // 9. Click the Library button
    if (!lib.bounds) { console.error('No bounds on Library.'); process.exit(1); }

    const { x, y, width, height } = lib.bounds;
    const cx = Math.floor(x + width / 2);
    const cy = Math.floor(y + height / 2);

    console.log(`\nFinal bounds: x=${x} y=${y} w=${width} h=${height}`);
    console.log(`Center: (${cx}, ${cy})`);

    if (height === 0 || width === 0) {
        console.warn('⚠️  Still zero-height after scroll. Click may not work.');
    }

    console.log('Stealth Clicking...\n');
    const { stealthClick } = require('../utils/mouse.js');
    const success = stealthClick(cx, cy);

    if (success) {
        console.log(`\n✅ Stealth Clicked at (${cx}, ${cy})`);
    } else {
        console.error('\n❌ Stealth Click failed.');
        process.exit(1);
    }
}

main();
