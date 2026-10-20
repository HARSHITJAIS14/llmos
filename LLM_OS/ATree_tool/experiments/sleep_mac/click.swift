import CoreGraphics
import Foundation

let source = CGEventSource(stateID: .hidSystemState)
let loc = CGPoint(x: 20, y: 10)
let clickDown = CGEvent(mouseEventSource: source, mouseType: .leftMouseDown, mouseCursorPosition: loc, mouseButton: .left)
let clickUp = CGEvent(mouseEventSource: source, mouseType: .leftMouseUp, mouseCursorPosition: loc, mouseButton: .left)

clickDown?.post(tap: .cghidEventTap)
usleep(100000)
clickUp?.post(tap: .cghidEventTap)
