/**
 * Task: Send a WhatsApp Message to Any Contact
 *
 * Description:
 * Sends a text message to a specified contact on WhatsApp Desktop (macOS).
 * WhatsApp is a Catalyst/native app — its full accessibility tree is exposed
 * in a single snapshot call (no DFS drill-down needed, unlike Electron apps).
 *
 * Flow:
 * 1. Launch WhatsApp, find the visible window by scanning all windows for title "WhatsApp"
 *    (Catalyst apps don't appear in `list-windows --app`, must use `list-windows` globally).
 * 2. Snapshot → find Search textfield (role=textfield, name="Search") → click it.
 * 3. Paste contact name via clipboard → wait for search results.
 * 4. Re-snapshot → grep for contact name → click the matching button.
 * 5. Re-snapshot → find "Compose message" textfield → click it.
 * 6. Paste message via clipboard → press Enter to send.
 *
 * Key Learnings:
 * - WhatsApp macOS is Catalyst/native → FULL AX tree in ONE snapshot. No DFS needed.
 * - Catalyst apps don't register in `list-windows --app WhatsApp`. Use `list-windows`
 *   (global) and filter by window title containing "WhatsApp".
 * - The search textfield is role=textfield, name="Search" (ref ~e19).
 * - The compose input is role=textfield, name="Compose message" (ref ~e70).
 * - Clipboard paste (cmd+v) is more reliable than `type` for both search and message.
 *
 * Usage:
 *   node send_whatsapp_message.js "Contact Name" "Your message here"
 *   node send_whatsapp_message.js "silicon gaddha" "gettting richh soon"
 *
 * Requirements:
 *   - WhatsApp Desktop installed at /Applications/WhatsApp.app
 *   - agent-desktop installed at /Users/harshit/Desktop/YC/agent-desktop/npm
 */

const { spawnSync } = require('child_process');
const AGENT = '/Users/harshit/Desktop/YC/agent-desktop/npm/bin/agent-desktop.js';

const CONTACT = process.argv[2];
const MESSAGE = process.argv[3];
if (!CONTACT || !MESSAGE) {
    console.error('Usage: node send_whatsapp_message.js "<contact>" "<message>"');
    process.exit(1);
}

function runJSON(args) {
    const r = spawnSync(AGENT, args, { encoding: 'utf8', timeout: 30000 });
    try { return JSON.parse(r.stdout); } catch { return null; }
}
function shell(cmd) { spawnSync('sh', ['-c', cmd], { encoding: 'utf8' }); }
function press(keys) {
    console.log(`  ⌨️  ${keys}`);
    return runJSON(['--headed', 'press', keys]);
}

function findWhatsAppWindow() {
    // Catalyst apps don't show up in list-windows --app. Must scan all windows.
    const all = runJSON(['list-windows']);
    if (!all?.ok) return null;
    return all.data.find(w => w.visible && (w.title || '').includes('WhatsApp'));
}

function snapshot(windowId) {
    return runJSON(['snapshot', '--window-id', windowId, '-i', '--include-bounds']);
}

function findNode(node, matchFn) {
    if (matchFn(node)) return node;
    for (const child of node.children || []) {
        const found = findNode(child, matchFn);
        if (found) return found;
    }
    return null;
}

function findAll(node, matchFn, results = []) {
    if (matchFn(node)) results.push(node);
    for (const child of node.children || []) {
        findAll(child, matchFn, results);
    }
    return results;
}

function clickCenter(node) {
    const { x, y, width, height } = node.bounds;
    const cx = Math.floor(x + width / 2);
    const cy = Math.floor(y + height / 2);
    console.log(`  Click → (${cx}, ${cy})`);
    return runJSON(['--headed', 'mouse-click', '--xy', `${cx},${cy}`]);
}

function main() {
    // 1. Launch WhatsApp
    console.log(`Sending "${MESSAGE}" to "${CONTACT}"...\n`);
    console.log('1. Launching WhatsApp...');
    shell('open -a WhatsApp');
    shell('sleep 3');
    shell(`osascript -e 'tell application "WhatsApp" to activate'`);
    shell('sleep 2');

    const win = findWhatsAppWindow();
    if (!win) { console.error('No WhatsApp window found.'); process.exit(1); }
    console.log(`   Window: ${win.id}`);

    // 2. Find and click Search
    console.log('2. Opening search...');
    const snap1 = snapshot(win.id);
    if (!snap1?.ok) { console.error('Snapshot failed.'); process.exit(1); }

    const searchField = findNode(snap1.data.tree, n =>
        n.role === 'textfield' && (n.name || '').includes('Search') && n.ref_id
    );
    if (searchField) {
        clickCenter(searchField);
        shell('sleep 0.5');
    }

    // 3. Type contact name
    console.log(`3. Searching "${CONTACT}"...`);
    runJSON(['clipboard-set', CONTACT]);
    press('cmd+v');
    shell('sleep 2');

    // 4. Find and click contact
    console.log('4. Clicking contact...');
    const snap2 = snapshot(win.id);
    if (!snap2?.ok) { console.error('Post-search snapshot failed.'); process.exit(1); }

    const contactNode = findNode(snap2.data.tree, n =>
        (n.role === 'button' || n.role === 'cell') &&
        (n.name || '').toLowerCase().includes(CONTACT.toLowerCase().split(' ')[0]) &&
        n.ref_id && n.bounds?.height > 0
    );

    if (contactNode) {
        clickCenter(contactNode);
    } else {
        console.log('   Contact not in tree, pressing Enter...');
        press('return');
    }
    shell('sleep 2');

    // Make absolutely sure WhatsApp is focused before we type
    runJSON(['focus-window', win.id]);
    shell('sleep 0.5');

    // 5. Find compose field and type message
    console.log('5. Typing message...');
    const snap3 = snapshot(win.id);
    if (!snap3?.ok) { console.error('Chat snapshot failed.'); process.exit(1); }

    const composeField = findNode(snap3.data.tree, n =>
        n.role === 'textfield' && (n.name || '').includes('Compose') && n.ref_id && n.bounds?.height > 0
    );
    if (composeField) {
        clickCenter(composeField);
        shell('sleep 0.3');
    } else {
        console.log('   Compose field not found. Trying blind click near bottom...');
        // Fallback: click near bottom center of window
        const winBounds = snap3.data.tree.bounds || { x: 500, y: 500, width: 800, height: 600 };
        const cx = Math.floor(winBounds.x + winBounds.width / 2);
        const cy = Math.floor(winBounds.y + winBounds.height - 50);
        runJSON(['--headed', 'mouse-click', '--xy', `${cx},${cy}`]);
        shell('sleep 0.3');
    }

    runJSON(['clipboard-set', MESSAGE]);
    press('cmd+v');
    shell('sleep 0.5');

    // 6. Send
    console.log('6. Sending...');
    press('return');

    console.log(`\n✅ "${MESSAGE}" sent to "${CONTACT}"!`);
}

main();
