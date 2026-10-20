import Cocoa
import Vision

let targetText = "Library"
let imagePath = "/tmp/screen.png"

guard let image = NSImage(contentsOfFile: imagePath),
      let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
    print("Failed to load screenshot")
    exit(1)
}

let request = VNRecognizeTextRequest { (request, error) in
    guard let observations = request.results as? [VNRecognizedTextObservation] else { return }
    
    var found = false
    for obs in observations {
        guard let topCandidate = obs.topCandidates(1).first else { continue }
        if topCandidate.string.contains(targetText) {
            let box = obs.boundingBox
            let width = CGFloat(cgImage.width)
            let height = CGFloat(cgImage.height)
            
            let x = box.midX * width
            let y = (1.0 - box.midY) * height
            
            print("\(Int(x)),\(Int(y))")
            found = true
            break
        }
    }
    
    if !found {
        print("NOT_FOUND")
    }
}
request.recognitionLevel = .accurate

let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
try? handler.perform([request])
