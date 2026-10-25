package com.conectasolucoes.conectasign

import android.graphics.BitmapFactory
import android.media.MediaMetadataRetriever
import android.net.Uri
import android.os.Bundle
import android.view.KeyEvent
import android.view.View
import android.view.WindowManager
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import kotlinx.coroutines.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.TimeUnit
import kotlin.math.abs
import kotlin.random.Random

class MainActivity : AppCompatActivity() {
    private lateinit var player: ExoPlayer
    private lateinit var playerView: PlayerView
    private lateinit var imageView: ImageView
    private lateinit var statusPanel: LinearLayout
    private lateinit var codeText: TextView
    private lateinit var statusText: TextView
    private lateinit var serverInput: EditText
    private lateinit var saveServerButton: Button
    private lateinit var settingsButton: Button
    private lateinit var offlineBadge: TextView

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private val client = OkHttpClient.Builder().connectTimeout(4, TimeUnit.SECONDS).readTimeout(20, TimeUnit.SECONDS).build()
    private val prefs by lazy { getSharedPreferences("conecta_sign", MODE_PRIVATE) }

    private var pairingCode = ""
    private var serverUrl = ""
    private var activeItems = mutableListOf<PlaylistItem>()
    private var currentIndex = -1
    private var imageJob: Job? = null
    private var playlistVersion = ""
    private var playbackStarted = false
    private var syncAnchorMs = 0L
    private var serverClockOffsetMs = 0L

    data class PlaylistItem(
        val id: String,
        val name: String,
        val kind: String,
        val durationSeconds: Int,
        val url: String,
        val localPath: String,
        val durationMs: Long
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        enterImmersive()

        playerView = findViewById(R.id.playerView)
        imageView = findViewById(R.id.imageView)
        statusPanel = findViewById(R.id.statusPanel)
        codeText = findViewById(R.id.codeText)
        statusText = findViewById(R.id.statusText)
        serverInput = findViewById(R.id.serverInput)
        saveServerButton = findViewById(R.id.saveServerButton)
        settingsButton = findViewById(R.id.settingsButton)
        offlineBadge = findViewById(R.id.offlineBadge)

        player = ExoPlayer.Builder(this).build()
        playerView.player = player
        player.repeatMode = Player.REPEAT_MODE_OFF
        player.addListener(object : Player.Listener {
            override fun onPlaybackStateChanged(playbackState: Int) {
                if (playbackState == Player.STATE_ENDED && activeItems.isNotEmpty()) syncPlayback(true)
            }
        })

        pairingCode = prefs.getString("pairing_code", null)
            ?: Random.nextInt(100000, 999999).toString().also { prefs.edit().putString("pairing_code", it).apply() }
        codeText.text = "${pairingCode.take(3)} ${pairingCode.takeLast(3)}"

        serverUrl = prefs.getString("server_url", "") ?: ""
        serverInput.setText(serverUrl.removePrefix("http://"))
        saveServerButton.setOnClickListener { saveAndConnect() }
        settingsButton.setOnClickListener { showServerSettings() }

        loadCachedPlaylist()
        if (serverUrl.isBlank()) {
            showServerSettings()
        } else {
            if (activeItems.isNotEmpty()) {
                offlineBadge.visibility = View.VISIBLE
                syncPlayback(true)
            } else {
                showPairingState("Conectando ao servidor...")
            }
            scope.launch { connectivityLoop() }
        }
    }

    private fun enterImmersive() {
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_FULLSCREEN or View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or
            View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION or View.SYSTEM_UI_FLAG_LAYOUT_STABLE
    }

    private fun saveAndConnect() {
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
    }

    private suspend fun connectivityLoop() {
        while (scope.isActive) {
            if (serverUrl.isBlank()) return
            try {
                val cfg = withContext(Dispatchers.IO) { getJson("$serverUrl/api/player/config?pairingCode=$pairingCode") }
                offlineBadge.visibility = View.GONE
                applyConfig(cfg)
                if (cfg.optBoolean("paired")) withContext(Dispatchers.IO) { postHeartbeat() }
            } catch (_: Exception) {
                if (activeItems.isNotEmpty()) {
                    offlineBadge.visibility = View.VISIBLE
                    if (!playbackStarted) syncPlayback(true)
                } else {
                    showPairingState("Sem conexão com o servidor. Tentando novamente...")
                }
            }
            delay(15_000)
        }
    }

    private suspend fun applyConfig(cfg: JSONObject) {
        if (!cfg.optBoolean("paired")) { showPairingState("Cadastre este código no painel do Conecta Mídia."); return }
        val serverTime = cfg.optLong("serverTimeMs", System.currentTimeMillis())
        serverClockOffsetMs = serverTime - System.currentTimeMillis()
        val playlist = cfg.optJSONObject("playlist")
        if (playlist == null) { showPairingState("Dispositivo pareado. Aguardando uma playlist..."); return }
        syncAnchorMs = cfg.optLong("syncAnchorMs", System.currentTimeMillis() + serverClockOffsetMs)
        val newVersion = playlist.optString("updatedAt")

        if (newVersion != playlistVersion || activeItems.isEmpty()) {
            val parsed = withContext(Dispatchers.IO) { cachePlaylist(playlist) }
            if (parsed.isEmpty()) { showPairingState("Playlist sem arquivos compatíveis."); return }
            activeItems = parsed.toMutableList()
            playlistVersion = newVersion
            currentIndex = -1
            saveCachedPlaylist(playlist)
            saveSyncState()
            syncPlayback(true)
        } else {
            saveSyncState()
            syncPlayback(false)
        }
    }

    private fun cachePlaylist(playlist: JSONObject): List<PlaylistItem> {
        val arr = playlist.optJSONArray("items") ?: JSONArray()
        val out = mutableListOf<PlaylistItem>()
        val mediaDir = File(filesDir, "media").apply { mkdirs() }
        val validNames = mutableSetOf<String>()
        for (i in 0 until arr.length()) {
            val o = arr.optJSONObject(i) ?: continue
            val id = o.optString("id")
            val name = o.optString("name", id)
            val kind = o.optString("kind")
            val url = o.optString("url")
            val duration = o.optInt("durationSeconds", 10).coerceAtLeast(1)
            if (id.isBlank() || url.isBlank() || kind !in setOf("video", "image")) continue
            val ext = Uri.parse(url).lastPathSegment?.substringAfterLast('.', "")?.takeIf { it.length <= 5 }
            val filename = if (ext.isNullOrBlank()) id else "$id.$ext"
            val file = File(mediaDir, filename)
            validNames += filename
            if (!file.exists() || file.length() == 0L) downloadTo(url, file)
            if (file.exists() && file.length() > 0L) {
                val durationMs = if (kind == "video") videoDurationMs(file).coerceAtLeast(1000L) else duration * 1000L
                out += PlaylistItem(id, name, kind, duration, url, file.absolutePath, durationMs)
            }
        }
        mediaDir.listFiles()?.forEach { if (it.name !in validNames) runCatching { it.delete() } }
        return out
    }

    private fun videoDurationMs(file: File): Long = runCatching {
        val r = MediaMetadataRetriever(); r.setDataSource(file.absolutePath)
        val ms = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLongOrNull() ?: 0L
        r.release(); ms
    }.getOrDefault(0L)

    private fun downloadTo(url: String, target: File) {
        val tmp = File(target.parentFile, target.name + ".part")
        try {
            client.newCall(Request.Builder().url(url).build()).execute().use { response ->
                if (!response.isSuccessful) error("HTTP ${response.code}")
                val body = response.body ?: error("Arquivo vazio")
                FileOutputStream(tmp).use { out -> body.byteStream().copyTo(out) }
            }
            if (target.exists()) target.delete()
            if (!tmp.renameTo(target)) error("Falha ao salvar mídia")
        } catch (e: Exception) { tmp.delete(); throw e }
    }

    private fun synchronizedNowMs(): Long = System.currentTimeMillis() + serverClockOffsetMs

    private fun timelinePosition(): Pair<Int, Long> {
        val total = activeItems.sumOf { it.durationMs }.coerceAtLeast(1L)
        val elapsed = ((synchronizedNowMs() - syncAnchorMs) % total + total) % total
        var cursor = 0L
        activeItems.forEachIndexed { index, item ->
            if (elapsed < cursor + item.durationMs) return index to (elapsed - cursor)
            cursor += item.durationMs
        }
        return 0 to 0L
    }

    private fun syncPlayback(force: Boolean) {
        if (activeItems.isEmpty()) return
        val (targetIndex, targetOffset) = timelinePosition()
        val target = activeItems[targetIndex]
        val sameItem = currentIndex == targetIndex && playbackStarted
        if (!force && sameItem) {
            if (target.kind == "video" && abs(player.currentPosition - targetOffset) > 1500L) player.seekTo(targetOffset)
            return
        }
        playItem(targetIndex, targetOffset)
    }

    private fun playItem(index: Int, offsetMs: Long) {
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
            player.seekTo(offsetMs.coerceIn(0L, (item.durationMs - 250L).coerceAtLeast(0L)))
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
    }

    private fun showPairingState(message: String) {
        playbackStarted = false
        player.stop(); imageJob?.cancel()
        playerView.visibility = View.GONE; imageView.visibility = View.GONE; statusPanel.visibility = View.VISIBLE
        codeText.visibility = View.VISIBLE; findViewById<TextView>(R.id.codeLabel).visibility = View.VISIBLE
        statusText.text = message
        serverInput.visibility = View.GONE; saveServerButton.visibility = View.GONE
        settingsButton.visibility = if (serverUrl.isBlank()) View.GONE else View.VISIBLE
    }

    private fun showServerSettings() {
        playbackStarted = false
        player.pause(); imageJob?.cancel()
        playerView.visibility = View.GONE; imageView.visibility = View.GONE; statusPanel.visibility = View.VISIBLE
        serverInput.visibility = View.VISIBLE; saveServerButton.visibility = View.VISIBLE; settingsButton.visibility = View.GONE
        statusText.text = "Informe o IP do computador que está executando o Conecta Mídia."
        serverInput.requestFocus()
    }

    private fun saveCachedPlaylist(playlist: JSONObject) {
        prefs.edit().putString("cached_playlist", playlist.toString()).putString("playlist_version", playlist.optString("updatedAt")).apply()
    }

    private fun saveSyncState() {
        prefs.edit().putLong("sync_anchor_ms", syncAnchorMs).putLong("server_clock_offset_ms", serverClockOffsetMs).apply()
    }

    private fun loadCachedPlaylist() {
        syncAnchorMs = prefs.getLong("sync_anchor_ms", 0L)
        serverClockOffsetMs = prefs.getLong("server_clock_offset_ms", 0L)
        val raw = prefs.getString("cached_playlist", null) ?: return
        playlistVersion = prefs.getString("playlist_version", "") ?: ""
        runCatching {
            val playlist = JSONObject(raw)
            val arr = playlist.optJSONArray("items") ?: return@runCatching
            val mediaDir = File(filesDir, "media")
            val list = mutableListOf<PlaylistItem>()
            for (i in 0 until arr.length()) {
                val o = arr.optJSONObject(i) ?: continue
                val id = o.optString("id"); val kind = o.optString("kind"); val url = o.optString("url")
                val duration = o.optInt("durationSeconds", 10).coerceAtLeast(1)
                val ext = Uri.parse(url).lastPathSegment?.substringAfterLast('.', "")?.takeIf { it.length <= 5 }
                val filename = if (ext.isNullOrBlank()) id else "$id.$ext"
                val file = File(mediaDir, filename)
                if (file.exists() && file.length() > 0L) {
                    val durationMs = if (kind == "video") videoDurationMs(file).coerceAtLeast(1000L) else duration * 1000L
                    list += PlaylistItem(id, o.optString("name", id), kind, duration, url, file.absolutePath, durationMs)
                }
            }
            if (list.isNotEmpty()) {
                activeItems = list
                if (syncAnchorMs <= 0L) syncAnchorMs = System.currentTimeMillis()
            }
        }
    }

    private fun getJson(url: String): JSONObject {
        val req = Request.Builder().url(url).build()
        client.newCall(req).execute().use { response ->
            val text = response.body?.string() ?: "{}"
            if (!response.isSuccessful && response.code != 404) error("HTTP ${response.code}")
            return JSONObject(text)
        }
    }

    private fun postHeartbeat() {
        val payload = JSONObject().put("pairingCode", pairingCode).toString()
        val req = Request.Builder().url("$serverUrl/api/player/heartbeat").post(payload.toRequestBody("application/json".toMediaType())).build()
        client.newCall(req).execute().close()
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_BACK && event?.isLongPress == true) { showServerSettings(); return true }
        return super.onKeyDown(keyCode, event)
    }

    override fun onResume() { super.onResume(); enterImmersive() }
    override fun onDestroy() { super.onDestroy(); imageJob?.cancel(); scope.cancel(); player.release() }
}
