// Draws the 1024x1024 app icon. CoreGraphics only: AppKit crashes when run as a script.
//   swift icon.swift letter <out.png> <letter> <#background> <#foreground>
//   swift icon.swift logo   <out.png> <in.png|jpg|heic> <#background> <pad|fill>
// The result never has an alpha channel (Xcode rejects icons that do) and has
// square corners (iOS applies its own mask).
import CoreGraphics
import CoreText
import Foundation
import ImageIO

func fail(_ msg: String) -> Never {
    FileHandle.standardError.write(Data((msg + "\n").utf8))
    exit(1)
}

func color(_ hex: String) -> CGColor {
    var h = hex
    if h.hasPrefix("#") { h.removeFirst() }
    let v = UInt32(h, radix: 16) ?? 0xFFFFFF
    return CGColor(srgbRed: CGFloat((v >> 16) & 255) / 255, green: CGFloat((v >> 8) & 255) / 255,
                   blue: CGFloat(v & 255) / 255, alpha: 1)
}

let a = CommandLine.arguments
guard a.count == 6, ["letter", "logo"].contains(a[1]) else {
    fail("usage: icon.swift letter <out.png> <letter> <#bg> <#fg> | logo <out.png> <in> <#bg> <pad|fill>")
}
let size = 1024
let ctx = CGContext(data: nil, width: size, height: size, bitsPerComponent: 8, bytesPerRow: 0,
                    space: CGColorSpace(name: CGColorSpace.sRGB)!,
                    bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
ctx.interpolationQuality = .high
ctx.setFillColor(color(a[4]))
ctx.fill(CGRect(x: 0, y: 0, width: size, height: size))

if a[1] == "letter" {
    let font = CTFontCreateWithName("HelveticaNeue-Medium" as CFString, 620, nil)
    let text = NSAttributedString(string: String(a[3].prefix(1)).uppercased(), attributes: [
        NSAttributedString.Key(kCTFontAttributeName as String): font,
        NSAttributedString.Key(kCTForegroundColorAttributeName as String): color(a[5]),
    ])
    let line = CTLineCreateWithAttributedString(text)
    let box = CTLineGetBoundsWithOptions(line, .useGlyphPathBounds)
    ctx.textPosition = CGPoint(x: (CGFloat(size) - box.width) / 2 - box.minX,
                               y: (CGFloat(size) - box.height) / 2 - box.minY)
    CTLineDraw(line, ctx)
} else {
    guard let src = CGImageSourceCreateWithURL(URL(fileURLWithPath: a[3]) as CFURL, nil),
          let logo = CGImageSourceCreateImageAtIndex(src, 0, nil) else { fail("cannot read the logo image") }
    let w = CGFloat(logo.width), h = CGFloat(logo.height)
    // fill: cover the whole square (a logo that is already an icon). pad: fit it
    // inside 68% of the square, centered, on the background color.
    let area = a[5] == "fill" ? CGFloat(size) : CGFloat(size) * 0.68
    let scale = a[5] == "fill" ? max(area / w, area / h) : min(area / w, area / h)
    let dw = w * scale, dh = h * scale
    ctx.draw(logo, in: CGRect(x: (CGFloat(size) - dw) / 2, y: (CGFloat(size) - dh) / 2, width: dw, height: dh))
}

guard let image = ctx.makeImage(),
      let dest = CGImageDestinationCreateWithURL(URL(fileURLWithPath: a[2]) as CFURL, "public.png" as CFString, 1, nil)
else { fail("cannot write the icon") }
CGImageDestinationAddImage(dest, image, nil)
exit(CGImageDestinationFinalize(dest) ? 0 : 1)
