import CoreGraphics
import Foundation

func postKey(code: CGKeyCode) {
    let down = CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: true)
    let up = CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: false)
    down?.post(tap: .cghidEventTap)
    up?.post(tap: .cghidEventTap)
    usleep(20000) // 20ms
}

// Click Apple Menu
let loc = CGPoint(x: 20, y: 10)
let clickDown = CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown, mouseCursorPosition: loc, mouseButton: .left)
let clickUp = CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp, mouseCursorPosition: loc, mouseButton: .left)
clickDown?.post(tap: .cghidEventTap)
usleep(100000)
clickUp?.post(tap: .cghidEventTap)

usleep(400000) // Wait for menu to open

// Type s, l, e, e, p
postKey(code: 1)  // s
postKey(code: 37) // l
postKey(code: 14) // e
postKey(code: 14) // e
postKey(code: 35) // p

usleep(300000) // Wait for selection
postKey(code: 36) // return
