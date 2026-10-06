#!/bin/sh
# Redraws the logo's rasters from assets/logo/videocode.svg, which is the source:
#
#   assets/logo/videocode.png                     the mark alone
#   logo.png                                      the mark alone at 150 px — what the README's example scene shows
#   assets/logo/icon.png                          the mark on a night disc — the window icon off macOS
#   Video-Code.app/Contents/Resources/icon.icns   the mark on a full night square: macOS masks a
#                                                 square to its own shape, and puts a disc on a grey plate
#
# macOS only: the SVG is drawn by AppKit, the .icns packed by iconutil.
set -e
cd "$(dirname "$0")/.."
tmp=$(mktemp -d)

cat > "$tmp/render.swift" <<'SWIFT'
import AppKit
// render.swift <mark.svg> <out.png> <plain|disc|square>
let args = CommandLine.arguments
let mark = NSImage(contentsOfFile: args[1])!
let size = 1024
let night = NSColor(deviceRed: 0.0862745, green: 0.0941176, blue: 0.145098, alpha: 1)
let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: size, pixelsHigh: size, bitsPerSample: 8, samplesPerPixel: 4,
                           hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
let full = NSRect(x: 0, y: 0, width: size, height: size)
var side = CGFloat(size)
switch args[3] {
case "disc":
    night.setFill()
    NSBezierPath(ovalIn: full.insetBy(dx: 100, dy: 100)).fill()
    side = 528
case "square":
    night.setFill()
    full.fill()
    side = 669
default: break
}
mark.draw(in: NSRect(x: (CGFloat(size) - side) / 2, y: (CGFloat(size) - side) / 2, width: side, height: side))
NSGraphicsContext.current = nil
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: args[2]))
SWIFT

swift "$tmp/render.swift" assets/logo/videocode.svg assets/logo/videocode.png plain
sips -z 150 150 assets/logo/videocode.png --out logo.png > /dev/null
swift "$tmp/render.swift" assets/logo/videocode.svg assets/logo/icon.png disc
swift "$tmp/render.swift" assets/logo/videocode.svg "$tmp/square.png" square

mkdir "$tmp/icon.iconset"
for s in 16 32 128 256 512; do
    sips -z $s $s "$tmp/square.png" --out "$tmp/icon.iconset/icon_${s}x${s}.png" > /dev/null
    sips -z $((s * 2)) $((s * 2)) "$tmp/square.png" --out "$tmp/icon.iconset/icon_${s}x${s}@2x.png" > /dev/null
done
iconutil -c icns "$tmp/icon.iconset" -o Video-Code.app/Contents/Resources/icon.icns
