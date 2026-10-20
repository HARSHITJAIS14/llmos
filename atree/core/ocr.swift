// Local OCR via Vision.framework — rung 3 of the vision ladder.
// Usage: swift ocr.swift <image.png>   -> recognized text, one line per block.
// Free and offline; no model call. (Lineage: ATree_tool find_text.swift.)
import Foundation
import Vision
import AppKit

guard CommandLine.arguments.count > 1,
      let image = NSImage(contentsOfFile: CommandLine.arguments[1]),
      let cg = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    FileHandle.standardError.write("usage: swift ocr.swift <image.png>\n".data(using: .utf8)!)
    exit(1)
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false

do {
    try VNImageRequestHandler(cgImage: cg, options: [:]).perform([request])
    for obs in request.results ?? [] {
        if let top = obs.topCandidates(1).first {
            print(top.string)
        }
    }
} catch {
    FileHandle.standardError.write("ocr error: \(error)\n".data(using: .utf8)!)
    exit(1)
}
