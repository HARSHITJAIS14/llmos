# Rich text injection: HTML → RTF → NSPasteboard (any native editor)

<!-- provenance: ATree_tool day 5, MS Word + Pages + Notes, macOS 15 -->

Typing or pasting raw Markdown into desktop editors fails — text engines
treat `#`/`**` as literal characters. The universal pipeline:

1. Compose the payload as HTML (`<h1>`, `<b>`, `<ul><li>`).
2. Compile to native RTF: `textutil -convert rtf content.html`
3. Load the RTF pasteboard type directly:
   `osascript -e 'set the clipboard to (read (POSIX file "content.rtf") as "RTF ")'`
4. Focus the target app (see catalyst.md focus rules), then
   `agent-desktop press cmd+v`.

100% fidelity headings/weights/lists in Word, Pages, Notes, Mail, TextEdit —
no brittle formatting-menu navigation.
