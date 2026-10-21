import Vision
import Foundation
let dir = CommandLine.arguments[1]
let files = try! FileManager.default.contentsOfDirectory(atPath: dir).filter{$0.hasSuffix(".jpg")}.sorted()
for f in files {
    let url = URL(fileURLWithPath: dir + "/" + f)
    let req = VNDetectFaceRectanglesRequest()
    let h = VNImageRequestHandler(url: url)
    try? h.perform([req])
    let faces = (req.results ?? []).map { r -> String in
        let b = r.boundingBox
        return String(format: "%.4f,%.4f,%.4f,%.3f", b.midX, b.width, b.midY, r.confidence)
    }
    print(f, faces.joined(separator: " "))
}
