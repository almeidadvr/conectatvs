from pathlib import Path

main = Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
s = main.read_text(encoding='utf-8')

# 0.8.7: preservar saveAndConnect()/resolveServer().
s = s.replace('import android.graphics.BitmapFactory', 'import android.graphics.BitmapFactory\nimport android.graphics.Color')
s = s.replace('import android.view.WindowManager', 'import android.view.WindowManager\nimport android.util.TypedValue')
s = s.replace('import java.io.FileOutputStream', 'import java.io.FileOutputStream\nimport java.io.FileInputStream')
s = s.replace('import kotlin.math.abs', 'import kotlin.math.abs\nimport kotlin.math.roundToInt')

s = s.replace(
    '    private lateinit var offlineBadge: TextView\n    private lateinit var watermarkContainer: LinearLayout',
    '    private lateinit var offlineBadge: TextView\n    private lateinit var wifiPanel: LinearLayout\n    private lateinit var wifiNetworkText: TextView\n    private lateinit var wifiSignalText: TextView\n    private lateinit var wifiQualityText: TextView\n    private lateinit var wifiBarsText: TextView\n    private lateinit var brandLogo: ImageView\n    private lateinit var watermarkContainer: LinearLayout'
)

s = s.replace(
    '    private var syncAnchorMs = 0L\n    private var serverClockOffsetMs = 0L',
    '    private var syncAnchorMs = 0L\n    private var serverClockOffsetMs = 0L\n    private var serverTimeBaseMs = 0L\n    private var monotonicBaseMs = 0L\n    private var lastSyncDriftMs = 0L\n    private var lastSyncRttMs = 0L\n    private var lastSyncSpeed = 1f\n    private var lastHardSyncElapsedMs = 0L\n    private var networkUiJob: Job? = null\n    private data class ClockSample(val rttMs: Long, val offsetMs: Long)\n    private val clockSamples = java.util.ArrayDeque<ClockSample>()'
)

s = s.replace(
    '    data class TimedConfig(val json: JSONObject, val offsetMs: Long)',
    '    data class TimedConfig(val json: JSONObject, val offsetMs: Long, val rttMs: Long)'
)

s = s.replace(
    '        offlineBadge = findViewById(R.id.offlineBadge)\n        watermarkContainer = findViewById(R.id.watermarkContainer)',
    '        offlineBadge = findViewById(R.id.offlineBadge)\n        wifiPanel = findViewById(R.id.wifiPanel)\n        wifiNetworkText = findViewById(R.id.wifiNetworkText)\n        wifiSignalText = findViewById(R.id.wifiSignalText)\n        wifiQualityText = findViewById(R.id.wifiQualityText)\n        wifiBarsText = findViewById(R.id.wifiBarsText)\n        brandLogo = findViewById(R.id.brandLogo)\n        applyTransparentBrandLogo()\n        watermarkContainer = findViewById(R.id.watermarkContainer)'
)

s = s.replace(
    '        loadCachedPlaylist()\n        startLocalSyncLoop()',
    '        applyResponsivePairingLayout()\n        startNetworkUiLoop()\n        loadCachedPlaylist()\n        startLocalSyncLoop()'
)

# Verificação frequente, mas correção só quando necessário.
s = s.replace('                delay(1000)', '                delay(250)', 1)

old_timed = '''    private fun getTimedConfig(url: String): TimedConfig {
        val wallStart = System.currentTimeMillis()
        val monoStart = SystemClock.elapsedRealtime()
        val json = getJson(url)
        val monoEnd = SystemClock.elapsedRealtime()
        val rtt = monoEnd - monoStart
        val localMidpoint = wallStart + (rtt / 2L)
        val serverTime = json.optLong("serverTimeMs", localMidpoint)
        return TimedConfig(json, serverTime - localMidpoint)
    }'''
new_timed = '''    private fun getTimedConfig(url: String): TimedConfig {
        val wallStart = System.currentTimeMillis()
        val monoStart = SystemClock.elapsedRealtime()
        val json = getJson(url)
        val monoEnd = SystemClock.elapsedRealtime()
        val rtt = (monoEnd - monoStart).coerceAtLeast(0L)
        val localMidpoint = wallStart + (rtt / 2L)
        val serverTime = json.optLong("serverTimeMs", localMidpoint)
        return TimedConfig(json, serverTime - localMidpoint, rtt)
    }'''
if old_timed not in s:
    raise SystemExit('getTimedConfig não encontrado')
s = s.replace(old_timed, new_timed)
s = s.replace('applyConfig(timed.json, timed.offsetMs)', 'applyConfig(timed.json, timed.offsetMs, timed.rttMs)')
s = s.replace('private suspend fun applyConfig(cfg: JSONObject, measuredOffsetMs: Long)', 'private suspend fun applyConfig(cfg: JSONObject, measuredOffsetMs: Long, measuredRttMs: Long)')

old_clock = '''        // Suaviza pequenas variações de rede sem deixar um valor antigo dominar.
        serverClockOffsetMs = if (serverClockOffsetMs == 0L) measuredOffsetMs else
            ((serverClockOffsetMs * 3L) + measuredOffsetMs) / 4L'''
if old_clock not in s:
    raise SystemExit('bloco de clock não encontrado')
s = s.replace(old_clock, '        recordClockSample(measuredRttMs, measuredOffsetMs)')

old_now = '    private fun synchronizedNowMs(): Long = System.currentTimeMillis() + serverClockOffsetMs'
new_now = '''    private fun recordClockSample(rttMs: Long, offsetMs: Long) {
        clockSamples.addLast(ClockSample(rttMs, offsetMs))
        while (clockSamples.size > 8) clockSamples.removeFirst()
        val best = clockSamples.toList().sortedBy { it.rttMs }.take(5)
        val offsets = best.map { it.offsetMs }.sorted()
        serverClockOffsetMs = offsets[offsets.size / 2]
        lastSyncRttMs = rttMs
        serverTimeBaseMs = System.currentTimeMillis() + serverClockOffsetMs
        monotonicBaseMs = SystemClock.elapsedRealtime()
    }

    private fun synchronizedNowMs(): Long {
        if (serverTimeBaseMs > 0L && monotonicBaseMs > 0L) {
            return serverTimeBaseMs + (SystemClock.elapsedRealtime() - monotonicBaseMs)
        }
        return System.currentTimeMillis() + serverClockOffsetMs
    }'''
if old_now not in s:
    raise SystemExit('synchronizedNowMs não encontrado')
s = s.replace(old_now, new_now)

start = s.find('    private fun syncPlayback(force: Boolean) {')
end = s.find('    private fun playItem(index: Int, offsetMs: Long) {', start)
if start < 0 or end < 0:
    raise SystemExit('syncPlayback/playItem não encontrados')
new_sync = '''    private fun setSyncSpeed(speed: Float) {
        if (abs(lastSyncSpeed - speed) < 0.001f) return
        lastSyncSpeed = speed
        runCatching { player.setPlaybackSpeed(speed) }
    }

    private fun syncPlayback(force: Boolean) {
        if (activeItems.isEmpty() || syncAnchorMs <= 0L) return
        val (targetIndex, targetOffset) = timelinePosition()
        val target = activeItems[targetIndex]
        val sameItem = currentIndex == targetIndex && playbackStarted
        if (!force && sameItem) {
            if (target.kind == "video" && player.playbackState != Player.STATE_IDLE) {
                val drift = player.currentPosition - targetOffset
                lastSyncDriftMs = drift
                when (abs(drift)) {
                    in 0L..60L -> setSyncSpeed(1f)
                    in 61L..250L -> setSyncSpeed(if (drift > 0) 0.985f else 1.015f)
                    in 251L..500L -> setSyncSpeed(if (drift > 0) 0.97f else 1.03f)
                    else -> {
                        setSyncSpeed(1f)
                        val now = SystemClock.elapsedRealtime()
                        if (now - lastHardSyncElapsedMs >= 1500L) {
                            lastHardSyncElapsedMs = now
                            player.seekTo(targetOffset.coerceAtMost((target.durationMs - 200L).coerceAtLeast(0L)))
                        }
                    }
                }
            } else {
                lastSyncDriftMs = 0L
                setSyncSpeed(1f)
            }
            return
        }
        setSyncSpeed(1f)
        lastSyncDriftMs = 0L
        playItem(targetIndex, targetOffset)
    }

'''
s = s[:start] + new_sync + s[end:]

needle = '''        val file = File(item.localPath)
        if (!file.exists()) { scope.launch { delay(500); syncPlayback(true) }; return }'''
if needle not in s:
    raise SystemExit('ponto de preload não encontrado')
s = s.replace(needle, needle + '\n        warmNextMedia(index)', 1)

helpers = r'''    private fun warmNextMedia(index: Int) {
        if (activeItems.size < 2) return
        val next = activeItems[(index + 1) % activeItems.size]
        scope.launch(Dispatchers.IO) {
            runCatching {
                FileInputStream(File(next.localPath)).use { input ->
                    val buffer = ByteArray(256 * 1024)
                    input.read(buffer)
                }
            }
        }
    }

    private fun applyTransparentBrandLogo() {
        runCatching {
            val bitmap = BitmapFactory.decodeResource(resources, R.drawable.tv_banner_brand)
                .copy(android.graphics.Bitmap.Config.ARGB_8888, true)
            val pixels = IntArray(bitmap.width * bitmap.height)
            bitmap.getPixels(pixels, 0, bitmap.width, 0, 0, bitmap.width, bitmap.height)
            for (i in pixels.indices) {
                val c = pixels[i]
                val r = Color.red(c); val g = Color.green(c); val b = Color.blue(c)
                val avg = (r + g + b) / 3
                if (avg < 105 && b >= r && b >= g) pixels[i] = Color.argb(0, r, g, b)
            }
            bitmap.setPixels(pixels, 0, bitmap.width, 0, 0, bitmap.width, bitmap.height)
            brandLogo.setImageBitmap(bitmap)
        }
    }

    private fun applyResponsivePairingLayout() {
        val dm = resources.displayMetrics
        val density = dm.density.coerceAtLeast(1f)
        val heightDp = dm.heightPixels / density
        val panelWidthPx = (dm.widthPixels * 0.42f).roundToInt().coerceIn(dp(420), dp(680))
        val lp = statusPanel.layoutParams as FrameLayout.LayoutParams
        lp.width = panelWidthPx
        statusPanel.layoutParams = lp
        val scale = when {
            heightDp < 560f -> 0.72f
            heightDp < 700f -> 0.82f
            heightDp < 850f -> 0.90f
            else -> 1f
        }
        statusPanel.setPadding(dp((24 * scale).roundToInt()), dp((20 * scale).roundToInt()), dp((24 * scale).roundToInt()), dp((22 * scale).roundToInt()))
        brandLogo.layoutParams = brandLogo.layoutParams.apply {
            width = (panelWidthPx * 0.55f).roundToInt()
            height = dp((84 * scale).roundToInt())
        }
        codeText.setTextSize(TypedValue.COMPLEX_UNIT_SP, 48f * scale)
        findViewById<TextView>(R.id.subtitleText).setTextSize(TypedValue.COMPLEX_UNIT_SP, 17f * scale)
        findViewById<TextView>(R.id.codeLabel).setTextSize(TypedValue.COMPLEX_UNIT_SP, 16f * scale)
        statusText.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14.5f * scale)
    }

    private fun wifiQualityLabel(rssi: Int): String = when {
        rssi >= -50 -> "Excelente"
        rssi >= -60 -> "Muito bom"
        rssi >= -67 -> "Bom"
        rssi >= -75 -> "Fraco"
        else -> "Ruim"
    }
    private fun wifiColor(rssi: Int): Int = when {
        rssi >= -67 -> Color.parseColor("#35D38A")
        rssi >= -75 -> Color.parseColor("#FFC857")
        else -> Color.parseColor("#FF6B6B")
    }
    private fun wifiBars(rssi: Int): String = when {
        rssi >= -50 -> "▂▄▆█"
        rssi >= -60 -> "▂▄▆"
        rssi >= -67 -> "▂▄"
        rssi >= -75 -> "▂"
        else -> "·"
    }

    private fun updateNetworkPanel() {
        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val caps = cm.getNetworkCapabilities(cm.activeNetwork)
        when {
            caps?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true -> {
                val wm = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
                val info = wm.connectionInfo
                val ssid = (info.ssid ?: "").trim('"').takeIf { it.isNotBlank() && it != "<unknown ssid>" } ?: "Wi‑Fi"
                val rssi = info.rssi.takeIf { it > -127 } ?: -100
                wifiNetworkText.text = ssid
                wifiSignalText.text = "$rssi dBm"
                wifiQualityText.text = wifiQualityLabel(rssi)
                wifiQualityText.setTextColor(wifiColor(rssi))
                wifiBarsText.text = wifiBars(rssi)
                wifiBarsText.setTextColor(wifiColor(rssi))
            }
            caps?.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) == true -> {
                wifiNetworkText.text = "Ethernet"
                wifiSignalText.text = localIpAddress().ifBlank { "Cabo" }
                wifiQualityText.text = "Conectado"
                wifiQualityText.setTextColor(Color.parseColor("#35D38A"))
                wifiBarsText.text = "▂▄▆█"
                wifiBarsText.setTextColor(Color.parseColor("#35D38A"))
            }
            else -> {
                wifiNetworkText.text = "Sem rede"
                wifiSignalText.text = "—"
                wifiQualityText.text = "Desconectado"
                wifiQualityText.setTextColor(Color.parseColor("#FF6B6B"))
                wifiBarsText.text = "·"
                wifiBarsText.setTextColor(Color.parseColor("#FF6B6B"))
            }
        }
        wifiPanel.visibility = View.VISIBLE
    }

    private fun startNetworkUiLoop() {
        networkUiJob?.cancel()
        networkUiJob = scope.launch {
            while (isActive) {
                runCatching { updateNetworkPanel() }
                delay(3000)
            }
        }
    }

'''
marker = '    private fun showPairingState(message: String) {'
if marker not in s:
    raise SystemExit('showPairingState não encontrado')
s = s.replace(marker, helpers + marker, 1)

hb = '''            .put("wifiLinkSpeed", wifiLinkSpeed)
            .put("playbackError", lastPlaybackError)'''
hb2 = '''            .put("wifiLinkSpeed", wifiLinkSpeed)
            .put("syncDriftMs", lastSyncDriftMs)
            .put("syncRttMs", lastSyncRttMs)
            .put("serverClockOffsetMs", serverClockOffsetMs)
            .put("syncQuality", when (abs(lastSyncDriftMs)) {
                in 0L..80L -> "excellent"
                in 81L..250L -> "adjusting"
                else -> "resync"
            })
            .put("playbackError", lastPlaybackError)'''
if hb not in s:
    raise SystemExit('heartbeat Wi-Fi não encontrado')
s = s.replace(hb, hb2, 1)

s = s.replace('        playbackStarted = true\n        currentIndex = index', '        playbackStarted = true\n        currentIndex = index\n        setSyncSpeed(1f)', 1)
s = s.replace('override fun onDestroy() { super.onDestroy(); imageJob?.cancel(); syncJob?.cancel(); transitionJob?.cancel(); scope.cancel(); player.release() }', 'override fun onDestroy() { super.onDestroy(); imageJob?.cancel(); syncJob?.cancel(); transitionJob?.cancel(); networkUiJob?.cancel(); scope.cancel(); player.release() }')
main.write_text(s, encoding='utf-8')

layout = Path('app/src/main/res/layout/activity_main.xml')
layout.write_text(r'''<FrameLayout xmlns:android="http://schemas.android.com/apk/res/android" xmlns:app="http://schemas.android.com/apk/res-auto" android:layout_width="match_parent" android:layout_height="match_parent" android:background="@drawable/player_screen_bg">
<androidx.media3.ui.PlayerView android:id="@+id/playerView" android:layout_width="match_parent" android:layout_height="match_parent" android:visibility="gone" app:use_controller="false" app:resize_mode="fit" />
<ImageView android:id="@+id/imageView" android:layout_width="match_parent" android:layout_height="match_parent" android:visibility="gone" android:scaleType="fitCenter" android:background="#000000" />
<LinearLayout android:id="@+id/statusPanel" android:layout_width="560dp" android:layout_height="wrap_content" android:layout_gravity="center" android:orientation="vertical" android:gravity="center_horizontal" android:padding="24dp" android:background="@drawable/status_panel_bg_0861">
<ImageView android:id="@+id/brandLogo" android:layout_width="300dp" android:layout_height="90dp" android:scaleType="fitCenter" android:contentDescription="Conecta Soluções" android:src="@drawable/tv_banner_brand" />
<TextView android:id="@+id/subtitleText" android:layout_width="wrap_content" android:layout_height="wrap_content" android:layout_marginTop="2dp" android:text="Player para Android TV" android:textColor="#DCE9F8" android:textSize="17sp" />
<TextView android:id="@+id/codeLabel" android:layout_width="wrap_content" android:layout_height="wrap_content" android:layout_marginTop="14dp" android:text="Código deste dispositivo" android:textColor="#AFC6E2" android:textSize="16sp" />
<TextView android:id="@+id/codeText" android:layout_width="wrap_content" android:layout_height="wrap_content" android:layout_marginTop="2dp" android:text="000 000" android:textColor="#FFFFFF" android:textStyle="bold" android:textSize="48sp" android:letterSpacing="0.08" />
<TextView android:id="@+id/statusText" android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="10dp" android:text="Configure o endereço do servidor." android:textColor="#D8E6F6" android:textSize="14sp" android:gravity="center" />
<EditText android:id="@+id/serverInput" android:layout_width="match_parent" android:layout_height="48dp" android:layout_marginTop="14dp" android:hint="IP do computador. Ex.: 192.168.1.50" android:singleLine="true" android:inputType="textUri" android:textColor="#FFFFFF" android:textColorHint="#829AB7" android:background="@drawable/server_input_bg_0861" android:paddingLeft="16dp" android:paddingRight="16dp" android:textSize="14sp" />
<LinearLayout android:id="@+id/wifiPanel" android:layout_width="match_parent" android:layout_height="58dp" android:layout_marginTop="10dp" android:orientation="horizontal" android:gravity="center_vertical" android:paddingLeft="14dp" android:paddingRight="14dp" android:background="@drawable/network_panel_bg_087">
<TextView android:id="@+id/wifiBarsText" android:layout_width="58dp" android:layout_height="wrap_content" android:text="▂▄▆█" android:textColor="#35D38A" android:textSize="19sp" android:gravity="center" />
<LinearLayout android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:orientation="vertical"><TextView android:layout_width="wrap_content" android:layout_height="wrap_content" android:text="Wi‑Fi" android:textColor="#8FA9C8" android:textSize="10sp" /><TextView android:id="@+id/wifiNetworkText" android:layout_width="match_parent" android:layout_height="wrap_content" android:text="—" android:textColor="#FFFFFF" android:textStyle="bold" android:textSize="13sp" android:maxLines="1" android:ellipsize="end" /></LinearLayout>
<View android:layout_width="1dp" android:layout_height="32dp" android:layout_marginLeft="10dp" android:layout_marginRight="10dp" android:background="#355270" />
<LinearLayout android:layout_width="82dp" android:layout_height="wrap_content" android:orientation="vertical"><TextView android:layout_width="wrap_content" android:layout_height="wrap_content" android:text="Sinal" android:textColor="#8FA9C8" android:textSize="10sp" /><TextView android:id="@+id/wifiSignalText" android:layout_width="wrap_content" android:layout_height="wrap_content" android:text="—" android:textColor="#FFFFFF" android:textStyle="bold" android:textSize="12sp" /></LinearLayout>
<View android:layout_width="1dp" android:layout_height="32dp" android:layout_marginLeft="8dp" android:layout_marginRight="10dp" android:background="#355270" />
<LinearLayout android:layout_width="100dp" android:layout_height="wrap_content" android:orientation="vertical"><TextView android:layout_width="wrap_content" android:layout_height="wrap_content" android:text="Qualidade" android:textColor="#8FA9C8" android:textSize="10sp" /><TextView android:id="@+id/wifiQualityText" android:layout_width="wrap_content" android:layout_height="wrap_content" android:text="—" android:textColor="#35D38A" android:textStyle="bold" android:textSize="12sp" /></LinearLayout>
</LinearLayout>
<Button android:id="@+id/saveServerButton" android:layout_width="230dp" android:layout_height="48dp" android:layout_marginTop="12dp" android:text="SALVAR E CONECTAR" android:textColor="#FFFFFF" android:textStyle="bold" android:textSize="13sp" android:background="@drawable/button_primary_0861" />
<Button android:id="@+id/settingsButton" android:layout_width="230dp" android:layout_height="48dp" android:layout_marginTop="10dp" android:text="ALTERAR SERVIDOR" android:textColor="#FFFFFF" android:textStyle="bold" android:textSize="13sp" android:background="@drawable/button_secondary_0861" android:visibility="gone" />
</LinearLayout>
<LinearLayout android:id="@+id/watermarkContainer" android:layout_width="wrap_content" android:layout_height="wrap_content" android:layout_gravity="bottom|end" android:layout_margin="24dp" android:orientation="vertical" android:gravity="center" android:visibility="gone"><ImageView android:id="@+id/watermarkLogo" android:layout_width="180dp" android:layout_height="92dp" android:scaleType="fitCenter" android:visibility="gone" /><TextView android:id="@+id/watermarkText" android:layout_width="wrap_content" android:layout_height="wrap_content" android:layout_marginTop="4dp" android:textColor="#FFFFFFFF" android:textStyle="bold" android:textSize="27sp" android:shadowColor="#CC000000" android:shadowDx="2" android:shadowDy="2" android:shadowRadius="4" android:gravity="center" android:maxLines="2" android:visibility="gone" /></LinearLayout>
<TextView android:id="@+id/offlineBadge" android:layout_width="wrap_content" android:layout_height="wrap_content" android:layout_gravity="top|end" android:layout_margin="18dp" android:paddingLeft="14dp" android:paddingRight="14dp" android:paddingTop="9dp" android:paddingBottom="9dp" android:background="#AA000000" android:text="OFFLINE • reproduzindo cache" android:textColor="#FFFFFF" android:textSize="12sp" android:visibility="gone" />
</FrameLayout>''', encoding='utf-8')

d = Path('app/src/main/res/drawable')
(d / 'network_panel_bg_087.xml').write_text('<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle"><solid android:color="#66102743"/><stroke android:width="1dp" android:color="#2A72B8"/><corners android:radius="12dp"/></shape>', encoding='utf-8')
print('0.8.7: UI responsiva, Wi-Fi local e sincronização refinada aplicadas')
