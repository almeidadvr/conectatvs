from pathlib import Path

main = Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
gradle = Path('app/build.gradle.kts')
s = main.read_text(encoding='utf-8')

start = s.find('    private fun resolveServer(raw: String): String? {')
end = s.find('    private suspend fun connectivityLoop()', start)
if start < 0 or end < 0:
    raise SystemExit('resolveServer/connectivityLoop não encontrados')

new_resolve = '''    private fun resolveServer(raw: String): String? {
        val cleaned = raw.removePrefix("http://").removePrefix("https://").trimEnd('/')
        val hasPort = Regex(Regex.escape(":" ) + "[0-9]+$").containsMatchIn(cleaned)
        val candidates = if (hasPort) listOf("http://$cleaned") else (8787..8810).map { "http://$cleaned:$it" }
        for (candidate in candidates) {
            try {
                val state = getJson("$candidate/api/state")
                if (state.has("settings") && state.has("tvs") && state.has("media")) return candidate
            } catch (_: Exception) { }
        }
        return null
    }

'''
s = s[:start] + new_resolve + s[end:]

start = s.find('    private suspend fun connectivityLoop() {')
end = s.find('    private fun getTimedConfig(', start)
if start < 0 or end < 0:
    raise SystemExit('connectivityLoop/getTimedConfig não encontrados')

new_loop = '''    private suspend fun connectivityLoop() {
        while (scope.isActive) {
            if (serverUrl.isBlank()) return
            try {
                val wallStart = System.currentTimeMillis()
                val monoStart = SystemClock.elapsedRealtime()
                val state = withContext(Dispatchers.IO) { getJson("$serverUrl/api/state") }
                val monoEnd = SystemClock.elapsedRealtime()
                val rtt = (monoEnd - monoStart).coerceAtLeast(0L)
                val localMidpoint = wallStart + (rtt / 2L)
                val cfg = stateToLegacyConfig(state, localMidpoint)
                offlineBadge.visibility = View.GONE
                applyStateConfig(cfg, rtt)
                withContext(Dispatchers.IO) { runCatching { postHeartbeat() } }
            } catch (_: Exception) {
                if (activeItems.isNotEmpty()) {
                    offlineBadge.visibility = View.VISIBLE
                    if (!playbackStarted) syncPlayback(true)
                } else {
                    showPairingState("Sem conexão com o servidor. Tentando novamente...")
                }
            }
            delay(5000)
        }
    }

    private suspend fun applyStateConfig(cfg: JSONObject, rttMs: Long) {
        val midpoint = System.currentTimeMillis()
        val serverTime = cfg.optLong("serverTimeMs", midpoint)
        val offset = serverTime - midpoint
        applyConfig(cfg, offset, rttMs)
    }

    private fun stateToLegacyConfig(state: JSONObject, localNowMs: Long): JSONObject {
        val out = JSONObject()
        out.put("serverTimeMs", localNowMs)

        val tvs = state.optJSONArray("tvs") ?: JSONArray()
        var tv: JSONObject? = null
        for (i in 0 until tvs.length()) {
            val candidate = tvs.optJSONObject(i) ?: continue
            if (candidate.optString("pairingCode") == pairingCode) {
                tv = candidate
                break
            }
        }

        out.put("paired", tv != null)
        if (tv == null) return out

        val tvId = tv.optString("id")
        val tvGroups = mutableSetOf<String>()
        val tvGroupArr = tv.optJSONArray("groupIds") ?: JSONArray()
        for (i in 0 until tvGroupArr.length()) tvGroups += tvGroupArr.optString(i)

        val playlists = state.optJSONArray("playlists") ?: JSONArray()
        var playlistId = tv.optString("currentPlaylistId")
        if (playlistId.isBlank()) playlistId = tv.optString("playlistId")
        var selected: JSONObject? = null

        if (playlistId.isNotBlank()) {
            for (i in 0 until playlists.length()) {
                val p = playlists.optJSONObject(i) ?: continue
                if (p.optString("id") == playlistId) { selected = p; break }
            }
        }

        if (selected == null) {
            for (i in 0 until playlists.length()) {
                val p = playlists.optJSONObject(i) ?: continue
                val active = p.optBoolean("active", true) || p.optBoolean("manualActive", false) || p.optBoolean("scheduleActive", false)
                if (!active) continue
                var matches = false
                val tvIds = p.optJSONArray("tvIds") ?: JSONArray()
                for (j in 0 until tvIds.length()) if (tvIds.optString(j) == tvId) matches = true
                val groupIds = p.optJSONArray("groupIds") ?: JSONArray()
                for (j in 0 until groupIds.length()) if (groupIds.optString(j) in tvGroups) matches = true
                if (matches) { selected = p; break }
            }
        }

        if (selected == null) return out

        val mediaArr = state.optJSONArray("media") ?: JSONArray()
        val mediaById = mutableMapOf<String, JSONObject>()
        for (i in 0 until mediaArr.length()) {
            val m = mediaArr.optJSONObject(i) ?: continue
            mediaById[m.optString("id")] = m
        }

        val legacyItems = JSONArray()
        val sourceItems = selected.optJSONArray("items") ?: JSONArray()
        for (i in 0 until sourceItems.length()) {
            val pi = sourceItems.optJSONObject(i) ?: continue
            val mediaId = pi.optString("mediaId")
            val m = mediaById[mediaId] ?: continue
            var mediaUrl = m.optString("url")
            if (mediaUrl.startsWith("/")) mediaUrl = serverUrl + mediaUrl
            val item = JSONObject()
                .put("id", mediaId)
                .put("name", m.optString("name", mediaId))
                .put("kind", m.optString("kind"))
                .put("url", mediaUrl)
                .put("durationSeconds", pi.optInt("durationSeconds", 10).coerceAtLeast(1))
            legacyItems.put(item)
        }

        val legacyPlaylist = JSONObject()
            .put("id", selected.optString("id"))
            .put("name", selected.optString("name"))
            .put("updatedAt", selected.optString("updatedAt", selected.optString("id") + ":" + sourceItems.toString().hashCode()))
            .put("items", legacyItems)

        out.put("playlist", legacyPlaylist)
        out.put("syncAnchorMs", if (syncAnchorMs > 0L) syncAnchorMs else localNowMs)
        return out
    }

'''
s = s[:start] + new_loop + s[end:]

if 'private suspend fun applyConfig(cfg: JSONObject, measuredOffsetMs: Long, measuredRttMs: Long)' not in s:
    s = s.replace(
        'private suspend fun applyConfig(cfg: JSONObject, measuredOffsetMs: Long)',
        'private suspend fun applyConfig(cfg: JSONObject, measuredOffsetMs: Long, measuredRttMs: Long)'
    )

# Mantém heartbeat e proof das versões anteriores. A API /api/state substitui apenas a leitura de configuração.
main.write_text(s, encoding='utf-8')

g = gradle.read_text(encoding='utf-8')
g = g.replace('versionCode = 21', 'versionCode = 23')
g = g.replace('versionName = "0.9.1"', 'versionName = "0.9.3"')
gradle.write_text(g, encoding='utf-8')

print('Patch 0.9.3 aplicado: /api/state com heartbeat e telemetria preservados.')
