from pathlib import Path

p = Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
s = p.read_text(encoding='utf-8')

s = s.replace('import android.os.StatFs', 'import android.os.StatFs\nimport android.os.Build\nimport java.net.NetworkInterface')

s = s.replace(
'''    private var lastProofKey = ""\n    private var lastProofAt = 0L''',
'''    private var lastProofKey = ""\n    private var lastProofAt = 0L\n    private val appStartedAtMs = System.currentTimeMillis()\n    private val appStartedElapsedMs = SystemClock.elapsedRealtime()''')

old = '''    private fun storageFreeMb(): Long = runCatching {\n        StatFs(filesDir.absolutePath).availableBytes / (1024L * 1024L)\n    }.getOrDefault(0L)\n\n    private fun postHeartbeat() {\n        if (serverUrl.isBlank()) return\n        val currentMedia = activeItems.getOrNull(currentIndex)?.id ?: ""\n        val payload = JSONObject()\n            .put("pairingCode", pairingCode)\n            .put("appVersion", BuildConfig.VERSION_NAME)\n            .put("storageFreeMB", storageFreeMb())\n            .put("downloadedItems", downloadedItemsCount)\n            .put("totalItems", totalItemsCount)\n            .put("currentMediaId", currentMedia)\n            .put("currentPlaylistId", currentPlaylistId)\n            .toString()\n        val req = Request.Builder().url("$serverUrl/api/player/heartbeat").post(payload.toRequestBody("application/json".toMediaType())).build()\n        client.newCall(req).execute().close()\n    }'''

new = '''    private fun storageStatsMb(): Pair<Long, Long> = runCatching {\n        val stat = StatFs(filesDir.absolutePath)\n        Pair(stat.totalBytes / (1024L * 1024L), stat.availableBytes / (1024L * 1024L))\n    }.getOrDefault(Pair(0L, 0L))\n\n    private fun localIpAddress(): String = runCatching {\n        NetworkInterface.getNetworkInterfaces().toList()\n            .flatMap { it.inetAddresses.toList() }\n            .firstOrNull { !it.isLoopbackAddress && it.hostAddress?.contains(':') == false }\n            ?.hostAddress ?: ""\n    }.getOrDefault("")\n\n    private fun postHeartbeat() {\n        if (serverUrl.isBlank()) return\n        val currentMedia = activeItems.getOrNull(currentIndex)?.id ?: ""\n        val (storageTotal, storageFree) = storageStatsMb()\n        val dm = resources.displayMetrics\n        val uptimeSeconds = ((SystemClock.elapsedRealtime() - appStartedElapsedMs).coerceAtLeast(0L)) / 1000L\n        val payload = JSONObject()\n            .put("pairingCode", pairingCode)\n            .put("appVersion", BuildConfig.VERSION_NAME)\n            .put("manufacturer", Build.MANUFACTURER ?: "")\n            .put("model", Build.MODEL ?: "")\n            .put("deviceCode", Build.DEVICE ?: "")\n            .put("product", Build.PRODUCT ?: "")\n            .put("androidVersion", Build.VERSION.RELEASE ?: "")\n            .put("sdkInt", Build.VERSION.SDK_INT)\n            .put("buildDisplay", Build.DISPLAY ?: "")\n            .put("storageTotalMB", storageTotal)\n            .put("storageFreeMB", storageFree)\n            .put("screenWidth", dm.widthPixels)\n            .put("screenHeight", dm.heightPixels)\n            .put("densityDpi", dm.densityDpi)\n            .put("localIp", localIpAddress())\n            .put("uptimeSeconds", uptimeSeconds)\n            .put("appStartedAt", appStartedAtMs)\n            .put("downloadedItems", downloadedItemsCount)\n            .put("totalItems", totalItemsCount)\n            .put("currentMediaId", currentMedia)\n            .put("currentPlaylistId", currentPlaylistId)\n            .toString()\n        val req = Request.Builder().url("$serverUrl/api/player/heartbeat").post(payload.toRequestBody("application/json".toMediaType())).build()\n        client.newCall(req).execute().close()\n    }'''

if old not in s:
    raise SystemExit('Bloco de heartbeat 0.6.0 não encontrado')
s = s.replace(old, new)

p.write_text(s, encoding='utf-8')
print('Telemetria 0.6.3 aplicada sem alterar conexão/sincronização')
