package com.conectasolucoes.conectasign

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import android.media.MediaMetadataRetriever
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.net.wifi.WifiInfo
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Bundle
import android.util.Base64
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
    private lateinit var brandLogo: ImageView
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
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(25, TimeUnit.SECONDS)
        .build()
    private val prefs by lazy { getSharedPreferences("conecta_sign", MODE_PRIVATE) }

    private var pairingCode = ""
    private var serverUrl = ""
    private var activeItems = mutableListOf<PlaylistItem>()
    private var currentIndex = -1
    private var imageJob: Job? = null
    private var connectivityJob: Job? = null
    private var pairedTv: JSONObject? = null
    private var currentPlaylistId = ""

    data class PlaylistItem(
        val id: String,
        val name: String,
        val kind: String,
        val url: String,
        val localPath: String,
        val durationMs: Long
    )

    data class NetInfo(val ssid: String, val rssi: Int, val quality: String, val ip: String)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        enterImmersive()

        playerView = findViewById(R.id.playerView)
        imageView = findViewById(R.id.imageView)
        statusPanel = findViewById(R.id.statusPanel)
        brandLogo = findViewById(R.id.brandLogo)
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

        loadOfficialLogo()
        requestNetworkPermissions()

        player = ExoPlayer.Builder(this).build()
        playerView.player = player
        player.repeatMode = Player.REPEAT_MODE_OFF
        player.addListener(object : Player.Listener {
            override fun onPlaybackStateChanged(state: Int) {
                if (state == Player.STATE_ENDED) playNext()
            }
        })

        pairingCode = prefs.getString("pairing_code", null)
            ?: Random.nextInt(100000, 999999).toString().also { prefs.edit().putString("pairing_code", it).apply() }
        codeText.text = "${pairingCode.take(3)} ${pairingCode.takeLast(3)}"

        serverUrl = prefs.getString("server_url", "") ?: ""
        serverInput.setText(serverUrl.removePrefix("http://").removeSuffix(":8799"))
        saveServerButton.setOnClickListener { saveAndConnect() }
        settingsButton.setOnClickListener { showServerSettings() }

        updateNetworkInfo()
        loadCachedPlaylist()
        if (serverUrl.isBlank()) showServerSettings() else {
            if (activeItems.isNotEmpty()) playItem(0, 0)
            else showPairingState("Conectando ao Console...")
            startConnectivityLoop()
        }
    }

    private fun loadOfficialLogo() {
        runCatching {
            val text = resources.openRawResource(R.raw.logo_conecta_base64).bufferedReader().use { it.readText().trim() }
            val bytes = Base64.decode(text, Base64.DEFAULT)
            brandLogo.setImageBitmap(BitmapFactory.decodeByteArray(bytes, 0, bytes.size))
        }.onFailure {
            brandLogo.visibility = View.GONE
        }
    }

    private fun enterImmersive() {
        window.decorView.systemUiVisibility = View.SYSTEM_UI_FLAG_FULLSCREEN or
            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or
            View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION or
            View.SYSTEM_UI_FLAG_LAYOUT_STABLE
    }

    private fun requestNetworkPermissions() {
        val list = mutableListOf<String>()
        if (Build.VERSION.SDK_INT <= 32 && ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            list += Manifest.permission.ACCESS_FINE_LOCATION
        }
        if (Build.VERSION.SDK_INT >= 33 && ActivityCompat.checkSelfPermission(this, Manifest.permission.NEARBY_WIFI_DEVICES) != PackageManager.PERMISSION_GRANTED) {
            list += Manifest.permission.NEARBY_WIFI_DEVICES
        }
        if (list.isNotEmpty()) ActivityCompat.requestPermissions(this, list.toTypedArray(), 104)
    }

    private fun wifiInfoModern(): WifiInfo? {
        return runCatching {
            val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
            val network = cm.activeNetwork ?: return@runCatching null
            val caps = cm.getNetworkCapabilities(network) ?: return@runCatching null
            if (!caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) return@runCatching null
            if (Build.VERSION.SDK_INT >= 31) caps.transportInfo as? WifiInfo
            else @Suppress("DEPRECATION") (applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager).connectionInfo
        }.getOrNull()
    }

    private fun networkInfo(): NetInfo {
        val wi = wifiInfoModern()
        var ssid = wi?.ssid?.trim('"').orEmpty()
        if (ssid.isBlank() || ssid.equals("<unknown ssid>", true)) {
            ssid = when {
                Build.VERSION.SDK_INT >= 33 && ActivityCompat.checkSelfPermission(this, Manifest.permission.NEARBY_WIFI_DEVICES) != PackageManager.PERMISSION_GRANTED -> "Permita Dispositivos próximos"
                Build.VERSION.SDK_INT <= 32 && ActivityCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED -> "Permita Localização"
                else -> "SSID indisponível no Android"
            }
        }
        val rssi = wi?.rssi ?: -127
        val quality = when {
            rssi >= -50 -> "Excelente"
            rssi >= -60 -> "Muito boa"
            rssi >= -70 -> "Boa"
            rssi >= -80 -> "Regular"
            rssi > -120 -> "Fraca"
            else -> "—"
        }
        return NetInfo(ssid, rssi, quality, deviceIp())
    }

    private fun deviceIp(): String = runCatching {
        NetworkInterface.getNetworkInterfaces().toList()
            .flatMap { it.inetAddresses.toList() }
            .firstOrNull { !it.isLoopbackAddress && it is Inet4Address }?.hostAddress ?: "—"
    }.getOrDefault("—")

    private fun updateNetworkInfo() {
        val n = networkInfo()
        ssidText.text = n.ssid
        signalText.text = if (n.rssi > -120) "${n.rssi} dBm" else "—"
        qualityText.text = n.quality
        ipText.text = n.ip
    }

    private fun saveAndConnect() {
        val raw = serverInput.text.toString().trim()
        if (raw.isBlank()) { statusText.text = "Informe o IP do computador."; return }
        scope.launch {
            saveServerButton.isEnabled = false
            statusText.text = "Testando $raw:8799..."
            val found = withContext(Dispatchers.IO) { resolveServer(raw) }
            saveServerButton.isEnabled = true
            if (found == null) {
                statusText.text = "Não consegui acessar $raw:8799. Use o Console 0.9.2.5 e confirme o Firewall do Windows."
                return@launch
            }
            serverUrl = found
            prefs.edit().putString("server_url", found).apply()
            serverInput.visibility = View.GONE
            saveServerButton.visibility = View.GONE
            settingsButton.visibility = View.VISIBLE
            statusText.text = "Console encontrado. Aguardando pareamento..."
            startConnectivityLoop()
        }
    }

    private fun resolveServer(raw: String): String? {
        val clean = raw.removePrefix("http://").removePrefix("https://").trimEnd('/')
        val candidate = if (Regex(":\\d+$").containsMatchIn(clean)) "http://$clean" else "http://$clean:8799"
        return runCatching { getJson("$candidate/api/state"); candidate }.getOrNull()
    }

    private fun startConnectivityLoop() {
        connectivityJob?.cancel()
        connectivityJob = scope.launch {
            while (isActive) {
                updateNetworkInfo()
                try {
                    val state = withContext(Dispatchers.IO) { getJson("$serverUrl/api/state") }
                    offlineBadge.visibility = View.GONE
                    applyState(state)
                    withContext(Dispatchers.IO) { postHeartbeat() }
                } catch (_: Exception) {
                    if (activeItems.isNotEmpty()) offlineBadge.visibility = View.VISIBLE
                    else showPairingState("Sem conexão com o Console em ${serverUrl.removePrefix("http://")}")
                }
                delay(5000)
            }
        }
    }

    private suspend fun applyState(state: JSONObject) {
        val tvs = state.optJSONArray("tvs") ?: JSONArray()
        val tv = (0 until tvs.length()).mapNotNull { tvs.optJSONObject(it) }
            .firstOrNull { it.optString("pairingCode") == pairingCode }
        pairedTv = tv
        if (tv == null) { showPairingState("Console conectado. Cadastre o código acima no painel."); return }

        val playlist = choosePlaylist(state, tv)
        if (playlist == null) { showPairingState("Dispositivo pareado. Aguardando playlist..."); return }
        currentPlaylistId = playlist.optString("id")
        val normalized = normalizePlaylist(state, playlist)
        val signature = normalized.toString().hashCode().toString()
        if (prefs.getString("playlist_signature", "") != signature || activeItems.isEmpty()) {
            val parsed = withContext(Dispatchers.IO) { cachePlaylist(normalized) }
            if (parsed.isEmpty()) { showPairingState("Playlist sem mídia compatível."); return }
            activeItems = parsed.toMutableList()
            prefs.edit().putString("cached_playlist", normalized.toString()).putString("playlist_signature", signature).apply()
            playItem(0, 0)
        } else if (currentIndex < 0 && activeItems.isNotEmpty()) playItem(0, 0)
    }

    private fun choosePlaylist(state: JSONObject, tv: JSONObject): JSONObject? {
        val arr = state.optJSONArray("playlists") ?: JSONArray()
        val all = (0 until arr.length()).mapNotNull { arr.optJSONObject(it) }.filter { it.optBoolean("active", true) }
        val fixed = tv.optString("playlistId")
        if (fixed.isNotBlank()) all.firstOrNull { it.optString("id") == fixed }?.let { return it }
        val tvId = tv.optString("id")
        all.firstOrNull { p ->
            val ids = p.optJSONArray("tvIds") ?: JSONArray()
            (0 until ids.length()).any { ids.optString(it) == tvId }
        }?.let { return it }
        return all.firstOrNull { it.optBoolean("fallback", false) }
    }

    private fun normalizePlaylist(state: JSONObject, playlist: JSONObject): JSONObject {
        val mediaArr = state.optJSONArray("media") ?: JSONArray()
        val mediaMap = (0 until mediaArr.length()).mapNotNull { mediaArr.optJSONObject(it) }.associateBy { it.optString("id") }
        val src = playlist.optJSONArray("items") ?: JSONArray()
        val out = JSONArray()
        for (i in 0 until src.length()) {
            val item = src.optJSONObject(i) ?: continue
            val mediaId = item.optString("mediaId").ifBlank { item.optString("id") }
            val m = mediaMap[mediaId] ?: continue
            var url = m.optString("url")
            if (url.startsWith('/')) url = serverUrl + url
            if (url.isBlank()) continue
            out.put(JSONObject()
                .put("id", m.optString("id"))
                .put("name", m.optString("name", m.optString("fileName", mediaId)))
                .put("kind", m.optString("kind"))
                .put("url", url)
                .put("durationSeconds", item.optInt("durationSeconds", m.optInt("durationSeconds", 10)).coerceAtLeast(1)))
        }
        return JSONObject().put("id", playlist.optString("id")).put("items", out)
    }

    private fun cachePlaylist(p: JSONObject): List<PlaylistItem> {
        val arr = p.optJSONArray("items") ?: JSONArray()
        val dir = File(filesDir, "media").apply { mkdirs() }
        val result = mutableListOf<PlaylistItem>()
        for (i in 0 until arr.length()) {
            val o = arr.optJSONObject(i) ?: continue
            val id = o.optString("id")
            val kind = o.optString("kind")
            val url = o.optString("url")
            if (id.isBlank() || url.isBlank() || kind !in setOf("video", "image")) continue
            val ext = Uri.parse(url).lastPathSegment?.substringAfterLast('.', "")?.takeIf { it.length <= 5 }
            val file = File(dir, if (ext.isNullOrBlank()) id else "$id.$ext")
            if (!file.exists() || file.length() == 0L) downloadTo(url, file)
            if (!file.exists() || file.length() == 0L) continue
            val duration = if (kind == "video") videoDuration(file).coerceAtLeast(1000L) else o.optInt("durationSeconds", 10) * 1000L
            result += PlaylistItem(id, o.optString("name", id), kind, url, file.absolutePath, duration)
        }
        return result
    }

    private fun downloadTo(url: String, target: File) {
        val tmp = File(target.parentFile, target.name + ".part")
        client.newCall(Request.Builder().url(url).build()).execute().use { r ->
            if (!r.isSuccessful) error("HTTP ${r.code}")
            FileOutputStream(tmp).use { out -> (r.body ?: error("sem corpo")).byteStream().copyTo(out) }
        }
        if (target.exists()) target.delete()
        if (!tmp.renameTo(target)) error("Falha ao salvar")
    }

    private fun videoDuration(file: File): Long = runCatching {
        val r = MediaMetadataRetriever(); r.setDataSource(file.absolutePath)
        val d = r.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLongOrNull() ?: 0L
        r.release(); d
    }.getOrDefault(0L)

    private fun playItem(index: Int, offset: Long) {
        if (activeItems.isEmpty()) return
        currentIndex = index % activeItems.size
        val item = activeItems[currentIndex]
        statusPanel.visibility = View.GONE
        settingsButton.visibility = View.GONE
        imageJob?.cancel(); player.stop()
        if (item.kind == "video") {
            imageView.visibility = View.GONE; playerView.visibility = View.VISIBLE
            player.setMediaItem(MediaItem.fromUri(Uri.fromFile(File(item.localPath))))
            player.prepare(); player.seekTo(offset.coerceAtLeast(0)); player.playWhenReady = true
        } else {
            playerView.visibility = View.GONE; imageView.visibility = View.VISIBLE
            imageView.setImageBitmap(BitmapFactory.decodeFile(item.localPath))
            imageJob = scope.launch { delay(item.durationMs); playNext() }
        }
    }

    private fun playNext() { if (activeItems.isNotEmpty()) playItem((currentIndex + 1) % activeItems.size, 0) }

    private fun showPairingState(message: String) {
        player.stop(); imageJob?.cancel(); currentIndex = -1
        playerView.visibility = View.GONE; imageView.visibility = View.GONE; statusPanel.visibility = View.VISIBLE
        statusText.text = message
        serverInput.visibility = if (serverUrl.isBlank()) View.VISIBLE else View.GONE
        saveServerButton.visibility = if (serverUrl.isBlank()) View.VISIBLE else View.GONE
        settingsButton.visibility = if (serverUrl.isBlank()) View.GONE else View.VISIBLE
        updateNetworkInfo()
    }

    private fun showServerSettings() {
        player.pause(); imageJob?.cancel(); currentIndex = -1
        playerView.visibility = View.GONE; imageView.visibility = View.GONE; statusPanel.visibility = View.VISIBLE
        serverInput.visibility = View.VISIBLE; saveServerButton.visibility = View.VISIBLE; settingsButton.visibility = View.GONE
        serverInput.setText(serverUrl.removePrefix("http://").removeSuffix(":8799"))
        statusText.text = "Informe o IP do PC com o Console 0.9.2.5."
        updateNetworkInfo(); serverInput.requestFocus()
    }

    private fun loadCachedPlaylist() {
        val raw = prefs.getString("cached_playlist", null) ?: return
        runCatching {
            val p = JSONObject(raw); val arr = p.optJSONArray("items") ?: return@runCatching
            val dir = File(filesDir, "media"); val list = mutableListOf<PlaylistItem>()
            for (i in 0 until arr.length()) {
                val o = arr.optJSONObject(i) ?: continue
                val id = o.optString("id"); val kind = o.optString("kind"); val url = o.optString("url")
                val ext = Uri.parse(url).lastPathSegment?.substringAfterLast('.', "")?.takeIf { it.length <= 5 }
                val f = File(dir, if (ext.isNullOrBlank()) id else "$id.$ext")
                if (f.exists()) {
                    val d = if (kind == "video") videoDuration(f).coerceAtLeast(1000L) else o.optInt("durationSeconds", 10) * 1000L
                    list += PlaylistItem(id, o.optString("name", id), kind, url, f.absolutePath, d)
                }
            }
            activeItems = list
        }
    }

    private fun postHeartbeat() {
        val tv = pairedTv ?: return
        val n = networkInfo()
        val body = JSONObject(tv.toString())
            .put("lastSeen", Instant.now().toString())
            .put("wifiSsid", n.ssid).put("wifiRssi", n.rssi).put("ipAddress", n.ip)
            .put("currentPlaylistId", currentPlaylistId)
            .put("currentMediaId", activeItems.getOrNull(currentIndex)?.id ?: "")
            .put("appVersion", BuildConfig.VERSION_NAME)
        val req = Request.Builder().url("$serverUrl/api/tvs")
            .put(body.toString().toRequestBody("application/json".toMediaType())).build()
        runCatching { client.newCall(req).execute().close() }
    }

    private fun getJson(url: String): JSONObject {
        client.newCall(Request.Builder().url(url).build()).execute().use { r ->
            val txt = r.body?.string() ?: "{}"
            if (!r.isSuccessful) error("HTTP ${r.code}")
            return JSONObject(txt)
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 104) updateNetworkInfo()
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_BACK && event?.isLongPress == true) { showServerSettings(); return true }
        return super.onKeyDown(keyCode, event)
    }

    override fun onResume() { super.onResume(); enterImmersive(); updateNetworkInfo() }
    override fun onDestroy() { connectivityJob?.cancel(); imageJob?.cancel(); scope.cancel(); player.release(); super.onDestroy() }
}
