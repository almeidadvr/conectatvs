from pathlib import Path

main = Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
gradle = Path('app/build.gradle.kts')
s = main.read_text(encoding='utf-8')

start = s.find('    private fun resolveServer(raw: String): String? {')
end = s.find('    private suspend fun connectivityLoop()', start)
if start < 0 or end < 0:
    raise SystemExit('resolveServer/connectivityLoop não encontrados')

new = r'''    private fun resolveServer(raw: String): String? {
        val cleaned = raw.removePrefix("http://").removePrefix("https://").trimEnd('/')
        val hasPort = Regex(":\\d+$").containsMatchIn(cleaned)
        // Mantém a API legada do Player, mas amplia a descoberta para incluir 8799
        // e aceita o Console mesmo quando este dispositivo ainda não foi pareado.
        val candidates = if (hasPort) listOf("http://$cleaned") else (8787..8810).map { "http://$cleaned:$it" }
        for (candidate in candidates) {
            try {
                val cfg = getJson("$candidate/api/player/config?pairingCode=$pairingCode")
                // O Console válido responde JSON da rota do Player mesmo antes do pareamento.
                // Não exigir paired=true evita confundir "não pareado" com "servidor inexistente".
                if (cfg.has("paired") || cfg.has("serverTimeMs") || cfg.has("playlist")) return candidate
            } catch (_: Exception) { }
        }
        return null
    }

'''
s = s[:start] + new + s[end:]
main.write_text(s, encoding='utf-8')

g = gradle.read_text(encoding='utf-8')
g = g.replace('versionCode = 27', 'versionCode = 28')
g = g.replace('versionName = "0.9.7"', 'versionName = "0.9.8"')
gradle.write_text(g, encoding='utf-8')

print('Patch 0.9.8 aplicado: descoberta 8787-8810 e pré-pareamento sem alterar heartbeat/proof/auto-start.')
