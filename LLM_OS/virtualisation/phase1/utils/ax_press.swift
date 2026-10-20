import Cocoa
import ApplicationServices

func findElement(app: NSRunningApplication, role: String, nameOrId: String) -> AXUIElement? {
    let appElement = AXUIElementCreateApplication(app.processIdentifier)
    return searchTree(element: appElement, targetRole: role, targetString: nameOrId)
}

func searchTree(element: AXUIElement, targetRole: String, targetString: String) -> AXUIElement? {
    var value: CFTypeRef?
    
    // Check role
    var matchesRole = false
    if AXUIElementCopyAttributeValue(element, kAXRoleAttribute as CFString, &value) == .success {
        if let currentRole = value as? String {
            let roleStr = currentRole.lowercased().replacingOccurrences(of: "ax", with: "")
            let targetStr = targetRole.lowercased().replacingOccurrences(of: "ax", with: "")
            if roleStr == targetStr {
                matchesRole = true
            }
        }
    }
    
    // Check name, description, or identifier
    var matchesString = false
    
    if AXUIElementCopyAttributeValue(element, kAXTitleAttribute as CFString, &value) == .success {
        if let currentName = value as? String, currentName.lowercased() == targetString.lowercased() {
            matchesString = true
        }
    }
    
    if !matchesString && AXUIElementCopyAttributeValue(element, kAXDescriptionAttribute as CFString, &value) == .success {
        if let currentDesc = value as? String, currentDesc.lowercased() == targetString.lowercased() {
            matchesString = true
        }
    }
    
    if !matchesString && AXUIElementCopyAttributeValue(element, kAXIdentifierAttribute as CFString, &value) == .success {
        if let currentId = value as? String, currentId.lowercased() == targetString.lowercased() {
            matchesString = true
        }
    }
    
    // Some elements might have value instead of title
    if !matchesString && AXUIElementCopyAttributeValue(element, kAXValueAttribute as CFString, &value) == .success {
        if let currentVal = value as? String, currentVal.lowercased() == targetString.lowercased() {
            matchesString = true
        }
    }
    
    if matchesRole && matchesString {
        return element
    }
    
    // Recurse children
    var childrenRef: CFTypeRef?
    if AXUIElementCopyAttributeValue(element, kAXChildrenAttribute as CFString, &childrenRef) == .success {
        if let children = childrenRef as? [AXUIElement] {
            for child in children {
                if let found = searchTree(element: child, targetRole: targetRole, targetString: targetString) {
                    return found
                }
            }
        }
    }
    return nil
}

func main() {
    let args = CommandLine.arguments
    if args.count < 4 {
        print("Usage: ax_press <app_name> <role> <name_or_identifier>")
        exit(1)
    }
    
    let appName = args[1]
    let targetRole = args[2]
    let targetString = args[3]
    
    let workspace = NSWorkspace.shared
    guard let app = workspace.runningApplications.first(where: { $0.localizedName?.lowercased() == appName.lowercased() }) else {
        print("Error: Application '\(appName)' not found or not running.")
        exit(1)
    }
    
    guard let element = findElement(app: app, role: targetRole, nameOrId: targetString) else {
        print("Error: Element with role '\(targetRole)' and name/identifier '\(targetString)' not found.")
        exit(1)
    }
    
    let result = AXUIElementPerformAction(element, kAXPressAction as CFString)
    if result == .success {
        print("Successfully pressed element '\(targetString)' in '\(appName)'.")
    } else {
        print("Failed to press element. Error code: \(result.rawValue)")
        exit(1)
    }
}

main()
