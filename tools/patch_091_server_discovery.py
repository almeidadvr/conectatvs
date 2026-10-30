from pathlib import Path

main = Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
gradle = Path('app/build.gradle.kts')

s = main.read_text(encoding='utf-8')

start = s.find('    private fun resolveServer(raw: String): String? {')
end = s.find('    private suspend fun connectivityLoop()', start)
if start < 0 or end < 0:
    raise SystemExit('resolveServer/connectivityLoop não encontrados')

new = '''    private fun resolveServer(raw: String): String? {
        val cleaned = raw.removePrefix("http://").removePrefix("https://").trimEnd('/')
        val hasPort = Regex(""":\\d+$""").containsMatchIn(cleaned)
        // O Console pode mudar de porta entre versões. Procura uma faixa mais ampla,
        // incluindo 8799 usada pelo Console 0.9.2.
        val candidates = if (hasPort) listOf("http://$cleaned") else (8787..8810).map { "http://$cleaned:$it" }
        for (candidate in candidates) {
            try {
                // Um JSON válido da rota do Player confirma o Console,
                // mesmo quando o dispositivo ainda não está pareado.
                getJson("$candidate/api/player/config?pairingCode=$pairingCode")
                return candidate
            } catch (_: Exception) { }
        }
        return null
    }

'''

s = s[:start] + new + s[end:]
main.write_text(s, encoding='utf-8')

g = gradle.read_text(encoding='utf-8')
g = g.replace('versionCode = 20', 'versionCode = 21')
g = g.replace('versionName = "0.9.0"', 'versionName = "0.9.1"')
gradle.write_text(g, encoding='utf-8')

print('Patch 0.9.1 aplicado: descoberta 8787-8810 e validação pela rota do Player.')
