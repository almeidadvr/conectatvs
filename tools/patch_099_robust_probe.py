from pathlib import Path

main = Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
gradle = Path('app/build.gradle.kts')
s = main.read_text(encoding='utf-8')

# Campo de diagnóstico de descoberta
needle = '    private var serverUrl = ""\n'
if needle in s and 'private var discoveryDiagnostic' not in s:
    s = s.replace(needle, needle + '    private var discoveryDiagnostic = ""\n', 1)

start = s.find('    private fun resolveServer(raw: String): String? {')
end = s.find('    private suspend fun connectivityLoop()', start)
if start < 0 or end < 0:
    raise SystemExit('resolveServer/connectivityLoop não encontrados')

new_resolve = r'''    private fun resolveServer(raw: String): String? {
        val cleaned = raw.removePrefix("http://").removePrefix("https://").trimEnd('/')
        val hasPort = Regex(":\\d+$").containsMatchIn(cleaned)
        val candidates = if (hasPort) listOf("http://$cleaned") else (8787..8810).map { "http://$cleaned:$it" }
        val notes = mutableListOf<String>()

        for (candidate in candidates) {
            val port = Uri.parse(candidate).port
            try {
                // 1) Rota oficial do Player. Não exige JSON durante a descoberta.
                val configReq = Request.Builder()
                    .url("$candidate/api/player/config?pairingCode=$pairingCode")
                    .build()
                client.newCall(configReq).execute().use { response ->
                    val body = response.body?.string().orEmpty()
                    notes += "$port:C${response.code}"
                    if (response.isSuccessful) {
                        // Um 2xx nesta rota é suficiente para identificar o núcleo do Console.
                        discoveryDiagnostic = notes.joinToString(" ")
                        return candidate
                    }
                    // Alguns builds respondem 404 para código ainda não cadastrado.
                    // Se a resposta menciona pareamento/player, a rota existe e o núcleo foi encontrado.
                    val lower = body.lowercase()
                    if (response.code == 404 && ("pair" in lower || "player" in lower || "codigo" in lower || "código" in lower)) {
                        discoveryDiagnostic = notes.joinToString(" ")
                        return candidate
                    }
                }
            } catch (_: Exception) {
                notes += "$port:CX"
            }

            try {
                // 2) Health é aceito como confirmação do mesmo núcleo.
                val healthReq = Request.Builder().url("$candidate/api/health").build()
                client.newCall(healthReq).execute().use { response ->
                    notes += "$port:H${response.code}"
                    if (response.isSuccessful) {
                        discoveryDiagnostic = notes.joinToString(" ")
                        return candidate
                    }
                }
            } catch (_: Exception) {
                notes += "$port:HX"
            }
        }

        discoveryDiagnostic = notes.takeLast(12).joinToString(" ")
        return null
    }

'''
s = s[:start] + new_resolve + s[end:]

# Melhor mensagem quando a descoberta falhar
old = 'if (found == null) { statusText.text = "Não encontrei o servidor. Confira o IP e se o console está aberto no Windows."; return@launch }'
new = 'if (found == null) { statusText.text = "Não encontrei o servidor. Diagnóstico: $discoveryDiagnostic"; return@launch }'
if old in s:
    s = s.replace(old, new, 1)

# Quando o núcleo foi encontrado mas config ainda não retorna JSON válido (pré-pareamento),
# mostrar estado de pareamento em vez de acusar servidor ausente.
old_catch = '''            } catch (_: Exception) {
                if (activeItems.isNotEmpty()) {
                    offlineBadge.visibility = View.VISIBLE
                    if (!playbackStarted) syncPlayback(true)
                } else {
                    showPairingState("Sem conexão com o servidor. Tentando novamente...")
                }
            }'''
new_catch = '''            } catch (_: Exception) {
                if (activeItems.isNotEmpty()) {
                    offlineBadge.visibility = View.VISIBLE
                    if (!playbackStarted) syncPlayback(true)
                } else {
                    showPairingState("Servidor encontrado em ${serverUrl}. Se ainda não estiver cadastrado, adicione o código ${pairingCode} no Console. Tentando novamente...")
                }
            }'''
if old_catch not in s:
    raise SystemExit('catch do connectivityLoop não encontrado')
s = s.replace(old_catch, new_catch, 1)

main.write_text(s, encoding='utf-8')

g = gradle.read_text(encoding='utf-8')
g = g.replace('versionCode = 28', 'versionCode = 29')
g = g.replace('versionName = "0.9.8"', 'versionName = "0.9.9"')
gradle.write_text(g, encoding='utf-8')

print('Patch 0.9.9 aplicado: probe HTTP robusto + diagnóstico, sem alterar heartbeat/proof/kiosk.')
