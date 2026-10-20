import CoreGraphics
import Foundation

// Check args
if CommandLine.arguments.count < 3 {
    print("Usage: stealth_click <x> <y>")
    exit(1)
}

guard let targetX = Double(CommandLine.arguments[1]),
      let targetY = Double(CommandLine.arguments[2]) else {
    print("Invalid coordinates")
    exit(1)
}

let targetLoc = CGPoint(x: targetX, y: targetY)

// 1. Get current mouse location
guard let currentEvent = CGEvent(source: nil) else {
    print("Could not get current mouse location")
    exit(1)
}
let originalLoc = currentEvent.location

// 2. Perform click at target
let source = CGEventSource(stateID: .hidSystemState)
let clickDown = CGEvent(mouseEventSource: source, mouseType: .leftMouseDown, mouseCursorPosition: targetLoc, mouseButton: .left)
let clickUp = CGEvent(mouseEventSource: source, mouseType: .leftMouseUp, mouseCursorPosition: targetLoc, mouseButton: .left)

// Move to target
let moveTarget = CGEvent(mouseEventSource: source, mouseType: .mouseMoved, mouseCursorPosition: targetLoc, mouseButton: .left)
moveTarget?.post(tap: .cghidEventTap)

// Perform click with zero delay as requested
clickDown?.post(tap: .cghidEventTap)
clickUp?.post(tap: .cghidEventTap)

// 3. Restore original mouse location immediately
let moveBack = CGEvent(mouseEventSource: source, mouseType: .mouseMoved, mouseCursorPosition: originalLoc, mouseButton: .left)
moveBack?.post(tap: .cghidEventTap)

// Wait briefly to ensure the window server processes the moveBack event before the process exits
usleep(50000)
