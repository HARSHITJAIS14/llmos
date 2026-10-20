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

// 2. Teleport to target
CGWarpMouseCursorPosition(targetLoc)
usleep(10000) // 10ms wait to ensure warp registers before click

// 3. Perform click
let source = CGEventSource(stateID: .hidSystemState)
let clickDown = CGEvent(mouseEventSource: source, mouseType: .leftMouseDown, mouseCursorPosition: targetLoc, mouseButton: .left)
let clickUp = CGEvent(mouseEventSource: source, mouseType: .leftMouseUp, mouseCursorPosition: targetLoc, mouseButton: .left)

clickDown?.post(tap: .cghidEventTap)
clickUp?.post(tap: .cghidEventTap)
usleep(10000) // 10ms wait to ensure click registers

// 4. Restore original mouse location
CGWarpMouseCursorPosition(originalLoc)
usleep(10000) // Wait briefly to ensure the window server processes the moveBack event
