const { execSync } = require('child_process');
const fs = require('fs');

const MAX_REQUESTS = 15; // Limit DFS to prevent infinite hangs
let requestCount = 0;

function runCmd(cmd) {
    try {
        return execSync(cmd, { stdio: 'pipe', encoding: 'utf8' });
    } catch (e) {
        console.error("Command failed:", cmd);
        console.error(e.stderr ? e.stderr : e.message);
        return null;
    }
}

function findNodeByNativeId(node, value) {
    if (node.native_id && node.native_id.value === value) return node;
    if (node.children) {
        for (const child of node.children) {
            const found = findNodeByNativeId(child, value);
            if (found) return found;
        }
    }
    return null;
}

function dfs(node, snapshotId) {
    if (requestCount >= MAX_REQUESTS) return;

    // If a node says it has children, but they aren't loaded in the JSON, it's truncated.
    if (node.children_count > 0 && (!node.children || node.children.length === 0)) {
        console.log(`[Req ${requestCount+1}/${MAX_REQUESTS}] Drilling down into ${node.ref_id} (Role: ${node.role})...`);
        requestCount++;
        const drillOut = runCmd(`bin/agent-desktop.js snapshot --root ${node.ref_id} --snapshot ${snapshotId} -i --include-bounds`);
        
        if (drillOut) {
            try {
                const drillData = JSON.parse(drillOut);
                if (drillData.ok && drillData.data && drillData.data.tree) {
                    // The drilled down tree is the node itself, so we take its children
                    node.children = drillData.data.tree.children || [];
                } else {
                    console.error(`Drill down failed for ${node.ref_id}:`, drillData.error);
                }
            } catch (err) {
                console.error("Failed to parse drill down output:", err.message);
            }
        }
    }

    // Continue DFS into newly populated or existing children
    if (node.children) {
        for (const child of node.children) {
            dfs(child, snapshotId);
        }
    }
}

function main() {
    console.log("Activating Notion...");
    runCmd(`osascript -e 'tell application "Notion" to activate'`);
    runCmd('sleep 1');

    console.log("Finding Notion window...");
    const listOutput = runCmd('bin/agent-desktop.js list-windows --app Notion');
    if (!listOutput) return;
    const windowsData = JSON.parse(listOutput);
    let target = windowsData.data.find(w => w.is_focused) || windowsData.data.find(w => w.visible) || windowsData.data[0];

    if (!target) {
        console.log("No Notion window found.");
        return;
    }

    console.log(`Taking initial snapshot of ${target.id}...`);
    const snapOut = runCmd(`bin/agent-desktop.js snapshot --window-id ${target.id} -i --include-bounds`);
    if (!snapOut) return;
    const snapData = JSON.parse(snapOut);
    
    if (!snapData.ok) {
        console.log("Initial snapshot failed:", JSON.stringify(snapData.error));
        return;
    }

    const snapshotId = snapData.data.snapshot_id;
    const root = snapData.data.tree;

    // We specifically want to drill down into the 'notion-app' webarea/group to save time
    const notionAppNode = findNodeByNativeId(root, 'notion-app');
    
    if (notionAppNode) {
        console.log(`\nFound 'notion-app' node at ${notionAppNode.ref_id}. Starting DFS...`);
        dfs(notionAppNode, snapshotId);
    } else {
        console.log("\nCould not find 'notion-app' node, starting DFS from root...");
        dfs(root, snapshotId);
    }

    const outPath = '/Users/harshit/Desktop/YC/LLM_OS/notion_dfs_tree.json';
    fs.writeFileSync(outPath, JSON.stringify(snapData, null, 4));
    console.log(`\nDFS complete. Result saved to ${outPath}`);
}

main();
