from pathlib import Path

p = Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
s = p.read_text(encoding='utf-8')

old = '''        val url = playlist.optString("watermarkLogoUrl", "")\n        if (url.isBlank()) {'''
new = '''        val rawUrl = playlist.optString("watermarkLogoUrl", "")\n        val url = when {\n            rawUrl.startsWith("http://") || rawUrl.startsWith("https://") -> rawUrl\n            rawUrl.startsWith("/") && serverUrl.isNotBlank() -> serverUrl.trimEnd('/') + rawUrl\n            else -> rawUrl\n        }\n        if (url.isBlank()) {'''

if old not in s:
    raise SystemExit('Bloco watermarkLogoUrl não encontrado')
s = s.replace(old, new)

p.write_text(s, encoding='utf-8')
print('Suporte a logo específica relativa aplicado sem alterar conexão/sincronização')
