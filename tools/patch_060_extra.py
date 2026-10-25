from pathlib import Path

p = Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
s = p.read_text(encoding='utf-8')

s = s.replace('import android.os.SystemClock', 'import android.os.SystemClock\nimport android.os.StatFs')

s = s.replace(
'''    private var playlistTransition = "cut"''',
'''    private var playlistTransition = "cut"\n    private var currentPlaylistId = ""\n    private var downloadedItemsCount = 0\n    private var totalItemsCount = 0\n    private var lastProofKey = ""\n    private var lastProofAt = 0L''')

s = s.replace(
'''        val playlist = cfg.optJSONObject("playlist")\n        if (playlist == null) { showPairingState("Dispositivo pareado. Aguardando uma playlist..."); return }\n\n        playlistTransition''',
'''        val playlist = cfg.optJSONObject("playlist")\n        if (playlist == null) { showPairingState("Dispositivo pareado. Aguardando uma playlist..."); return }\n\n        currentPlaylistId = playlist.optString("id")\n        playlistTransition''')

s = s.replace(
'''        val arr = playlist.optJSONArray("items") ?: JSONArray()\n        val out = mutableListOf<PlaylistItem>()''',
'''        val arr = playlist.optJSONArray("items") ?: JSONArray()\n        totalItemsCount = arr.length()\n        downloadedItemsCount = 0\n        val out = mutableListOf<PlaylistItem>()''')

s = s.replace(
'''            if (file.exists() && file.length() > 0L) {\n                val durationMs = if (kind == "video") videoDurationMs(file).coerceAtLeast(1000L) else duration * 1000L\n                out += PlaylistItem(id, name, kind, duration, url, file.absolutePath, durationMs)\n            }''',
'''            if (file.exists() && file.length() > 0L) {\n                val durationMs = if (kind == "video") videoDurationMs(file).coerceAtLeast(1000L) else duration * 1000L\n                out += PlaylistItem(id, name, kind, duration, url, file.absolutePath, durationMs)\n                downloadedItemsCount++\n                runCatching { postHeartbeat() }\n            }''')

s = s.replace(
'''        val item = activeItems[index]\n        val file = File(item.localPath)''',
'''        val item = activeItems[index]\n        reportProof(item)\n        val file = File(item.localPath)''')

s = s.replace(
'''            val playlist = JSONObject(raw)\n            playlistTransition''',
'''            val playlist = JSONObject(raw)\n            currentPlaylistId = playlist.optString("id")\n            playlistTransition''')

s = s.replace(
'''            if (list.isNotEmpty()) {\n                activeItems = list''',
'''            if (list.isNotEmpty()) {\n                activeItems = list\n                totalItemsCount = list.size\n                downloadedItemsCount = list.size''')

old = '''    private fun postHeartbeat() {\n        val payload = JSONObject().put("pairingCode", pairingCode).toString()\n        val req = Request.Builder().url("$serverUrl/api/player/heartbeat").post(payload.toRequestBody("application/json".toMediaType())).build()\n        client.newCall(req).execute().close()\n    }'''

new = '''    private fun storageFreeMb(): Long = runCatching {\n        StatFs(filesDir.absolutePath).availableBytes / (1024L * 1024L)\n    }.getOrDefault(0L)\n\n    private fun postHeartbeat() {\n        if (serverUrl.isBlank()) return\n        val currentMedia = activeItems.getOrNull(currentIndex)?.id ?: ""\n        val payload = JSONObject()\n            .put("pairingCode", pairingCode)\n            .put("appVersion", BuildConfig.VERSION_NAME)\n            .put("storageFreeMB", storageFreeMb())\n            .put("downloadedItems", downloadedItemsCount)\n            .put("totalItems", totalItemsCount)\n            .put("currentMediaId", currentMedia)\n            .put("currentPlaylistId", currentPlaylistId)\n            .toString()\n        val req = Request.Builder().url("$serverUrl/api/player/heartbeat").post(payload.toRequestBody("application/json".toMediaType())).build()\n        client.newCall(req).execute().close()\n    }\n\n    private fun reportProof(item: PlaylistItem) {\n        if (serverUrl.isBlank() || currentPlaylistId.isBlank()) return\n        val now = SystemClock.elapsedRealtime()\n        val key = "$currentPlaylistId:${item.id}"\n        if (key == lastProofKey && now - lastProofAt < 2000L) return\n        lastProofKey = key\n        lastProofAt = now\n        scope.launch(Dispatchers.IO) {\n            runCatching {\n                val payload = JSONObject()\n                    .put("pairingCode", pairingCode)\n                    .put("playlistID", currentPlaylistId)\n                    .put("mediaID", item.id)\n                    .toString()\n                val req = Request.Builder().url("$serverUrl/api/player/proof").post(payload.toRequestBody("application/json".toMediaType())).build()\n                client.newCall(req).execute().close()\n            }\n        }\n    }'''

if old not in s:
    raise SystemExit('postHeartbeat original não encontrado')
s = s.replace(old, new)

p.write_text(s, encoding='utf-8')
print('Extras 0.6.0 aplicados sem alterar conexão/sincronização')
