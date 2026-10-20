const { execSync } = require('child_process');
const fs = require('fs');

try {
    console.log("Activating Notion...");
    execSync(`osascript -e 'tell application "Notion" to activate'`);
    execSync('sleep 2');

    console.log("Listing windows...");
    const listOutput = execSync('bin/agent-desktop.js list-windows --app Notion').toString();
    const data = JSON.parse(listOutput);
    
    // Find candidate window (focused or visible)
    let target = data.data.find(w => w.is_focused);
    if (!target) target = data.data.find(w => w.visible);
    if (!target && data.data.length > 0) target = data.data[0];

    if (!target) {
        console.error("No Notion windows found.");
        process.exit(1);
    }

    console.log(`Taking full snapshot of window: ${target.id} (${target.title})`);
    
    // Attempt full snapshot (without --compact)
    execSync(`bin/agent-desktop.js snapshot --window-id ${target.id} -i > /Users/harshit/Desktop/YC/LLM_OS/notion_snapshot_full.json`);
    console.log("Full snapshot saved.");

} catch (error) {
    console.error("Script failed:", error.message);
}
