/**
 * Experiment: Play "Money Trees by Kendrick Lamar" on YouTube Music
 *
 * Strategy:
 * 1. Open YT Music search URL directly in browser (fastest navigation)
 * 2. Wait for page load
 * 3. Use agent-desktop to find and click the first play button/song result
 *
 * Alternative: Open the URL and let the user interact manually.
 */

const { spawnSync } = require('child_process');
const AGENT = '/Users/harshit/Desktop/YC/agent-desktop/npm/bin/agent-desktop.js';

function runJSON(args) {
    const r = spawnSync(AGENT, args, { encoding: 'utf8', timeout: 30000 });
    try { return JSON.parse(r.stdout); } catch { return null; }
}
function shell(cmd) { spawnSync('sh', ['-c', cmd], { encoding: 'utf8' }); }
function press(keys) {
    console.log(`  ⌨️  ${keys}`);
    return runJSON(['--headed', 'press', keys]);
}

const SEARCH_URL = 'https://music.youtube.com/search?q=Money+Trees+Kendrick+Lamar';

// 1. Open YT Music search in default browser
console.log('1. Opening YouTube Music search...');
shell(`open "${SEARCH_URL}"`);
shell('sleep 4');

// 2. Find the browser window
console.log('2. Finding browser window...');
// Try common browsers
let browserApp = null;
for (const app of ['Google Chrome', 'Arc', 'Safari', 'Firefox', 'Brave Browser']) {
    const result = runJSON(['list-windows', '--app', app]);
    if (result?.ok && result.data?.length > 0) {
        const win = result.data.find(w => w.visible && (w.title || '').includes('YouTube Music'));
        if (win) {
            browserApp = app;
            console.log(`  Found: ${app} — ${win.id} "${win.title}"`);
            break;
        }
    }
}

if (!browserApp) {
    // Fallback: just check which app is focused
    const allWindows = runJSON(['list-windows']);
    const focused = allWindows?.data?.find(w => w.is_focused);
    if (focused) {
        browserApp = focused.app;
        console.log(`  Focused app: ${browserApp} — ${focused.id} "${focused.title}"`);
    }
}

if (!browserApp) {
    console.log('  Could not find browser. Waiting longer...');
    shell('sleep 3');
}

// 3. Take a snapshot of the browser to find the play button
console.log('3. Taking browser snapshot...');
const listResult = runJSON(['list-windows', '--app', browserApp || 'Arc']);
const windows = listResult?.data || [];
const target = windows.find(w => w.visible && (w.title || '').includes('YouTube')) ||
               windows.find(w => w.visible) ||
               windows[0];

if (!target) {
    console.error('No browser window found.');
    process.exit(1);
}
console.log(`  Window: ${target.id} — "${target.title}"`);

// Activate the browser
shell(`osascript -e 'tell application "${browserApp}" to activate'`);
shell('sleep 1');

// Snapshot
const snap = runJSON(['snapshot', '--window-id', target.id, '-i', '--include-bounds']);
if (!snap?.ok) {
    console.error('Snapshot failed:', snap?.error?.message);
    // Fallback: try clicking the first song result area
    console.log('Attempting blind keyboard play...');
    // Tab into the results and press Enter
    press('Tab');
    shell('sleep 0.5');
    press('Tab');
    shell('sleep 0.5');
    press('return');
    console.log('✅ Attempted keyboard play.');
    process.exit(0);
}

const fs = require('fs');
const path = require('path');
const OUT_DIR = '/Users/harshit/Desktop/YC/LLM_OS/experiments/ytmusic_play';
fs.mkdirSync(OUT_DIR, { recursive: true });
const treePath = path.join(OUT_DIR, 'ytmusic_tree.json');
fs.writeFileSync(treePath, JSON.stringify(snap, null, 2));
console.log(`  Tree saved → ${treePath}`);

// 4. Search for a play button or the first song result
console.log('4. Searching for song/play button...');
const grepResult = spawnSync('python3', ['-c', `
import json
d = json.load(open("${treePath}"))
results = []
def walk(n, depth=0):
    name = (n.get("name","") or "").lower()
    role = n.get("role","")
    ref = n.get("ref_id")
    b = n.get("bounds")
    states = n.get("states",[])
    actions = n.get("available_actions",[])
    
    # Look for song results or play buttons
    if ref and b and b.get("height",0) > 0 and "offscreen" not in states:
        if ("money" in name and "tree" in name) or \
           (role == "link" and "money" in name) or \
           (role == "button" and ("play" in name or "shuffle" in name)):
            results.append({
                "ref_id": ref,
                "role": role,
                "name": n.get("name","")[:80],
                "bounds": b,
                "actions": actions,
                "depth": depth
            })
    for c in n.get("children") or []:
        walk(c, depth+1)
walk(d["data"]["tree"])
for r in results[:10]:
    print(json.dumps(r, indent=2))
print(f"\\nTotal matches: {len(results)}")
`], { encoding: 'utf8' });

console.log(grepResult.stdout);

// Parse matches and click the best one
let matches = [];
try {
    const parts = grepResult.stdout.split('\nTotal')[0].trim();
    // Try to parse as array of individual JSON objects
    const jsonStrs = parts.split('\n}\n');
    for (const s of jsonStrs) {
        try { matches.push(JSON.parse(s + (s.endsWith('}') ? '' : '}'))); } catch {}
    }
} catch {}

if (matches.length > 0) {
    // Click the first song match (prefer links over buttons)
    const songLink = matches.find(m => m.role === 'link') || matches[0];
    const { x, y, width, height } = songLink.bounds;
    const cx = Math.floor(x + width / 2);
    const cy = Math.floor(y + height / 2);

    console.log(`Clicking: "${songLink.name}" at (${cx}, ${cy})`);
    const click = runJSON(['--headed', 'mouse-click', '--xy', `${cx},${cy}`]);
    console.log('Click:', click?.ok ? '✅' : '❌', JSON.stringify(click?.data || click?.error));
} else {
    console.log('No direct song match. Trying keyboard shortcut...');
    // YT Music: Tab through to results, Enter to play
    press('Tab');
    shell('sleep 0.3');
    press('return');
}

console.log('\n✅ Done! Money Trees should be playing.');
