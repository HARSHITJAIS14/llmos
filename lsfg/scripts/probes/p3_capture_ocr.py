"""CG window list (with ghost strips), in-memory capture, Vision OCR fast/accurate/crop.
Nothing is written to disk. Result on 2026-09-30 (Safari full screen 2560x1440): list 0.5 ms;
a 2560x33 layer-0 strip listed BEFORE the real window; capture 10.5 ms; OCR fast 14 ms,
accurate 117 ms, top-20% crop 6.9 ms.
Usage: python p3_capture_ocr.py AppName"""
import sys

import Quartz
import Vision

from _common import pid_of, timed

name = sys.argv[1] if len(sys.argv) > 1 else "Safari"
pid = pid_of(name)
if not pid:
    sys.exit(f"{name} is not running")
opts = Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements
lmed, _, wins = timed(lambda: Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID))
mine = [w for w in wins if int(w.get(Quartz.kCGWindowOwnerPID, -1)) == pid
        and int(w.get(Quartz.kCGWindowLayer, 0)) == 0]
sizes = [(int(w["kCGWindowBounds"]["Width"]), int(w["kCGWindowBounds"]["Height"])) for w in mine]
print(f"CGWindowListCopyWindowInfo {lmed:.1f} ms; {name} layer-0 on-screen windows (front to back): {sizes}")
real = [w for w in mine if w["kCGWindowBounds"]["Height"] > 40 and w["kCGWindowBounds"]["Width"] > 200]
if not real:
    sys.exit("no real on-screen window")
wid = int(real[0][Quartz.kCGWindowNumber])


def cap():
    return Quartz.CGWindowListCreateImage(
        Quartz.CGRectNull, Quartz.kCGWindowListOptionIncludingWindow, wid,
        Quartz.kCGWindowImageBoundsIgnoreFraming | Quartz.kCGWindowImageNominalResolution)


cmed, cmx, img = timed(cap)
W, H = Quartz.CGImageGetWidth(img), Quartz.CGImageGetHeight(img)


def ocr(level, image):
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(level)  # 1 = fast, 0 = accurate
    req.setUsesLanguageCorrection_(False)
    Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(image, None).performRequests_error_([req], None)
    return len(req.results() or [])


fmed, _, nf = timed(lambda: ocr(1, img))
amed, _, na = timed(lambda: ocr(0, img), n=2)
crop = Quartz.CGImageCreateWithImageInRect(img, Quartz.CGRectMake(0, 0, W, int(H * 0.2)))
rmed, _, nr = timed(lambda: ocr(1, crop))
print(f"capture {cmed:.1f} ms (max {cmx:.1f}) {W}x{H} | OCR fast {fmed:.0f} ms ({nf} texts) | "
      f"accurate {amed:.0f} ms ({na}) | top-20% crop fast {rmed:.1f} ms ({nr})")
