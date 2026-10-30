from pathlib import Path

path = Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
text = path.read_text(encoding='utf-8')
old = 'loadOfficialLogo(); requestNetworkPermissions()'
new = 'requestNetworkPermissions()'
if old not in text:
    raise SystemExit('Logo runtime hook not found; refusing to alter unknown source')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
print('Logo fix applied: XML drawable remains authoritative; layout size unchanged.')
