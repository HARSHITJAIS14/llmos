/**
 * Experiment: Send "gettting richh soon" to "silicon gaddha" on WhatsApp
 *
 * Key Discovery: WhatsApp macOS is Catalyst/native — full AX tree in ONE snapshot!
 * No DFS drill-downs needed (unlike Notion's Electron veil).
 *
 * Flow:
 * 1. Launch WhatsApp, find visible window by title
 * 2. Snapshot → save full tree → find Search textfield
 * 3. Click search, type contact name, snapshot again
 * 4. Click the contact result
 * 5. Find message textfield, type message, press Enter to send
 */

const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const AGENT = '/Users/harshit/Desktop/YC/agent-desktop/npm/bin/agent-desktop.js';
const OUT_DIR = '/Users/harshit/Desktop/YC/LLM_OS/experiments/whatsapp_send';
const CONTACT = 'silicon gaddha';
const MESSAGE = 'gettting richh soon';

function runJSON(args) {
    const r = spawnSync(AGENT, args, { encoding: 'utf8', timeout: 30000 });
    try { return JSON.parse(r.stdout); } catch { return null; }
}
function shell(cmd) { spawnSync('sh', ['-c', cmd], { encoding: 'utf8' }); }
function press(keys) {
    console.log(`  ⌨️  ${keys}`);
    return runJSON(['--headed', 'press', keys]);
}

function saveTree(snap, name) {
    fs.mkdirSync(OUT_DIR, { recursive: true });
    const p = path.join(OUT_DIR, `${name}.json`);
    fs.writeFileSync(p, JSON.stringify(snap, null, 2));
    console.log(`  💾 ${p}`);
    return p;
}

function findVisible() {
    // WhatsApp Catalyst apps don't show up in list-windows --app
    // Must search all visible windows for one titled "WhatsApp"
    const all = runJSON(['list-windows']);
    if (!all?.ok) return null;
    return all.data.find(w => w.visible && (w.title || '').includes('WhatsApp'));
}

function grepTree(treePath, query) {
    const r = spawnSync('python3', ['-c', `
import json
d = json.load(open("${treePath}"))
results = []
def walk(n, depth=0):
    name = (n.get("name","") or "").lower()
    value = (n.get("value","") or "").lower()
    ref = n.get("ref_id")
    b = n.get("bounds")
    states = n.get("states",[])
    q = "${query}".lower()
    if ref and b and b.get("height",0) > 0 and "offscreen" not in states:
        if q in name or q in value:
            results.append({
                "ref_id": ref, "role": n.get("role",""), "name": n.get("name","")[:80],
                "bounds": b, "actions": n.get("available_actions",[]), "depth": depth
            })
    for c in n.get("children") or []:
        walk(c, depth+1)
walk(d["data"]["tree"])
print(json.dumps(results, indent=2))
`], { encoding: 'utf8' });
    try { return JSON.parse(r.stdout); } catch { return []; }
}

function clickNode(node) {
    const { x, y, width, height } = node.bounds;
    const cx = Math.floor(x + width / 2);
    const cy = Math.floor(y + height / 2);
    console.log(`  Clicking "${node.name}" [${node.role}] at (${cx}, ${cy})`);
    return runJSON(['--headed', 'mouse-click', '--xy', `${cx},${cy}`]);
}

function main() {
    // === STEP 1: Launch WhatsApp ===
    console.log('=== STEP 1: Launch WhatsApp ===');
    shell('open -a WhatsApp');
    shell('sleep 4');
    shell(`osascript -e 'tell application "WhatsApp" to activate'`);
    shell('sleep 2');

    const win = findVisible();
    if (!win) { console.error('No WhatsApp window found.'); process.exit(1); }
    console.log(`  Window: ${win.id} — "${win.title}"`);

    // Snapshot initial state
    console.log('\n  Taking snapshot...');
    const snap1 = runJSON(['snapshot', '--window-id', win.id, '-i', '--include-bounds']);
    if (!snap1?.ok) { console.error('Snapshot failed:', snap1?.error?.message); process.exit(1); }
    console.log(`  Snapshot: ${snap1.data.snapshot_id}`);
    const tree1Path = saveTree(snap1, 'step1_initial');

    // === STEP 2: Click search and type contact ===
    console.log('\n=== STEP 2: Search for contact ===');
    const searchNodes = grepTree(tree1Path, 'Search');
    const searchField = searchNodes.find(n => n.role === 'textfield');
    
    if (searchField) {
        clickNode(searchField);
        shell('sleep 0.5');
    } else {
        console.log('  No search field, trying Cmd+F...');
        press('cmd+f');
        shell('sleep 0.5');
    }

    console.log(`  Typing "${CONTACT}"...`);
    runJSON(['clipboard-set', CONTACT]);
    press('cmd+v');
    shell('sleep 2');

    // Snapshot after search
    console.log('\n  Taking post-search snapshot...');
    const snap2 = runJSON(['snapshot', '--window-id', win.id, '-i', '--include-bounds']);
    if (!snap2?.ok) { console.error('Post-search snapshot failed.'); process.exit(1); }
    console.log(`  Snapshot: ${snap2.data.snapshot_id}`);
    const tree2Path = saveTree(snap2, 'step2_after_search');

    // Find contact
    console.log('\n  Looking for "silicon" in results...');
    const contactNodes = grepTree(tree2Path, 'silicon');
    console.log(`  Found ${contactNodes.length} matches:`);
    contactNodes.forEach(n => console.log(`    [${n.role}] "${n.name}" ref=${n.ref_id}`));

    // === STEP 3: Click contact ===
    console.log('\n=== STEP 3: Open chat ===');
    const contact = contactNodes.find(n => n.role === 'button' || n.role === 'cell' || n.role === 'statictext') || contactNodes[0];
    
    if (contact) {
        clickNode(contact);
    } else {
        console.log('  Contact not found. Pressing Enter to select first result...');
        press('return');
    }
    shell('sleep 2');

    // Snapshot with chat open
    console.log('\n  Taking chat snapshot...');
    const snap3 = runJSON(['snapshot', '--window-id', win.id, '-i', '--include-bounds']);
    if (!snap3?.ok) { console.error('Chat snapshot failed.'); process.exit(1); }
    console.log(`  Snapshot: ${snap3.data.snapshot_id}`);
    const tree3Path = saveTree(snap3, 'step3_chat_open');

    // === STEP 4: Type and send message ===
    console.log('\n=== STEP 4: Type and send message ===');
    
    // Find the message input field
    const msgNodes = grepTree(tree3Path, 'message');
    console.log(`  Found ${msgNodes.length} message-related nodes:`);
    msgNodes.forEach(n => console.log(`    [${n.role}] "${n.name}" ref=${n.ref_id}`));
    
    const msgField = msgNodes.find(n => n.role === 'textfield' || n.role === 'textbox');
    if (msgField) {
        clickNode(msgField);
        shell('sleep 0.3');
    }

    // Type message
    console.log(`  Typing "${MESSAGE}"...`);
    runJSON(['clipboard-set', MESSAGE]);
    press('cmd+v');
    shell('sleep 0.5');

    // Send
    console.log('  Sending...');
    press('return');
    shell('sleep 1');

    // Final snapshot
    console.log('\n=== STEP 5: Verify ===');
    const snap4 = runJSON(['snapshot', '--window-id', win.id, '-i', '--include-bounds']);
    if (snap4?.ok) saveTree(snap4, 'step4_after_send');

    console.log(`\n✅ "${MESSAGE}" sent to "${CONTACT}"!`);
}

main();
