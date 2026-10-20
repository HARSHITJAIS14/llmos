const { spawnSync } = require('child_process');
const path = require('path');

const STEALTH_CLICK_BIN = path.join(__dirname, 'stealth_click');

/**
 * Perform a "stealth click" at the specified (x, y) coordinates.
 * This moves the mouse to the coordinates, clicks, and instantly restores
 * the original mouse position to avoid interrupting the user's workflow.
 * 
 * @param {number} x The x coordinate
 * @param {number} y The y coordinate
 * @returns {boolean} True if the click executed successfully
 */
function stealthClick(x, y) {
    const result = spawnSync(STEALTH_CLICK_BIN, [String(x), String(y)], {
        encoding: 'utf8',
        timeout: 2000
    });

    if (result.error || result.status !== 0) {
        console.error(`Stealth click failed at (${x}, ${y}):`, result.error?.message || result.stderr || result.stdout);
        return false;
    }
    return true;
}

module.exports = {
    stealthClick
};
