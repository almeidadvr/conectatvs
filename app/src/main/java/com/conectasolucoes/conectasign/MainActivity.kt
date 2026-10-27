package com.conectasolucoes.conectasign

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import android.media.MediaMetadataRetriever
import android.net.Uri
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Bundle
import android.view.KeyEvent
import android.view.View
import android.view.WindowManager
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
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
import java.net.Inet4Address
import java.net.NetworkInterface
import java.time.Instant
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
    private lateinit var ssidText: TextView
    private lateinit var signalText: TextView
    private lateinit var qualityText: TextView
    private lateinit var ipText: TextView

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private val client = OkHttpClient.Builder()
        .connectTimeout(4, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .build()
    private val prefs by lazy { getSharedPreferences("conecta_sign", MODE_PRIVATE) }

    private var pairingCode = ""
    private var serverUrl = ""
    private var activeItems = mutableListOf<PlaylistItem>()
    private var currentIndex = -1
    private var imageJob: Job? = null
    private var syncJob: Job? = null
    private var connectivityJob: Job? = null
    private var playlistVersion = ""
    private var currentPlaylistId = ""
    private var playbackStarted = false
    private var syncAnchorMs = 0L
    private var serverClockOffsetMs = 0L
    private var pairedTv: JSONObject? = null

    data class PlaylistItem(
        val id: String,
        val name: String,
        val kind: String,
        val durationSeconds: Int,
        val url: String,
        val localPath: String,
        val durationMs: Long
    )

    data class NetworkInfo(
        val ssid: String,
        val rssi: Int,
        val quality: String,
        val ip: String
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
        ssidText = findViewById(R.id.ssidText)
        signalText = findViewById(R.id.signalText)
        qualityText = findViewById(R.id.qualityText)
        ipText = findViewById(R.id.ipText)

        player = ExoPlayer.Builder(this).build()
        playerView.player = player
        player.repeatMode = Player.REPEAT_MODE_OFF
        player.addListener(object : Player.Listener {
            override fun onPlaybackStateChanged(playbackState: Int) {
                if (playbackState == Player.STATE_ENDED && activeItems.isNotEmpty()) syncPlayback(true)
            }
        })

        pairingCode = prefs.getString("pairing_code", null)
            ?: Random.nextInt(100000, 999999).toString().also {
                prefs.edit().putString("pairing_code", it).apply()
            }
        codeText.text = "${pairingCode.take(3)} ${pairingCode.takeLast(3)}"

        serverUrl = prefs.getString("server_url", "") ?: ""
        serverInput.setText(serverUrl.removePrefix("http://").removeSuffix(":8799"))
        saveServerButton.setOnClickListener { saveAndConnect() }
        settingsButton.setOnClickListener { showServerSettings() }

        requestWifiPermissionIfNeeded()
        updateNetworkInfo()
        loadCachedPlaylist()
        startLocalSyncLoop()

        if (serverUrl.isBlank()) {
            showServerSettings()
        } else {
            if (activeItems.isNotEmpty()) {
                offlineBadge.visibility = View.VISIBLE
                syncPlayback(true)
            } else {
                showPairingState("Conectando ao servidor...")
            }
            startConnectivityLoop()
        }
    }

    private fun enterImmersive() {
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_FULLSCREEN or
            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or
            View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION or
            View.SYSTEM_UI_FLAG_LAYOUT_STABLE
    }

    private fun requestWifiPermissionIfNeeded() {
        val permissions = mutableListOf<String>()
        if (ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            permissions += Manifest.permission.ACCESS_FINE_LOCATION
        }
        if (Build.VERSION.SDK_INT >= 33 && ActivityCompat.checkSelfPermission(this, Manifest.permission.NEARBY_WIFI_DEVICES) != PackageManager.PERMISSION_GRANTED) {
            permissions += Manifest.permission.NEARBY_WIFI_DEVICES
        }
        if (permissions.isNotEmpty()) ActivityCompat.requestPermissions(this, permissions.toTypedArray(), 104)
    }

    private fun networkInfo(): NetworkInfo {
        val wm = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        val wi = runCatching { wm.connectionInfo }.getOrNull()
        var ssid = wi?.ssid?.trim('"') ?: "Wi-Fi"
        if (ssid.isBlank() || ssid == "<unknown ssid>") ssid = "Wi-Fi conectado"
        val rssi = wi?.rssi ?: -127
        val quality = when {
            rssi >= -50 -> "Excelente"
            rssi >= -60 -> "Muito boa"
            rssi >= -70 -> "Boa"
            rssi >= -80 -> "Regular"
            else -> "Fraca"
        }
        val ip = deviceIp()
        return NetworkInfo(ssid, rssi, quality, ip)
    }

    private fun deviceIp(): String {
        return runCatching {
            NetworkInterface.getNetworkInterfaces().toList()
                .flatMap { it.inetAddresses.toList() }
                .firstOrNull { !it.isLoopbackAddress && it is Inet4Address }
                ?.hostAddress ?: "—"
        }.getOrDefault("—")
    }

    private fun updateNetworkInfo() {
        val n = networkInfo()
        ssidText.text = n.ssid
        signalText.text = if (n.rssi > -120) "${n.rssi} dBm" else "—"
        qualityText.text = n.quality
        ipText.text = n.ip
    }

    private fun startLocalSyncLoop() {
        syncJob?.cancel()
        syncJob = scope.launch {
            while (isActive) {
                delay(1000)
                if (playbackStarted && activeItems.isNotEmpty()) syncPlayback(false)
            }
        }
    }

    private fun startConnectivityLoop() {
        connectivityJob?.cancel()
        connectivityJob = scope.launch { connectivityLoop() }
    }

    private fun saveAndConnect() {
        val raw = serverInput.text.toString().trim()
        if (raw.isBlank()) {
            statusText.text = "Informe o IP do computador."
            return
        }
        scope.launch {
            saveServerButton.isEnabled = false
            statusText.text = "Procurando o Conecta Mídia..."
            val found = withContext(Dispatchers.IO) { resolveServer(raw) }
            saveServerButton.isEnabled = true
            if (found == null) {
                statusText.text = "Não encontrei o servidor. Confira o IP e se o console está aberto no Windows."
                return@launch
            }
            serverUrl = found
            prefs.edit().putString("server_url", found).apply()
            serverInput.visibility = View.GONE
            saveServerButton.visibility = View.GONE
            settingsButton.visibility = View.VISIBLE
            statusText.text = "Servidor encontrado. Aguardando pareamento..."
            startConnectivityLoop()
        }
    }

    private fun resolveServer(raw: String): String? {
        val cleaned = raw.removePrefix("http://").removePrefix("https://").trimEnd('/')
        val candidate = if (Regex(":\\d+$").containsMatchIn(cleaned)) "http://$cleaned" else "http://$cleaned:8799"
        return runCatching {
            getJson("$candidate/api/state")
            candidate
        }.getOrNull()
    }

    private suspend fun connectivityLoop() {
        while (scope.isActive) {
            if (serverUrl.isBlank()) return
            updateNetworkInfo()
            try {
                val state = withContext(Dispatchers.IO) { getJson("$serverUrl/api/state") }
                offlineBadge.visibility = View.GONE
                applyState(state)
                withContext(Dispatchers.IO) { postHeartbeat() }
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

    private suspend fun applyState(state: JSONObject) {
        val tvs = state.optJSONArray("tvs") ?: JSONArray()
        pairedTv = (0 until tvs.length())
            .mapNotNull { tvs.optJSONObject(it) }
            .firstOrNull { it.optString("pairingCode") == pairingCode }

        val tv = pairedTv
        if (tv == null) {
            showPairingState("Cadastre este código no painel do Conecta Mídia.")
            return
        }

        val selected = choosePlaylist(state, tv)
        if (selected == null) {
            showPairingState("Dispositivo pareado. Aguardando uma playlist...")
            return
        }

        val normalized = normalizePlaylist(state, selected)
        val version = selected.optString("updatedAt").ifBlank { selected.toString().hashCode().toString() }
        currentPlaylistId = selected.optString("id")

        if (version != playlistVersion || activeItems.isEmpty()) {
            val parsed = withContext(Dispatchers.IO) { cachePlaylist(normalized) }
            if (parsed.isEmpty()) {
                showPairingState("Playlist sem arquivos compatíveis.")
                return
            }
            activeItems = parsed.toMutableList()
            playlistVersion = version
            currentIndex = -1
            syncAnchorMs = System.currentTimeMillis()
            serverClockOffsetMs = 0L
            saveCachedPlaylist(normalized)
            saveSyncState()
            syncPlayback(true)
        } else {
            if (syncAnchorMs <= 0L) syncAnchorMs = System.currentTimeMillis()
            syncPlayback(false)
        }
    }

    private fun choosePlaylist(state: JSONObject, tv: JSONObject): JSONObject? {
        val playlists = state.optJSONArray("playlists") ?: JSONArray()
        val targeted = (0 until playlists.length()).mapNotNull { playlists.optJSONObject(it) }
            .filter { it.optBoolean("active", true) && targetsTv(it, tv) }

        val scheduled = targeted.filter { !it.optBoolean("fallback", false) && hasSchedule(it) && isScheduleActive(it) }
        if (scheduled.isNotEmpty()) return scheduled.first()

        val regular = targeted.filter { !it.optBoolean("fallback", false) && !hasSchedule(it) }
        if (regular.isNotEmpty()) return regular.first()

        val fixedId = tv.optString("playlistId")
        if (fixedId.isNotBlank()) {
            (0 until playlists.length()).mapNotNull { playlists.optJSONObject(it) }
                .firstOrNull { it.optString("id") == fixedId && it.optBoolean("active", true) }
                ?.let { return it }
        }

        return targeted.firstOrNull { it.optBoolean("fallback", false) }
    }

    private fun targetsTv(p: JSONObject, tv: JSONObject): Boolean {
        val tvId = tv.optString("id")
        if (p.optString("id") == tv.optString("playlistId") || p.optString("id") == tv.optString("currentPlaylistId")) return true
        val tvIds = p.optJSONArray("tvIds") ?: JSONArray()
        if ((0 until tvIds.length()).any { tvIds.optString(it) == tvId }) return true
        val tvGroups = tv.optJSONArray("groupIds") ?: JSONArray()
        val groups = (0 until tvGroups.length()).map { tvGroups.optString(it) }.toSet()
        val pGroups = p.optJSONArray("groupIds") ?: JSONArray()
        return (0 until pGroups.length()).any { pGroups.optString(it) in groups }
    }

    private fun hasSchedule(p: JSONObject): Boolean = p.optString("startTime").isNotBlank() || p.optString("endTime").isNotBlank()

    private fun isScheduleActive(p: JSONObject): Boolean {
        fun minutes(v: String): Int? {
            val x = v.split(':')
            if (x.size < 2) return null
            return x[0].toIntOrNull()?.times(60)?.plus(x[1].toIntOrNull() ?: return null)
        }
        val now = java.util.Calendar.getInstance().let { it.get(java.util.Calendar.HOUR_OF_DAY) * 60 + it.get(java.util.Calendar.MINUTE) }
        val start = minutes(p.optString("startTime"))
        val end = minutes(p.optString("endTime"))
        if (start == null && end == null) return true
        if (start != null && end == null) return now >= start
        if (start == null && end != null) return now <= end
        return if (start!! <= end!!) now in start..end else now >= start || now <= end
    }

    private fun normalizePlaylist(state: JSONObject, playlist: JSONObject): JSONObject {
        val mediaArr = state.optJSONArray("media") ?: JSONArray()
        val mediaMap = (0 until mediaArr.length()).mapNotNull { mediaArr.optJSONObject(it) }
            .associateBy { it.optString("id") }
        val srcItems = playlist.optJSONArray("items") ?: JSONArray()
        val out = JSONArray()
        for (i in 0 until srcItems.length()) {
            val src = srcItems.optJSONObject(i) ?: continue
            val mediaId = src.optString("mediaId").ifBlank { src.optString("id") }
            val m = mediaMap[mediaId] ?: continue
            var url = m.optString("url")
            if (url.startsWith('/')) url = serverUrl + url
            if (url.isBlank()) continue
            out.put(JSONObject()
                .put("id", m.optString("id"))
                .put("name", m.optString("name", m.optString("fileName", mediaId)))
                .put("kind", m.optString("kind"))
                .put("url", url)
                .put("durationSeconds", src.optInt("durationSeconds", m.optInt("durationSeconds", 10)).coerceAtLeast(1)))
        }
        return JSONObject()
            .put("id", playlist.optString("id"))
            .put("updatedAt", playlist.optString("updatedAt").ifBlank { playlist.toString().hashCode().toString() })
            .put("items", out)
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
        val r = MediaMetadataRetriever()
        r.setDataSource(file.absolutePath)
        val ms = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLongOrNull() ?: 0L
        r.release()
        ms
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
        } catch (e: Exception) {
            tmp.delete()
            throw e
        }
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
        if (activeItems.isEmpty() || syncAnchorMs <= 0L) return
        val (targetIndex, targetOffset) = timelinePosition()
        val target = activeItems[targetIndex]
        val sameItem = currentIndex == targetIndex && playbackStarted
        if (!force && sameItem) {
            if (target.kind == "video" && player.playbackState != Player.STATE_IDLE) {
                val drift = abs(player.currentPosition - targetOffset)
                if (drift > 650L) player.seekTo(targetOffset.coerceAtMost((target.durationMs - 200L).coerceAtLeast(0L)))
            }
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
        if (!file.exists()) {
            scope.launch { delay(500); syncPlayback(true) }
            return
        }
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
    }

    private fun showPairingState(message: String) {
        playbackStarted = false
        player.stop()
        imageJob?.cancel()
        playerView.visibility = View.GONE
        imageView.visibility = View.GONE
        statusPanel.visibility = View.VISIBLE
        statusText.text = message
        serverInput.visibility = View.GONE
        saveServerButton.visibility = View.GONE
        settingsButton.visibility = if (serverUrl.isBlank()) View.GONE else View.VISIBLE
        updateNetworkInfo()
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
        statusText.text = "Informe o IP do computador que está executando o Conecta Mídia."
        serverInput.setText(serverUrl.removePrefix("http://").removeSuffix(":8799"))
        serverInput.requestFocus()
        updateNetworkInfo()
    }

    private fun saveCachedPlaylist(playlist: JSONObject) {
        prefs.edit()
            .putString("cached_playlist", playlist.toString())
            .putString("playlist_version", playlist.optString("updatedAt"))
            .putString("current_playlist_id", currentPlaylistId)
            .apply()
    }

    private fun saveSyncState() {
        prefs.edit().putLong("sync_anchor_ms", syncAnchorMs).putLong("server_clock_offset_ms", serverClockOffsetMs).apply()
    }

    private fun loadCachedPlaylist() {
        syncAnchorMs = prefs.getLong("sync_anchor_ms", 0L)
        serverClockOffsetMs = prefs.getLong("server_clock_offset_ms", 0L)
        currentPlaylistId = prefs.getString("current_playlist_id", "") ?: ""
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
            if (!response.isSuccessful) error("HTTP ${response.code}")
            return JSONObject(text)
        }
    }

    private fun postHeartbeat() {
        val tv = pairedTv ?: return
        val payload = JSONObject(tv.toString())
        val n = networkInfo()
        payload.put("lastSeen", Instant.now().toString())
        payload.put("wifiSsid", n.ssid)
        payload.put("wifiRssi", n.rssi)
        payload.put("ipAddress", n.ip)
        payload.put("currentPlaylistId", currentPlaylistId)
        payload.put("currentMediaId", activeItems.getOrNull(currentIndex)?.id ?: "")
        payload.put("totalItems", activeItems.size)
        payload.put("downloadedItems", activeItems.count { File(it.localPath).exists() })
        payload.put("manufacturer", Build.MANUFACTURER)
        payload.put("model", Build.MODEL)
        payload.put("androidVersion", Build.VERSION.RELEASE)
        payload.put("sdkInt", Build.VERSION.SDK_INT)
        payload.put("appVersion", BuildConfig.VERSION_NAME)
        payload.put("screenWidth", resources.displayMetrics.widthPixels)
        payload.put("screenHeight", resources.displayMetrics.heightPixels)

        val req = Request.Builder()
            .url("$serverUrl/api/tvs")
            .put(payload.toString().toRequestBody("application/json".toMediaType()))
            .build()
        runCatching { client.newCall(req).execute().close() }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 104) updateNetworkInfo()
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_BACK && event?.isLongPress == true) {
            showServerSettings()
            return true
        }
        return super.onKeyDown(keyCode, event)
    }

    override fun onResume() {
        super.onResume()
        enterImmersive()
        updateNetworkInfo()
    }

    override fun onDestroy() {
        super.onDestroy()
        imageJob?.cancel()
        syncJob?.cancel()
        connectivityJob?.cancel()
        scope.cancel()
        player.release()
    }
}
