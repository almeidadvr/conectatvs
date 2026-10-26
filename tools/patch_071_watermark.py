from pathlib import Path

main = Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
s = main.read_text(encoding='utf-8')

s = s.replace('import android.view.KeyEvent\nimport android.view.View', 'import android.view.KeyEvent\nimport android.view.View\nimport android.view.Gravity')

s = s.replace(
'''    private lateinit var offlineBadge: TextView''',
'''    private lateinit var offlineBadge: TextView\n    private lateinit var watermarkContainer: LinearLayout\n    private lateinit var watermarkLogoView: ImageView\n    private lateinit var watermarkTextView: TextView''')

s = s.replace(
'''    private val appStartedAtMs = System.currentTimeMillis()\n    private val appStartedElapsedMs = SystemClock.elapsedRealtime()''',
'''    private val appStartedAtMs = System.currentTimeMillis()\n    private val appStartedElapsedMs = SystemClock.elapsedRealtime()\n    private var watermarkEnabled = false''')

s = s.replace(
'''        offlineBadge = findViewById(R.id.offlineBadge)''',
'''        offlineBadge = findViewById(R.id.offlineBadge)\n        watermarkContainer = findViewById(R.id.watermarkContainer)\n        watermarkLogoView = findViewById(R.id.watermarkLogo)\n        watermarkTextView = findViewById(R.id.watermarkText)''')

s = s.replace(
'''        currentPlaylistId = playlist.optString("id")\n        playlistTransition''',
'''        currentPlaylistId = playlist.optString("id")\n        applyWatermarkState(playlist)\n        refreshWatermarkLogo(playlist)\n        playlistTransition''')

s = s.replace(
'''            val playlist = JSONObject(raw)\n            currentPlaylistId = playlist.optString("id")''',
'''            val playlist = JSONObject(raw)\n            currentPlaylistId = playlist.optString("id")\n            applyWatermarkState(playlist)''')

insert_before = '''    private fun showPairingState(message: String) {'''
watermark_code = r'''    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private fun applyWatermarkState(playlist: JSONObject) {
        watermarkEnabled = playlist.optBoolean("watermarkEnabled", false)
        if (!watermarkEnabled) {
            watermarkContainer.visibility = View.GONE
            return
        }

        val type = playlist.optString("watermarkType", "text").lowercase()
        val text = playlist.optString("watermarkText", "")
        val position = playlist.optString("watermarkPosition", "bottom-right").lowercase()
        val opacity = playlist.optInt("watermarkOpacity", 35).coerceIn(10, 100) / 100f
        val size = playlist.optString("watermarkSize", "medium").lowercase()

        watermarkTextView.text = text
        watermarkTextView.visibility = if ((type == "text" || type == "both") && text.isNotBlank()) View.VISIBLE else View.GONE
        watermarkLogoView.visibility = if (type == "logo" || type == "both") View.VISIBLE else View.GONE
        watermarkContainer.alpha = opacity
        watermarkContainer.visibility = View.VISIBLE

        val (logoW, logoH, textSp) = when (size) {
            "small" -> Triple(dp(110), dp(58), 18f)
            "large" -> Triple(dp(260), dp(130), 38f)
            else -> Triple(dp(180), dp(92), 27f)
        }
        watermarkLogoView.layoutParams = watermarkLogoView.layoutParams.apply {
            width = logoW
            height = logoH
        }
        watermarkTextView.textSize = textSp

        val lp = watermarkContainer.layoutParams as FrameLayout.LayoutParams
        lp.gravity = when (position) {
            "top-left" -> Gravity.TOP or Gravity.START
            "top-right" -> Gravity.TOP or Gravity.END
            "bottom-left" -> Gravity.BOTTOM or Gravity.START
            "center" -> Gravity.CENTER
            else -> Gravity.BOTTOM or Gravity.END
        }
        val margin = if (position == "center") 0 else dp(24)
        lp.setMargins(margin, margin, margin, margin)
        watermarkContainer.layoutParams = lp

        if (watermarkLogoView.visibility == View.VISIBLE) {
            val logoFile = File(filesDir, "watermark_logo")
            if (logoFile.exists() && logoFile.length() > 0L) {
                watermarkLogoView.setImageBitmap(BitmapFactory.decodeFile(logoFile.absolutePath))
            }
        }
    }

    private suspend fun refreshWatermarkLogo(playlist: JSONObject) {
        if (!playlist.optBoolean("watermarkEnabled", false)) return
        val type = playlist.optString("watermarkType", "text").lowercase()
        if (type != "logo" && type != "both") return
        val url = playlist.optString("watermarkLogoUrl", "")
        if (url.isBlank()) {
            watermarkLogoView.visibility = View.GONE
            return
        }
        val logoFile = File(filesDir, "watermark_logo")
        val lastUrl = prefs.getString("watermark_logo_url", "") ?: ""
        if (!logoFile.exists() || logoFile.length() == 0L || lastUrl != url) {
            runCatching {
                withContext(Dispatchers.IO) { downloadTo(url, logoFile) }
                prefs.edit().putString("watermark_logo_url", url).apply()
            }
        }
        if (logoFile.exists() && logoFile.length() > 0L) {
            watermarkLogoView.setImageBitmap(BitmapFactory.decodeFile(logoFile.absolutePath))
            watermarkLogoView.visibility = View.VISIBLE
        }
    }

'''
if insert_before not in s:
    raise SystemExit('showPairingState não encontrado')
s = s.replace(insert_before, watermark_code + insert_before)

s = s.replace(
'''        playbackStarted = false\n        player.stop(); imageJob?.cancel()''',
'''        playbackStarted = false\n        watermarkContainer.visibility = View.GONE\n        player.stop(); imageJob?.cancel()''', 1)

# Segunda ocorrência: showServerSettings
idx = s.find('''        playbackStarted = false\n        player.pause(); imageJob?.cancel()''')
if idx < 0:
    raise SystemExit('showServerSettings não encontrado')
s = s.replace(
'''        playbackStarted = false\n        player.pause(); imageJob?.cancel()''',
'''        playbackStarted = false\n        watermarkContainer.visibility = View.GONE\n        player.pause(); imageJob?.cancel()''', 1)

main.write_text(s, encoding='utf-8')

layout = Path('app/src/main/res/layout/activity_main.xml')
x = layout.read_text(encoding='utf-8')
needle = '''    <TextView android:id="@+id/offlineBadge"'''
overlay = '''    <LinearLayout\n        android:id="@+id/watermarkContainer"\n        android:layout_width="wrap_content"\n        android:layout_height="wrap_content"\n        android:layout_gravity="bottom|end"\n        android:layout_margin="24dp"\n        android:orientation="vertical"\n        android:gravity="center"\n        android:visibility="gone">\n\n        <ImageView\n            android:id="@+id/watermarkLogo"\n            android:layout_width="180dp"\n            android:layout_height="92dp"\n            android:scaleType="fitCenter"\n            android:visibility="gone" />\n\n        <TextView\n            android:id="@+id/watermarkText"\n            android:layout_width="wrap_content"\n            android:layout_height="wrap_content"\n            android:layout_marginTop="4dp"\n            android:textColor="#FFFFFFFF"\n            android:textStyle="bold"\n            android:textSize="27sp"\n            android:shadowColor="#CC000000"\n            android:shadowDx="2"\n            android:shadowDy="2"\n            android:shadowRadius="4"\n            android:gravity="center"\n            android:maxLines="2"\n            android:visibility="gone" />\n    </LinearLayout>\n\n'''
if needle not in x:
    raise SystemExit('offlineBadge não encontrado no layout')
x = x.replace(needle, overlay + needle)
layout.write_text(x, encoding='utf-8')

print('Marca d agua 0.7.1 aplicada sem alterar conexão/sincronização')
