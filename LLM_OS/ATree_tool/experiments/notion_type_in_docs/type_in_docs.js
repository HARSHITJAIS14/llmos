/**
 * Experiment: Type "successfully cracked notion" into Docs page in Notion
 *
 * Approach (pure keyboard — no coordinates needed):
 * 1. Activate Notion
 * 2. Cmd+K → type "Docs" → Enter → navigates to Docs page
 * 3. Cmd+End to jump to the end of the page
 * 4. Enter to make a new block
 * 5. Clipboard paste the text
 */

const { spawnSync } = require('child_process');
const AGENT = '/Users/harshit/Desktop/YC/agent-desktop/npm/bin/agent-desktop.js';
const TEXT = 'successfully cracked notion';

function runJSON(args) {
    const r = spawnSync(AGENT, args, { encoding: 'utf8', timeout: 15000 });
    try { return JSON.parse(r.stdout); } catch { return null; }
}
function shell(cmd) { spawnSync('sh', ['-c', cmd], { encoding: 'utf8' }); }
function press(keys) {
    console.log(`  ⌨️  ${keys}`);
    return runJSON(['--headed', 'press', keys]);
}

console.log('1. Activating Notion...');
shell(`osascript -e 'tell application "Notion" to activate'`);
shell('sleep 2');

console.log('2. Cmd+K → search "Docs"...');
press('cmd+k');
shell('sleep 1');

// Paste "Docs" into search
runJSON(['clipboard-set', 'Docs']);
press('cmd+v');
shell('sleep 1.5');

// Navigate to first result
console.log('3. Enter → navigate to Docs...');
press('return');
shell('sleep 2');

// Verify we're on the right page
const listResult = runJSON(['list-windows', '--app', 'Notion']);
const win = (listResult?.data || []).find(w => w.visible);
console.log(`   Window title: "${win?.title}"`);

// Jump to end of page content
console.log('4. Jumping to end of page...');
press('cmd+End');
shell('sleep 0.5');

// Create new block
console.log('5. Creating new block...');
press('return');
shell('sleep 0.3');

// Paste text
console.log('6. Pasting text...');
runJSON(['clipboard-set', TEXT]);
press('cmd+v');
shell('sleep 0.5');

// Confirm
press('return');

console.log(`\n✅ "${TEXT}" added to Docs page.`);
