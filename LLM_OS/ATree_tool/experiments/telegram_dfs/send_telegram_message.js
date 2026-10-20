/**
 * Task: Send Telegram Message using DFS and Stealth Clicks
 * 
 * 1. Activates Telegram and brings it to front.
 * 2. Takes a snapshot of the main window.
 * 3. Uses DFS to drill down into truncated nodes to build the full tree.
 * 4. Saves the full tree to `experiments/telegram_dfs/telegram_full_tree.json`.
 * 5. Greps the tree to find the Search field bounds.
 * 6. Uses stealthClick() to focus the Search field.
 * 7. Uses clipboard macros to paste the contact name, press enter, paste message, press enter.
 */

const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const { stealthClick } = require('../../utils/mouse.js');

const AGENT = '/Users/harshit/Desktop/YC/agent-desktop/npm/bin/agent-desktop.js';
const OUT_DIR = '/Users/harshit/Desktop/YC/LLM_OS/experiments/telegram_dfs';
const MAX_DRILL = 30;
let drillCount = 0;
let snapshotId = null;

const CONTACT = process.argv[2] || "gradiator iitk";
const MESSAGE = process.argv[3] || "Hi";

function shell(cmd) {
    console.log(`> ${cmd}`);
    const r = spawnSync('sh', ['-c', cmd], { encoding: 'utf8' });
    if (r.status !== 0) {
        console.error(`Command failed: ${cmd}\n${r.stderr}`);
    }
    return r.stdout.trim();
}

function runJSON(args) {
    const r = spawnSync(AGENT, args, { encoding: 'utf8', timeout: 30000 });
    try { return JSON.parse(r.stdout); } catch { return null; }
}

function findByNativeId(node, value) {
    if (node.native_id?.value === value) return node;
    for (const child of node.children || []) {
        const found = findByNativeId(child, value);
        if (found) return found;
    }
    return null;
}

// DFS to expand any node that has children but no children array, OR is marked subtree_truncated
function dfs(node) {
    if (drillCount >= MAX_DRILL) return;
    if (!node.ref_id) return;

    const needsDrill = node.subtree_truncated || (node.children_count > 0 && (!node.children || node.children.length === 0));

    if (needsDrill) {
        process.stdout.write(`  [${drillCount + 1}/${MAX_DRILL}] ${node.ref_id} ... `);
        drillCount++;
        const result = runJSON(['snapshot', '--root', node.ref_id, '--snapshot', snapshotId, '-i', '--include-bounds']);
        
        if (result?.ok && result.data?.tree) {
            node.children = result.data.tree.children || [];
            node.subtree_truncated = false; // Resolved
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
    console.log('1. Launching Telegram and waiting for window...');
    const launch = runJSON(['launch', 'Telegram']);
    if (!launch?.ok) {
        console.error('Failed to launch Telegram.');
        process.exit(1);
    }
    const target = launch.data.window;
    if (!target) {
        console.error('No Telegram window found.');
        process.exit(1);
    }
    console.log(`Window: ${target.id} — "${target.title}"`);

    console.log('\n2. Taking initial snapshot...');
    const snap = runJSON(['snapshot', '--window-id', target.id, '-i', '--include-bounds']);
    if (!snap?.ok) { console.error('Snapshot failed:', snap?.error?.message); process.exit(1); }

    snapshotId = snap.data.snapshot_id;
    const root = snap.data.tree;
    console.log(`Snapshot ID: ${snapshotId}`);

    console.log('\n3. Expanding tree (DFS)...');
    dfs(root);
    console.log(`Done. ${drillCount} drill-downs used.`);

    fs.mkdirSync(OUT_DIR, { recursive: true });
    const outPath = path.join(OUT_DIR, 'telegram_full_tree.json');
    fs.writeFileSync(outPath, JSON.stringify(snap, null, 2));
    console.log(`\n4. Saved fully expanded tree → ${outPath}`);

    console.log('\n5. Searching for Search field...');
    const grep = spawnSync('python3', ['-c', `
import json
d = json.load(open("${outPath}"))
results = []
def walk(n):
    role = n.get("role", "") or ""
    name = n.get("name", "") or ""
    desc = n.get("description", "") or ""
    value = n.get("value", "") or ""
    
    # Looking for something indicating search
    text_content = (name + " " + desc + " " + value).lower()
    if "search" in text_content and ("text" in role.lower() or "group" in role.lower() or "button" in role.lower()):
        results.append({
            "ref_id": n.get("ref_id"),
            "role": role,
            "name": name,
            "bounds": n.get("bounds")
        })
    for c in n.get("children") or []:
        walk(c)
walk(d["data"]["tree"])
print(json.dumps(results, indent=2))
`], { encoding: 'utf8' });

    let matches = [];
    try { matches = JSON.parse(grep.stdout); } catch {}
    
    if (matches.length === 0) {
        console.log('\n⚠️  No search field found in the DFS tree! Telegram is completely masking its DOM from macOS Accessibility.');
        console.log('Fallback: Using pure Keyboard Macros (Option B from learnings.md)...');
        
        console.log('Bringing Telegram to focus...');
        shell(`osascript -e 'tell application "Telegram" to activate'`);
        shell('sleep 1');
        
        console.log('Pressing Cmd+F to focus search...');
        shell(`${AGENT} --headed press cmd+f`);
        shell('sleep 1');
    } else {
        console.log('Search matches found:', JSON.stringify(matches, null, 2));

        const validMatches = matches.filter(m => m.bounds && m.bounds.height > 0 && m.bounds.width > 0);
        if (validMatches.length > 0) {
            const searchBar = validMatches[0];
            console.log(`\nSelected Search Bar: ${searchBar.ref_id} (${searchBar.role})`);

            const { x, y, width, height } = searchBar.bounds;
            const cx = Math.floor(x + width / 2);
            const cy = Math.floor(y + height / 2);

            console.log('\n6. Stealth Clicking the Search Bar...');
            shell(`${AGENT} focus-window ${target.id}`); 
            
            const clicked = stealthClick(cx, cy);
            if (!clicked) {
                console.error('Stealth click failed.');
                process.exit(1);
            }
            console.log(`✅ Stealth Clicked at (${cx}, ${cy})`);
            shell('sleep 0.5');
        } else {
            console.log('\n⚠️  Search fields found but all have 0 bounds. Falling back to Cmd+F...');
            shell(`osascript -e 'tell application "Telegram" to activate'`);
            shell('sleep 1');
            shell(`${AGENT} --headed press cmd+f`);
            shell('sleep 1');
        }
    }

    console.log(`\n7. Searching for contact "${CONTACT}"...`);
    shell(`osascript -e 'tell application "Telegram" to activate'`); // Ensure focus again
    shell(`${AGENT} clipboard-set "${CONTACT}"`);
    shell(`${AGENT} --headed press cmd+v`);
    
    console.log('Waiting for search results...');
    shell('sleep 3');

    console.log('Pressing Return to select contact...');
    shell(`${AGENT} --headed press return`);
    
    shell('sleep 1'); 

    console.log(`\n8. Typing message "${MESSAGE}"...`);
    shell(`${AGENT} clipboard-set "${MESSAGE}"`);
    shell(`${AGENT} --headed press cmd+v`);
    
    console.log('Sending message...');
    shell(`${AGENT} --headed press return`);

    console.log(`\n✅ Message sent successfully to ${CONTACT}!`);
}

main();
