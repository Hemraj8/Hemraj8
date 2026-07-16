import Foundation
import Vision
import CoreImage

// usage: swift cutout.swift <input> <output.png>
// Masks the foreground subject (person) onto a black background.
let inURL = URL(fileURLWithPath: CommandLine.arguments[1])
let outURL = URL(fileURLWithPath: CommandLine.arguments[2])

let handler = VNImageRequestHandler(url: inURL)
let request = VNGenerateForegroundInstanceMaskRequest()
try handler.perform([request])

guard let result = request.results?.first else {
    fputs("no subject found\n", stderr)
    exit(1)
}

let buffer = try result.generateMaskedImage(
    ofInstances: result.allInstances,
    from: handler,
    croppedToInstancesExtent: false
)

let ci = CIImage(cvPixelBuffer: buffer)
// composite over black so transparent background becomes true black
let black = CIImage(color: CIColor.black).cropped(to: ci.extent)
let composited = ci.composited(over: black)

let ctx = CIContext()
try ctx.writePNGRepresentation(
    of: composited,
    to: outURL,
    format: .RGBA8,
    colorSpace: CGColorSpace(name: CGColorSpace.sRGB)!
)
print("cutout written")
