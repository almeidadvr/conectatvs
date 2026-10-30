from pathlib import Path

main = Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
gradle = Path('app/build.gradle.kts')
s = main.read_text(encoding='utf-8')

start = s.find('    private fun postHeartbeat() {')
end = s.find('    private fun reportProof(', start)
if start < 0 or end < 0:
    raise SystemExit('postHeartbeat/reportProof não encontrados')

new_hb = r'''    private fun postHeartbeat() {
        if (serverUrl.isBlank()) return
        val currentMedia = activeItems.getOrNull(currentIndex)?.id ?: ""
        val (storageTotal, storageFree) = storageStatsMb()
        val dm = resources.displayMetrics
        val uptimeSeconds = ((SystemClock.elapsedRealtime() - appStartedElapsedMs).coerceAtLeast(0L)) / 1000L

        // O Console 0.9.2.x usa decoder estrito no heartbeat. Enviar somente
        // os campos aceitos pelo struct do backend, sem Wi-Fi/sync extras.
        val payload = JSONObject()
            .put("pairingCode", pairingCode)
            .put("appVersion", BuildConfig.VERSION_NAME)
            .put("manufacturer", Build.MANUFACTURER ?: "")
            .put("model", Build.MODEL ?: "")
            .put("deviceCode", Build.DEVICE ?: "")
            .put("product", Build.PRODUCT ?: "")
            .put("androidVersion", Build.VERSION.RELEASE ?: "")
            .put("sdkInt", Build.VERSION.SDK_INT)
            .put("buildDisplay", Build.DISPLAY ?: "")
            .put("storageTotalMB", storageTotal)
            .put("storageFreeMB", storageFree)
            .put("screenWidth", dm.widthPixels)
            .put("screenHeight", dm.heightPixels)
            .put("densityDpi", dm.densityDpi)
            .put("localIp", localIpAddress())
            .put("uptimeSeconds", uptimeSeconds)
            .put("appStartedAt", appStartedAtMs)
            .put("downloadedItems", downloadedItemsCount)
            .put("totalItems", totalItemsCount)
            .put("currentMediaId", currentMedia)
            .put("currentPlaylistId", currentPlaylistId)
            .put("playbackError", lastPlaybackError)
            .toString()

        val contentType = "application/json".toMediaType()
        val req = Request.Builder()
            .url("$serverUrl/api/player/heartbeat")
            .post(payload.toRequestBody(contentType))
            .build()

        client.newCall(req).execute().use { response ->
            if (response.isSuccessful) return
        }

        // Fallback de presença: se algum firmware/Console rejeitar a telemetria,
        // ainda atualiza lastSeen/Online usando o formato mínimo histórico.
        val minimal = JSONObject().put("pairingCode", pairingCode).toString()
        val fallbackReq = Request.Builder()
            .url("$serverUrl/api/player/heartbeat")
            .post(minimal.toRequestBody(contentType))
            .build()
        client.newCall(fallbackReq).execute().use { response ->
            if (!response.isSuccessful) error("Heartbeat HTTP ${response.code}")
        }
    }

'''
s = s[:start] + new_hb + s[end:]
main.write_text(s, encoding='utf-8')

g = gradle.read_text(encoding='utf-8')
g = g.replace('versionCode = 23', 'versionCode = 24')
g = g.replace('versionName = "0.9.3"', 'versionName = "0.9.4"')
gradle.write_text(g, encoding='utf-8')

print('Patch 0.9.4 aplicado: heartbeat compatível com Console 0.9.2.x + fallback mínimo.')
