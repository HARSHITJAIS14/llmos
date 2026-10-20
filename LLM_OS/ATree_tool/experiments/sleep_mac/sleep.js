/**
 * Experiment: Sleep the Mac via GUI (Apple Menu -> Sleep)
 *
 * Strategy:
 * 1. Snapshot the global menubar using `--surface menubar`
 * 2. Find the "Sleep" menu item inside the "Apple" menu
 * 3. Use a semantic click (`click` command without `--headed`) on the ref_id
 *    Note: Menus items are often marked "offscreen" and lack bounds until opened,
 *    but macOS Accessibility API (AXPress) handles semantic clicks on them perfectly.
 */

const { spawnSync } = require('child_process');

const AGENT = '/Users/harshit/Desktop/YC/agent-desktop/npm/bin/agent-desktop.js';

function runJSON(args) {
    const r = spawnSync(AGENT, args, { encoding: 'utf8', timeout: 30000 });
    try { return JSON.parse(r.stdout); } catch { return null; }
}

console.log('1. Snapshotting menubar...');
const snap = runJSON(['snapshot', '--app', 'Finder', '--surface', 'menubar', '-i']);
if (!snap?.ok) {
    console.error('Failed to snapshot menubar:', snap?.error?.message);
    process.exit(1);
}
const snapshotId = snap.data.snapshot_id;
console.log(`  Snapshot: ${snapshotId}`);

console.log('2. Finding Apple -> Sleep...');
let sleepRef = null;

function walk(node) {
    if (node.role === 'menuitem' && node.name === 'Sleep') {
        sleepRef = node.ref_id;
        return;
    }
    for (const child of node.children || []) {
        walk(child);
        if (sleepRef) return;
    }
}
walk(snap.data.tree);

if (!sleepRef) {
    console.error('Could not find Sleep menu item!');
    process.exit(1);
}
console.log(`  Found Sleep: ${sleepRef}`);

console.log('3. Semantic clicking Sleep...');
const clickResult = runJSON(['click', sleepRef, '--snapshot', snapshotId]);
console.log('Result:', JSON.stringify(clickResult));

if (clickResult?.ok) {
    console.log('✅ Sleep command sent via GUI!');
} else {
    console.log('❌ Failed to click Sleep.');
}
