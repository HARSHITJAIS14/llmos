/**
 * capture_finder_snapshot.js
 * 
 * Captures a pretty-printed accessibility tree snapshot of the frontmost
 * visible Finder window using agent-desktop.
 * 
 * Output:
 *   finder_window_snapshot_pretty.json  — full pretty-printed tree with bounds
 * 
 * Usage:
 *   node capture_finder_snapshot.js
 *   (Run from the agent-desktop/npm directory so bin/agent-desktop.js resolves)
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const AGENT_BIN = '/Users/harshit/Desktop/YC/agent-desktop/npm/bin/agent-desktop.js';
const OUT_DIR = path.resolve(__dirname);

function runCmd(cmd) {
    return execSync(cmd, { stdio: 'pipe', encoding: 'utf8' });
}

// 1. Activate Finder
console.log('Activating Finder...');
runCmd(`osascript -e 'tell application "Finder" to activate'`);
runCmd('sleep 1');

// 2. List windows and find the visible one
console.log('Finding visible Finder window...');
const listOut = runCmd(`${AGENT_BIN} list-windows --app Finder`);
const windows = JSON.parse(listOut).data;
const target = windows.find(w => w.visible) || windows[0];

if (!target) {
    console.error('No Finder window found.');
    process.exit(1);
}
console.log(`Targeting window: ${target.id} (${target.title || 'Finder'})`);

// 3. Take snapshot with bounds
console.log('Taking snapshot...');
const raw = runCmd(`${AGENT_BIN} snapshot --window-id ${target.id} -i --include-bounds --compact`);
const parsed = JSON.parse(raw);

if (!parsed.ok) {
    console.error('Snapshot failed:', parsed.error.message);
    process.exit(1);
}

// 4. Pretty-print and save
const prettyPath = path.join(OUT_DIR, 'finder_window_snapshot_pretty.json');
fs.writeFileSync(prettyPath, JSON.stringify(parsed, null, 4));
console.log(`\nSnapshot saved → ${prettyPath}`);
console.log(`Snapshot ID : ${parsed.data.snapshot_id}`);
console.log(`Ref count   : ${parsed.data.ref_count} interactive elements`);
