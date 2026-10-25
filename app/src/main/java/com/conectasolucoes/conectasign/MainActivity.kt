package com.conectasolucoes.conectasign

import android.graphics.BitmapFactory
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
    private val client = OkHttpClient.Builder()
        .connectTimeout(4, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .build()

    private val prefs by lazy { getSharedPreferences("conecta_sign", MODE_PRIVATE) }
    private var pairingCode = ""
    private var serverUrl = ""
    private var activeItems = mutableListOf<PlaylistItem>()
    private var currentIndex = 0
    private var imageJob: Job? = null
    private var playlistVersion = ""
    private var playbackStarted = false

    data class PlaylistItem(
        val id: String,
        val name: String,
        val kind: String,
        val durationSeconds: Int,
        val url: String,
        val localPath: String
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
                if (playbackState == Player.STATE_ENDED) nextItem()
            }
        })

        pairingCode = prefs.getString("pairing_code", null)
            ?: Random.nextInt(100000, 999999).toString().also {
                prefs.edit().putString("pairing_code", it).apply()
            }
        codeText.text = "${pairingCode.take(3)} ${pairingCode.takeLast(3)}"

        serverUrl = prefs.getString("server_url", "") ?: ""
        serverInput.setText(serverUrl.removePrefix("http://").substringBefore(":"))

        saveServerButton.setOnClickListener { saveAndConnect() }
        settingsButton.setOnClickListener { showServerSettings() }

        loadCachedPlaylist()
        if (serverUrl.isBlank()) {
            showServerSettings()
        } else {
            showPairingState("Conectando ao servidor...")
            scope.launch { connectivityLoop() }
        }
    }

    private fun enterImmersive() {
        window.decorView.systemUiVisibility = (
            View.SYSTEM_UI_FLAG_FULLSCREEN or
                View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
                View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or
                View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or
                View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION or
                View.SYSTEM_UI_FLAG_LAYOUT_STABLE
        )
    }

    private fun saveAndConnect() {
        val raw = serverInput.text.toString().trim()
        if (raw.isBlank()) {
            statusText.text = "Informe o IP do computador."
            return
        }
        scope.launch {
            saveServerButton.isEnabled = false
            statusText.text = "Procurando o Conecta Sign neste computador..."
            val found = withContext(Dispatchers.IO) { resolveServer(raw) }
            saveServerButton.isEnabled = true
            if (found == null) {
                statusText.text = "Não encontrei o servidor. Confira o IP e se o Conecta Sign está aberto no Windows."
                return@launch
            }
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
        for (candidate in candidates) {
            try {
                val req = Request.Builder().url("$candidate/api/health").build()
                client.newCall(req).execute().use { r -> if (r.isSuccessful) return candidate }
            } catch (_: Exception) { }
        }
        return null
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
                if (playbackStarted && activeItems.isNotEmpty()) {
                    offlineBadge.visibility = View.VISIBLE
                } else {
                    showPairingState("Sem conexão com o servidor. Tentando novamente...")
                }
            }
            delay(15_000)
        }
    }

    private suspend fun applyConfig(cfg: JSONObject) {
        if (!cfg.optBoolean("paired")) {
            showPairingState("Cadastre este código no painel do Conecta Sign.")
            return
        }
        val playlist = cfg.optJSONObject("playlist")
        if (playlist == null) {
            showPairingState("TV pareada. Aguardando uma playlist...")
            return
        }
        val newVersion = playlist.optString("updatedAt")
        if (newVersion == playlistVersion && activeItems.isNotEmpty()) {
            if (!playbackStarted) startPlayback()
            return
        }
        val parsed = withContext(Dispatchers.IO) { cachePlaylist(playlist) }
        if (parsed.isEmpty()) {
            showPairingState("Playlist sem arquivos compatíveis.")
            return
        }
        activeItems = parsed.toMutableList()
        playlistVersion = newVersion
        currentIndex = 0
        saveCachedPlaylist(playlist)
        startPlayback()
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
            if (file.exists() && file.length() > 0L) out += PlaylistItem(id, name, kind, duration, url, file.absolutePath)
        }
        mediaDir.listFiles()?.forEach { if (it.name !in validNames) runCatching { it.delete() } }
        return out
    }

    private fun downloadTo(url: String, target: File) {
        val tmp = File(target.parentFile, target.name + ".part")
        try {
            client.newCall(Request.Builder().url(url).build()).execute().use { response ->
                if (!response.isSuccessful) throw IllegalStateException("HTTP ${response.code}")
                val body = response.body ?: throw IllegalStateException("Arquivo vazio")
                FileOutputStream(tmp).use { out -> body.byteStream().copyTo(out) }
            }
            if (target.exists()) target.delete()
            tmp.renameTo(target)
        } catch (e: Exception) {
            tmp.delete()
            throw e
        }
    }

    private fun startPlayback() {
        if (activeItems.isEmpty()) return
        playbackStarted = true
        statusPanel.visibility = View.GONE
        settingsButton.visibility = View.GONE
        playCurrentItem()
    }

    private fun playCurrentItem() {
        if (activeItems.isEmpty()) return
        imageJob?.cancel()
        player.stop()
        val item = activeItems[currentIndex.coerceIn(activeItems.indices)]
        val file = File(item.localPath)
        if (!file.exists()) { nextItem(); return }
        if (item.kind == "video") {
            imageView.visibility = View.GONE
            playerView.visibility = View.VISIBLE
            player.setMediaItem(MediaItem.fromUri(Uri.fromFile(file)))
            player.prepare()
            player.playWhenReady = true
        } else {
            playerView.visibility = View.GONE
            imageView.visibility = View.VISIBLE
            imageView.setImageBitmap(BitmapFactory.decodeFile(file.absolutePath))
            imageJob = scope.launch {
                delay(item.durationSeconds * 1000L)
                nextItem()
            }
        }
    }

    private fun nextItem() {
        if (activeItems.isEmpty()) return
        currentIndex = (currentIndex + 1) % activeItems.size
        playCurrentItem()
    }

    private fun showPairingState(message: String) {
        playbackStarted = false
        player.stop()
        imageJob?.cancel()
        playerView.visibility = View.GONE
        imageView.visibility = View.GONE
        statusPanel.visibility = View.VISIBLE
        codeText.visibility = View.VISIBLE
        findViewById<TextView>(R.id.codeLabel).visibility = View.VISIBLE
        statusText.text = message
        serverInput.visibility = View.GONE
        saveServerButton.visibility = View.GONE
        settingsButton.visibility = if (serverUrl.isBlank()) View.GONE else View.VISIBLE
    }

    private fun showServerSettings() {
        playbackStarted = false
        player.pause()
        imageJob?.cancel()
        playerView.visibility = View.GONE
        imageView.visibility = View.GONE
        statusPanel.visibility = View.VISIBLE
        serverInput.visibility = View.VISIBLE
        saveServerButton.visibility = View.VISIBLE
        settingsButton.visibility = View.GONE
        statusText.text = "Informe o IP do computador que está executando o Conecta Sign."
        serverInput.requestFocus()
    }

    private fun saveCachedPlaylist(playlist: JSONObject) {
        prefs.edit().putString("cached_playlist", playlist.toString()).putString("playlist_version", playlist.optString("updatedAt")).apply()
    }

    private fun loadCachedPlaylist() {
        val raw = prefs.getString("cached_playlist", null) ?: return
        playlistVersion = prefs.getString("playlist_version", "") ?: ""
        runCatching {
            val playlist = JSONObject(raw)
            val arr = playlist.optJSONArray("items") ?: return@runCatching
            val mediaDir = File(filesDir, "media")
            val list = mutableListOf<PlaylistItem>()
            for (i in 0 until arr.length()) {
                val o = arr.optJSONObject(i) ?: continue
                val id = o.optString("id")
                val kind = o.optString("kind")
                val url = o.optString("url")
                val duration = o.optInt("durationSeconds", 10)
                val ext = Uri.parse(url).lastPathSegment?.substringAfterLast('.', "")?.takeIf { it.length <= 5 }
                val filename = if (ext.isNullOrBlank()) id else "$id.$ext"
                val file = File(mediaDir, filename)
                if (file.exists() && file.length() > 0L) list += PlaylistItem(id, o.optString("name", id), kind, duration, url, file.absolutePath)
            }
            if (list.isNotEmpty()) {
                activeItems = list
                currentIndex = 0
            }
        }
    }

    private fun getJson(url: String): JSONObject {
        val req = Request.Builder().url(url).build()
        client.newCall(req).execute().use { response ->
            val text = response.body?.string() ?: "{}"
            if (!response.isSuccessful && response.code != 404) throw IllegalStateException("HTTP ${response.code}")
            return JSONObject(text)
        }
    }

    private fun postHeartbeat() {
        val payload = JSONObject().put("pairingCode", pairingCode).toString()
        val req = Request.Builder().url("$serverUrl/api/player/heartbeat").post(payload.toRequestBody("application/json".toMediaType())).build()
        client.newCall(req).execute().close()
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_BACK && event?.isLongPress == true) {
            showServerSettings()
            return true
        }
        return super.onKeyDown(keyCode, event)
    }

    override fun onResume() { super.onResume(); enterImmersive() }

    override fun onDestroy() {
        super.onDestroy()
        imageJob?.cancel()
        scope.cancel()
        player.release()
    }
}
