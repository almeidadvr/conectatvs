from pathlib import Path
import re

p=Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
s=p.read_text(encoding='utf-8')

# Este patch roda depois dos patches 0.10.6 + 0.10.7.
# Corrige heartbeat para múltiplas TVs:
# - não reenvia JSONObject(tv.toString()) inteiro/stale;
# - envia apenas campos de configuração aceitos pelo mesmo PUT usado pelo Console;
# - lastSeen usa o relógio sincronizado do Console.

hb_re=re.compile(r'    private fun postHeartbeat\(\)\{.*?\n    private fun getStateWithClock', re.S)
m=hb_re.search(s)
if not m:
    raise SystemExit('postHeartbeat pós-0.10.7 não encontrado')

new_hb='''    private fun postHeartbeat(){
        val tv=pairedTv?:return
        val n=networkInfo()
        val dm=resources.displayMetrics
        val stat=StatFs(filesDir.absolutePath)
        val freeMb=stat.availableBytes/1024L/1024L
        val groups=tv.optJSONArray("groupIds")?:JSONArray()
        val body=JSONObject()
            .put("id",tv.optString("id"))
            .put("name",tv.optString("name","TV"))
            .put("pairingCode",tv.optString("pairingCode",pairingCode))
            .put("playlistId",tv.optString("playlistId"))
            .put("groupIds",groups)
            .put("lastSeen",Instant.ofEpochMilli(synchronizedNowMs()).toString())
            .put("wifiSsid",n.ssid)
            .put("wifiRssi",n.rssi)
            .put("wifiFrequency",n.frequency)
            .put("connectionType",if(n.wifi)"Wi-Fi" else "Rede")
            .put("ipAddress",n.ip)
            .put("localIp",n.ip)
            .put("currentPlaylistId",currentPlaylistId)
            .put("currentMediaId",activeItems.getOrNull(currentIndex)?.id?:"")
            .put("playSequence",playSequence)
            .put("totalItems",activeItems.size)
            .put("downloadedItems",activeItems.count{File(it.localPath).exists()})
            .put("manufacturer",Build.MANUFACTURER)
            .put("model",Build.MODEL)
            .put("androidVersion",Build.VERSION.RELEASE)
            .put("sdkInt",Build.VERSION.SDK_INT)
            .put("appVersion",BuildConfig.VERSION_NAME)
            .put("screenWidth",dm.widthPixels)
            .put("screenHeight",dm.heightPixels)
            .put("storageFreeMB",freeMb)
            .put("syncEnabled",syncEnabled)
            .put("syncDriftMs",currentSyncDriftMs())
            .put("syncRttMs",lastSyncRttMs)
            .put("serverClockOffsetMs",serverClockOffsetMs)
        val req=Request.Builder().url("$serverUrl/api/tvs").put(body.toString().toRequestBody("application/json".toMediaType())).build()
        runCatching{
            client.newCall(req).execute().use{r->if(!r.isSuccessful)error("heartbeat HTTP ${r.code}")}
        }
    }
    private fun getStateWithClock'''

s=s[:m.start()]+new_hb+s[m.end():]

# versão
g=Path('app/build.gradle.kts')
gs=g.read_text(encoding='utf-8')
if 'versionCode = 37' not in gs or 'versionName = "0.10.7"' not in gs:
    raise SystemExit('build.gradle não está na 0.10.7 esperada')
gs=gs.replace('versionCode = 37','versionCode = 38').replace('versionName = "0.10.7"','versionName = "0.10.8"')
g.write_text(gs,encoding='utf-8')

required=[
    'JSONObject()','Instant.ofEpochMilli(synchronizedNowMs()).toString()',
    '.put("id",tv.optString("id"))','.put("pairingCode",tv.optString("pairingCode",pairingCode))',
    '.put("playlistId",tv.optString("playlistId"))','.put("groupIds",groups)',
    'currentPlaylistId','currentMediaId','syncDriftMs','syncRttMs','serverClockOffsetMs',
    '/api/tvs','autoSyncEligible','getStateWithClock',':8799'
]
for x in required:
    if x not in s: raise SystemExit('ausente: '+x)
if 'JSONObject(tv.toString())' in s:
    raise SystemExit('heartbeat ainda clona objeto completo da TV')

p.write_text(s,encoding='utf-8')
print('OK 0.10.8: heartbeat normalizado e lastSeen baseado no relógio do Console.')
