from pathlib import Path

p = Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
s = p.read_text(encoding='utf-8')

seen = set()
out = []
for line in s.splitlines():
    if line.startswith('import '):
        if line in seen:
            continue
        seen.add(line)
    out.append(line)

p.write_text('\n'.join(out) + '\n', encoding='utf-8')
print('Imports duplicados removidos após patch 0.9.0.')
