import AppKit
// usage: caption <text> <out.png> <fontSize> <centerY> <fontFile|-> <weight> <strokeWidth%> [rtl|ltr]
let a = CommandLine.arguments
let text = a[1], out = a[2]
let size = CGFloat(Double(a[3])!), cy = CGFloat(Double(a[4])!)
let weight = Double(a[6])!, stroke = Double(a[7])!
let W = 1080, H = 1920
var font: NSFont
if a[5] == "-" { font = NSFont.systemFont(ofSize: size, weight: .medium) } else {
    let descs = CTFontManagerCreateFontDescriptorsFromURL(URL(fileURLWithPath: a[5]) as CFURL) as! [CTFontDescriptor]
    var f = CTFontCreateWithFontDescriptor(descs[0], size, nil)
    let wght: UInt32 = 0x77676874
    if let axes = CTFontCopyVariationAxes(f) as? [[String: Any]], !axes.isEmpty {
        let d = CTFontDescriptorCreateCopyWithVariation(descs[0], NSNumber(value: wght), CGFloat(weight))
        f = CTFontCreateWithFontDescriptor(d, size, nil)
    }
    font = f as NSFont
}
let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: W, pixelsHigh: H, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
let para = NSMutableParagraphStyle(); para.alignment = .center; para.baseWritingDirection = (a.count > 8 && a[8] == "ltr") ? .leftToRight : .rightToLeft
let shadow = NSShadow(); shadow.shadowColor = NSColor.black.withAlphaComponent(0.5); shadow.shadowBlurRadius = 8; shadow.shadowOffset = NSSize(width: 0, height: -3)
let base: [NSAttributedString.Key: Any] = [.font: font, .paragraphStyle: para]
var strokeA = base; strokeA[.strokeColor] = NSColor.black; strokeA[.strokeWidth] = stroke; strokeA[.shadow] = shadow
var fillA = base; fillA[.foregroundColor] = NSColor.white
let margin: CGFloat = 70, bw = CGFloat(W) - 2*margin
let s1 = NSAttributedString(string: text, attributes: strokeA)
let bh = s1.boundingRect(with: NSSize(width: bw, height: 2000), options: [.usesLineFragmentOrigin]).height
let rect = NSRect(x: margin, y: CGFloat(H) - cy - bh/2, width: bw, height: bh)
if stroke > 0 { s1.draw(with: rect, options: [.usesLineFragmentOrigin]) }
var fillS = fillA; if stroke <= 0 { fillS[.shadow] = shadow }
NSAttributedString(string: text, attributes: fillS).draw(with: rect, options: [.usesLineFragmentOrigin])
NSGraphicsContext.current = nil
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: out))
