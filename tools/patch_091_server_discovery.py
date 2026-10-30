from pathlib import Path

main = Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
gradle = Path('app/build.gradle.kts')

s = main.read_text(encoding='utf-8')

old = '''    private fun resolveServer(raw: String): String? {
        val cleaned = raw.removePrefix("http://").removePrefix("https://").trimEnd('/')
        val hasPort = Regex(":\\d+$").containsMatchIn(cleaned)
        val candidates = if (hasPort) listOf("http://$cleaned") else (8787..8797).map { "http://$cleaned:$it" }
        var firstHealthy: String? = null
        for (candidate in candidates) {
            try {
                val cfg = getJson("$candidate/api/player/config?pairingCode=$pairingCode")
                if (cfg.optBoolean("paired")) return candidate
                val req = Request.Builder().url("$candidate/api/health").build()
                client.newCall(req).execute().use { if (it.isSuccessful && firstHealthy == null) firstHealthy = candidate }
            } catch (_: Exception) { }
        }
        return firstHealthy
    }'''

new = '''    private fun resolveServer(raw: String): String? {
        val cleaned = raw.removePrefix("http://").removePrefix("https://").trimEnd('/')
        val hasPort = Regex(":\\d+$").containsMatchIn(cleaned)
        // O Console pode mudar de porta entre versões. Procura uma faixa mais ampla,
        // incluindo 8799 usada pelo Console 0.9.2.
        val candidates = if (hasPort) listOf("http://$cleaned") else (8787..8810).map { "http://$cleaned:$it" }
        for (candidate in candidates) {
            try {
                // A rota de configuração do próprio Player é a fonte de verdade.
                // Mesmo ainda não pareado, um JSON válido confirma que encontramos o Console.
                getJson("$candidate/api/player/config?pairingCode=$pairingCode")
                return candidate
            } catch (_: Exception) { }
        }
        return null
    }'''

if old not in s:
    raise SystemExit('resolveServer esperado não encontrado')

s = s.replace(old, new, 1)
main.write_text(s, encoding='utf-8')

g = gradle.read_text(encoding='utf-8')
g = g.replace('versionCode = 20', 'versionCode = 21')
g = g.replace('versionName = "0.9.0"', 'versionName = "0.9.1"')
gradle.write_text(g, encoding='utf-8')

print('Patch 0.9.1 aplicado: descoberta 8787-8810 e validação pela rota do Player.')
