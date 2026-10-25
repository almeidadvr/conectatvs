from pathlib import Path

p = Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
s = p.read_text(encoding='utf-8')

# Conexão mais robusta: feedback imediato, timeout curto e teste explícito da porta.
old_connect = '''    private fun saveAndConnect() {
        val raw = serverInput.text.toString().trim()
        if (raw.isBlank()) { statusText.text = "Informe o IP do computador."; return }
        scope.launch {
            saveServerButton.isEnabled = false
            statusText.text = "Procurando o Conecta Mídia neste computador..."
            val found = withContext(Dispatchers.IO) { resolveServer(raw) }
            saveServerButton.isEnabled = true
            if (found == null) { statusText.text = "Não encontrei o servidor. Confira o IP e se o console está aberto no Windows."; return@launch }
            serverUrl = found
            prefs.edit().putString("server_url", found).apply()
            serverInput.visibility = View.GONE
            saveServerButton.visibility = View.GONE
            settingsButton.visibility = View.VISIBLE
            statusText.text = "Servidor encontrado. Aguardando pareamento..."
            launch { connectivityLoop() }
        }
    }

    private fun resolveServer(raw: String): String? {
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

new_connect = '''    private fun saveAndConnect() {
        val raw = serverInput.text.toString().trim()
        if (raw.isBlank()) {
            statusText.visibility = View.VISIBLE
            statusText.text = "Informe o IP do computador."
            return
        }
        scope.launch {
            saveServerButton.isEnabled = false
            val oldText = saveServerButton.text
            saveServerButton.text = "CONECTANDO..."
            statusText.visibility = View.VISIBLE
            statusText.text = "Testando conexão com o Conecta Mídia..."

            val result = withContext(Dispatchers.IO) {
                runCatching { withTimeout(12_000L) { resolveServer(raw) } }
            }

            saveServerButton.isEnabled = true
            saveServerButton.text = oldText

            val found = result.getOrNull()
            if (found == null) {
                val detail = result.exceptionOrNull()?.message?.takeIf { it.isNotBlank() }
                statusText.text = if (detail != null)
                    "Não consegui conectar. $detail"
                else
                    "Não encontrei o servidor. Confira IP, porta, Wi-Fi e Firewall do Windows."
                return@launch
            }

            serverUrl = found
            prefs.edit().putString("server_url", found).apply()
            serverInput.visibility = View.GONE
            saveServerButton.visibility = View.GONE
            settingsButton.visibility = View.VISIBLE
            statusText.text = "Servidor encontrado em ${found.removePrefix("http://")}. Verificando pareamento..."
            launch { connectivityLoop() }
        }
    }

    private fun resolveServer(raw: String): String? {
        val cleaned = raw.removePrefix("http://").removePrefix("https://").trim().trimEnd('/')
        if (cleaned.isBlank()) return null
        val hasPort = Regex(":\\d+$").containsMatchIn(cleaned)
        val candidates = if (hasPort) listOf("http://$cleaned") else (8787..8797).map { "http://$cleaned:$it" }
        var firstHealthy: String? = null

        for (candidate in candidates) {
            try {
                // Primeiro confirma que existe um Conecta Mídia nessa porta.
                val healthReq = Request.Builder().url("$candidate/api/health").build()
                val healthy = client.newCall(healthReq).execute().use { it.isSuccessful }
                if (!healthy) continue
                if (firstHealthy == null) firstHealthy = candidate

                // Em seguida prefere a instância que já reconhece este dispositivo.
                val cfg = getJson("$candidate/api/player/config?pairingCode=$pairingCode")
                if (cfg.optBoolean("paired")) return candidate
            } catch (_: Exception) { }
        }
        return firstHealthy
    }'''

if old_connect not in s:
    raise SystemExit('Bloco de conexão original não encontrado')
s = s.replace(old_connect, new_connect)

s = s.replace(
'''    private var imageJob: Job? = null
    private var syncJob: Job? = null
    private var playlistVersion = ""''',
'''    private var imageJob: Job? = null
    private var syncJob: Job? = null
    private var transitionJob: Job? = null
    private var playlistVersion = ""''')

s = s.replace(
'''    private var syncAnchorMs = 0L
    private var serverClockOffsetMs = 0L''',
'''    private var syncAnchorMs = 0L
    private var serverClockOffsetMs = 0L
    private var playlistTransition = "cut"''')

s = s.replace(
'''        val playlist = cfg.optJSONObject("playlist")
        if (playlist == null) { showPairingState("Dispositivo pareado. Aguardando uma playlist..."); return }

        syncAnchorMs = cfg.optLong("syncAnchorMs", System.currentTimeMillis() + serverClockOffsetMs)''',
'''        val playlist = cfg.optJSONObject("playlist")
        if (playlist == null) { showPairingState("Dispositivo pareado. Aguardando uma playlist..."); return }

        playlistTransition = when (playlist.optString("transition", "cut").lowercase()) {
            "fade" -> "fade"
            "black" -> "black"
            else -> "cut"
        }
        syncAnchorMs = cfg.optLong("syncAnchorMs", System.currentTimeMillis() + serverClockOffsetMs)''')

old = '''    private fun playItem(index: Int, offsetMs: Long) {
        if (activeItems.isEmpty()) return
        playbackStarted = true
        currentIndex = index
        statusPanel.visibility = View.GONE
        settingsButton.visibility = View.GONE
        imageJob?.cancel()
        player.stop()
        val item = activeItems[index]
        val file = File(item.localPath)
        if (!file.exists()) { scope.launch { delay(500); syncPlayback(true) }; return }

        if (item.kind == "video") {
            imageView.visibility = View.GONE
            playerView.visibility = View.VISIBLE
            player.setMediaItem(MediaItem.fromUri(Uri.fromFile(file)))
            player.prepare()
            player.seekTo(offsetMs.coerceIn(0L, (item.durationMs - 200L).coerceAtLeast(0L)))
            player.playWhenReady = true
        } else {
            playerView.visibility = View.GONE
            imageView.visibility = View.VISIBLE
            imageView.setImageBitmap(BitmapFactory.decodeFile(file.absolutePath))
            imageJob = scope.launch {
                delay((item.durationMs - offsetMs).coerceAtLeast(100L))
                syncPlayback(true)
            }
        }
    }'''

new = '''    private fun playItem(index: Int, offsetMs: Long) {
        if (activeItems.isEmpty()) return

        val singleVideoLoop = activeItems.size == 1 && activeItems[0].kind == "video"
        if (singleVideoLoop && currentIndex == 0 && playbackStarted && player.playbackState != Player.STATE_IDLE) {
            player.repeatMode = Player.REPEAT_MODE_ONE
            val target = offsetMs.coerceIn(0L, (activeItems[0].durationMs - 200L).coerceAtLeast(0L))
            if (abs(player.currentPosition - target) > 650L) player.seekTo(target)
            return
        }

        val changingItem = playbackStarted && currentIndex >= 0 && currentIndex != index
        transitionJob?.cancel()
        transitionJob = when {
            !changingItem || playlistTransition == "cut" -> scope.launch { playItemNow(index, offsetMs, false) }
            playlistTransition == "fade" -> scope.launch {
                val currentView = if (playerView.visibility == View.VISIBLE) playerView else imageView
                currentView.animate().alpha(0f).setDuration(220).withEndAction {
                    scope.launch { playItemNow(index, offsetMs, true) }
                }.start()
            }
            else -> scope.launch {
                playerView.alpha = 0f
                imageView.alpha = 0f
                delay(180)
                playItemNow(index, offsetMs, false)
            }
        }
    }

    private fun playItemNow(index: Int, offsetMs: Long, fadeIn: Boolean) {
        if (activeItems.isEmpty()) return
        playbackStarted = true
        currentIndex = index
        statusPanel.visibility = View.GONE
        settingsButton.visibility = View.GONE
        imageJob?.cancel()
        player.stop()
        val item = activeItems[index]
        val file = File(item.localPath)
        if (!file.exists()) { scope.launch { delay(500); syncPlayback(true) }; return }

        if (item.kind == "video") {
            imageView.visibility = View.GONE
            imageView.alpha = 1f
            playerView.visibility = View.VISIBLE
            playerView.alpha = if (fadeIn) 0f else 1f
            player.repeatMode = if (activeItems.size == 1) Player.REPEAT_MODE_ONE else Player.REPEAT_MODE_OFF
            player.setMediaItem(MediaItem.fromUri(Uri.fromFile(file)))
            player.prepare()
            player.seekTo(offsetMs.coerceIn(0L, (item.durationMs - 200L).coerceAtLeast(0L)))
            player.playWhenReady = true
            if (fadeIn) playerView.animate().alpha(1f).setDuration(220).start()
        } else {
            player.repeatMode = Player.REPEAT_MODE_OFF
            playerView.visibility = View.GONE
            playerView.alpha = 1f
            imageView.visibility = View.VISIBLE
            imageView.alpha = if (fadeIn) 0f else 1f
            imageView.setImageBitmap(BitmapFactory.decodeFile(file.absolutePath))
            if (fadeIn) imageView.animate().alpha(1f).setDuration(220).start()
            imageJob = scope.launch {
                delay((item.durationMs - offsetMs).coerceAtLeast(100L))
                syncPlayback(true)
            }
        }
    }'''

if old not in s:
    raise SystemExit('playItem original não encontrado')
s = s.replace(old, new)

s = s.replace(
'''            val playlist = JSONObject(raw)
            val arr = playlist.optJSONArray("items") ?: return@runCatching''',
'''            val playlist = JSONObject(raw)
            playlistTransition = when (playlist.optString("transition", "cut").lowercase()) {
                "fade" -> "fade"
                "black" -> "black"
                else -> "cut"
            }
            val arr = playlist.optJSONArray("items") ?: return@runCatching''')

s = s.replace(
'''    override fun onDestroy() { super.onDestroy(); imageJob?.cancel(); syncJob?.cancel(); scope.cancel(); player.release() }''',
'''    override fun onDestroy() { super.onDestroy(); imageJob?.cancel(); syncJob?.cancel(); transitionJob?.cancel(); scope.cancel(); player.release() }''')

p.write_text(s, encoding='utf-8')
print('Patch 0.5.3 aplicado')
