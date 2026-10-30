from pathlib import Path

main = Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
gradle = Path('app/build.gradle.kts')
s = main.read_text(encoding='utf-8')

# add dedicated legacy player API base
needle = '    private var serverUrl = ""\n'
if needle not in s:
    raise SystemExit('serverUrl não encontrado')
s = s.replace(needle, needle + '    private var playerApiUrl = ""\n', 1)

# helper to discover legacy player API on old ports using same host as state server
marker = '    private suspend fun connectivityLoop() {'
helper = r'''    private fun discoverPlayerApi(): String? {
        val host = runCatching { Uri.parse(serverUrl).host }.getOrNull() ?: return null
        for (port in 8787..8797) {
            val candidate = "http://$host:$port"
            try {
                val req = Request.Builder().url("$candidate/api/player/config?pairingCode=$pairingCode").build()
                client.newCall(req).execute().use { response ->
                    if (response.isSuccessful) return candidate
                }
            } catch (_: Exception) { }
        }
        return null
    }

'''
if marker not in s:
    raise SystemExit('connectivityLoop não encontrado')
s = s.replace(marker, helper + marker, 1)

# ensure discovery before heartbeat each loop
old = '                applyStateConfig(cfg, rtt)\n                withContext(Dispatchers.IO) { runCatching { postHeartbeat() } }'
new = '                applyStateConfig(cfg, rtt)\n                if (playerApiUrl.isBlank()) playerApiUrl = withContext(Dispatchers.IO) { discoverPlayerApi() ?: "" }\n                withContext(Dispatchers.IO) { runCatching { postHeartbeat() } }'
if old not in s:
    raise SystemExit('ponto de heartbeat no loop não encontrado')
s = s.replace(old, new, 1)

# route heartbeat/proof through legacy API base when found
s = s.replace('.url("$serverUrl/api/player/heartbeat")', '.url("${if (playerApiUrl.isNotBlank()) playerApiUrl else serverUrl}/api/player/heartbeat")')
s = s.replace('.url("$serverUrl/api/player/proof")', '.url("${if (playerApiUrl.isNotBlank()) playerApiUrl else serverUrl}/api/player/proof")')

main.write_text(s, encoding='utf-8')

g = gradle.read_text(encoding='utf-8')
g = g.replace('versionCode = 24', 'versionCode = 25')
g = g.replace('versionName = "0.9.4"', 'versionName = "0.9.5"')
gradle.write_text(g, encoding='utf-8')

print('Patch 0.9.5 aplicado: /api/state separado da API legada de heartbeat/proof (8787..8797).')
