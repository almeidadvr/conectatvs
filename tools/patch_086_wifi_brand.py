from pathlib import Path

main = Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
s = main.read_text(encoding='utf-8')

s = s.replace(
    'import android.net.Uri\nimport android.os.Bundle',
    'import android.net.Uri\nimport android.net.ConnectivityManager\nimport android.net.NetworkCapabilities\nimport android.net.wifi.WifiManager\nimport android.content.Context\nimport android.os.Bundle'
)

needle = '''        val payload = JSONObject()\n            .put("pairingCode", pairingCode)'''
replacement = '''        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager\n        val caps = cm.getNetworkCapabilities(cm.activeNetwork)\n        val connectionType = when {\n            caps?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true -> "Wi-Fi"\n            caps?.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) == true -> "Ethernet"\n            else -> "Outro"\n        }\n        val wifiManager = applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager\n        val wifiInfo = wifiManager.connectionInfo\n        val wifiActive = connectionType == "Wi-Fi"\n        val wifiSsid = if (wifiActive) (wifiInfo.ssid ?: "").trim('"').takeIf { it != "<unknown ssid>" } ?: "" else ""\n        val wifiRssi = if (wifiActive && wifiInfo.rssi > -127) wifiInfo.rssi else 0\n        val wifiFrequency = if (wifiActive) wifiInfo.frequency else 0\n        val wifiLinkSpeed = if (wifiActive) wifiInfo.linkSpeed else 0\n\n        val payload = JSONObject()\n            .put("pairingCode", pairingCode)'''
if needle not in s:
    raise SystemExit('Heartbeat payload não encontrado')
s = s.replace(needle, replacement, 1)

needle2 = '''            .put("currentPlaylistId", currentPlaylistId)\n            .put("playbackError", lastPlaybackError)'''
replacement2 = '''            .put("currentPlaylistId", currentPlaylistId)\n            .put("connectionType", connectionType)\n            .put("wifiSsid", wifiSsid)\n            .put("wifiRssi", wifiRssi)\n            .put("wifiFrequency", wifiFrequency)\n            .put("wifiLinkSpeed", wifiLinkSpeed)\n            .put("playbackError", lastPlaybackError)'''
if needle2 not in s:
    raise SystemExit('Ponto playbackError não encontrado')
s = s.replace(needle2, replacement2, 1)
main.write_text(s, encoding='utf-8')

manifest = Path('app/src/main/AndroidManifest.xml')
x = manifest.read_text(encoding='utf-8')
if 'android.permission.ACCESS_WIFI_STATE' not in x:
    x = x.replace('<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />', '<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />\n    <uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />')
manifest.write_text(x, encoding='utf-8')

layout = Path('app/src/main/res/layout/activity_main.xml')
y = layout.read_text(encoding='utf-8')
old = '<TextView android:id="@+id/titleText" android:layout_width="wrap_content" android:layout_height="wrap_content" android:text="CONECTA MÍDIA" android:textColor="#FFFFFF" android:textStyle="bold" android:textSize="32sp" />'
new = '''<ImageView\n            android:id="@+id/brandLogo"\n            android:layout_width="400dp"\n            android:layout_height="118dp"\n            android:adjustViewBounds="true"\n            android:scaleType="fitCenter"\n            android:contentDescription="Conecta Soluções"\n            android:src="@drawable/tv_banner_brand" />'''
if old not in y:
    raise SystemExit('titleText não encontrado no layout')
y = y.replace(old, new, 1)
y = y.replace('android:text="Player de Mídia Digital"', 'android:text="Player para Android TV"')
layout.write_text(y, encoding='utf-8')

print('0.8.6: telemetria Wi-Fi e logo embutida aplicadas sem alterar conexão/sincronização')
