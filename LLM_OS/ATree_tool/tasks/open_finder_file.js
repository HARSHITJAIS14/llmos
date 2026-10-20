/**
 * Task: Open a File in Finder by Name
 *
 * Description:
 * Opens any file visible in the frontmost Finder window by searching for it
 * by name in the accessibility tree and firing a physical double-click on it.
 *
 * This is the verified, working pattern for opening files via OS automation.
 *
 * Key Learnings:
 * - Finder is a native AppKit app → single snapshot call returns a full, rich tree.
 * - Semantic click (AXPress / AXOpen) does NOT open files — the textfield role
 *   in Finder's column view needs a physical double-click (CGClick).
 * - `--headed double-click` sends a hardware-level double-click, bypassing all
 *   semantic API limitations.
 * - Ref IDs are tied to a snapshot session — always take a fresh snapshot before acting.
 * - Finder has many hidden background windows; always iterate through candidates
 *   and try snapshotting each one until one succeeds.
 *
 * Usage:
 *   node open_finder_file.js "Congratulations_on_Your_Internship_Harshit_J.pdf"
 *   node open_finder_file.js "report.pdf"
 *
 * Requirements:
 *   - agent-desktop installed at /Users/harshit/Desktop/YC/agent-desktop/npm
 *   - Finder must have a visible window open showing the target file
 */

const { spawnSync } = require('child_process');
const AGENT = '/Users/harshit/Desktop/YC/agent-desktop/npm/bin/agent-desktop.js';

const TARGET_NAME = process.argv[2];
if (!TARGET_NAME) {
    console.error('Usage: node open_finder_file.js "<filename>"');
    process.exit(1);
}

// Run a command and return parsed JSON. Returns null on failure (no crash).
function runJSON(args) {
    const result = spawnSync(AGENT, args, { encoding: 'utf8' });
    try { return JSON.parse(result.stdout); } catch { return null; }
}

// Run a shell command via osascript/sleep
function runShell(cmd) {
    spawnSync('sh', ['-c', cmd], { encoding: 'utf8' });
}

// 1. Activate Finder and wait
console.log('Activating Finder...');
runShell(`osascript -e 'tell application "Finder" to activate'`);
runShell('sleep 2');

// 2. Find the real Finder window — it has a meaningful title (e.g. "Recents", "Desktop", folder name)
//    Background/ghost windows all have the generic title "Finder" and fail to snapshot.
const listResult = runJSON(['list-windows', '--app', 'Finder']);
if (!listResult?.ok) { console.error('Could not list Finder windows.'); process.exit(1); }

const windows = listResult.data;
const target =
    windows.find(w => w.title && w.title !== 'Finder') ||   // Real named window (Recents, folder, etc.)
    windows.find(w => w.is_focused) ||                        // Fallback: focused
    windows.find(w => w.visible);                             // Fallback: visible

if (!target) { console.error('No usable Finder window found.'); process.exit(1); }
console.log(`Window : ${target.id} — "${target.title}"`);

// 3. Snapshot by window-id (--surface focused captures Desktop, not Finder window)
console.log('Taking snapshot...');
const snap = runJSON(['snapshot', '--window-id', target.id, '-i', '--include-bounds', '--compact']);

if (!snap?.ok) {
    console.error('Snapshot failed:', snap?.error?.message || 'Unknown error');
    process.exit(1);
}
console.log(`Snapshot ID : ${snap.data.snapshot_id}`);


// 4. Walk the tree to find the target file by name or value
function findFile(node, name) {
    const val = (node.value || node.name || '');
    if (val.includes(name) && node.ref_id) return node;
    for (const child of node.children || []) {
        const found = findFile(child, name);
        if (found) return found;
    }
    return null;
}

const fileNode = findFile(snap.data.tree, TARGET_NAME);
if (!fileNode) {
    console.error(`\nFile "${TARGET_NAME}" not found in the Finder window. Is it visible on screen?`);
    process.exit(1);
}

console.log(`Found  : ${fileNode.ref_id} [${fileNode.role}] → "${fileNode.value || fileNode.name}"`);

// 5. Physical double-click (semantic double-click is POLICY_DENIED on textfield role)
console.log('Opening with physical double-click...');
const clickResult = runJSON(['--headed', 'double-click', fileNode.ref_id]);

if (clickResult?.ok) {
    const step = clickResult.data.steps?.[0];
    console.log(`\n✅ "${TARGET_NAME}" opened successfully.`);
    console.log(`   Mechanism : ${step?.mechanism}`);
    console.log(`   Outcome   : ${step?.outcome}`);
} else {
    console.error('\n❌ Click failed:', clickResult?.error?.message);
    process.exit(1);
}

