from pathlib import Path
import re

p=Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
s=p.read_text(encoding='utf-8')

# Executado após 0.10.9.
# Restaura o contrato histórico aceito pelo Console: PUT /api/tvs com o objeto completo
# da TV, preservando o ID persistente. Falha de heartbeat não deve marcar o Console offline.

# 1) separa conectividade GET /api/state de falha de heartbeat
loop_re=re.compile(r'    private fun startConnectivityLoop\(\)\{.*?\n    private suspend fun applyState',re.S)
m=loop_re.search(s)
if not m:
    raise SystemExit('startConnectivityLoop pós-0.10.9 não encontrado')
loop='''    private fun startConnectivityLoop(){
        connectivityJob?.cancel()
        connectivityJob=scope.launch{
            while(isActive){
                updateNetworkInfo()
                try{
                    val wallStart=System.currentTimeMillis()
                    val monoStart=SystemClock.elapsedRealtime()
                    val snap=withContext(Dispatchers.IO){getStateWithClock("$serverUrl/api/state")}
                    val rtt=(SystemClock.elapsedRealtime()-monoStart).coerceAtLeast(0L)
                    val localMidpoint=wallStart+(rtt/2L)
                    val measuredOffset=snap.second-localMidpoint
                    serverClockOffsetMs=if(serverClockOffsetMs==0L)measuredOffset else ((serverClockOffsetMs*3L)+measuredOffset)/4L
                    lastSyncRttMs=rtt
                    offlineBadge.visibility=View.GONE
                    applyState(snap.first)
                    // Heartbeat é independente: rejeição do PUT não significa perda de conexão com o Console.
                    withContext(Dispatchers.IO){postHeartbeat()}
                }catch(_:Exception){
                    if(activeItems.isNotEmpty()){
                        offlineBadge.visibility=View.VISIBLE
                        if(syncEnabled)syncPlayback(false)
                    }else showPairingState("Sem conexão com o Console em ${serverUrl.removePrefix("http://")}")
                }
                delay(5000)
            }
        }
    }

    private suspend fun applyState'''
s=s[:m.start()]+loop+s[m.end():]

# 2) restaura objeto completo da TV no PUT, como nas versões funcionais 0.9.3/0.10.6.
hb_re=re.compile(r'    private fun postHeartbeat\(\)\{.*?\n    private fun getStateWithClock',re.S)
m=hb_re.search(s)
if not m:
    raise SystemExit('postHeartbeat pós-0.10.9 não encontrado')
hb='''    private fun postHeartbeat():Boolean{
        val tv=pairedTv?:return false
        val stableId=pairedTvId.ifBlank{tv.optString("id")}
        if(stableId.isBlank())return false
        val n=networkInfo()
        val dm=resources.displayMetrics
        val stat=StatFs(filesDir.absolutePath)
        val freeMb=stat.availableBytes/1024L/1024L
        val body=JSONObject(tv.toString())
            .put("id",stableId)
            .put("pairingCode",tv.optString("pairingCode",pairingCode))
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
        return runCatching{
            client.newCall(req).execute().use{r->r.isSuccessful}
        }.getOrDefault(false)
    }
    private fun getStateWithClock'''
s=s[:m.start()]+hb+s[m.end():]

# remove campo diagnóstico extra introduzido na 0.10.9 se restou em algum ponto
s=s.replace('.put("playerInstanceId",stableId+":"+pairingCode)\n','')

# versão
g=Path('app/build.gradle.kts')
gs=g.read_text(encoding='utf-8')
if 'versionCode = 39' not in gs or 'versionName = "0.10.9"' not in gs:
    raise SystemExit('build.gradle não está na 0.10.9 esperada')
g.write_text(gs.replace('versionCode = 39','versionCode = 40').replace('versionName = "0.10.9"','versionName = "0.10.10"'),encoding='utf-8')

required=[
    'val body=JSONObject(tv.toString())','.put("id",stableId)',
    'Instant.ofEpochMilli(synchronizedNowMs()).toString()',
    'private fun postHeartbeat():Boolean','r.isSuccessful',
    'pairedTvId','paired_tv_id','autoSyncEligible',
    '/api/state','/api/tvs',':8799','syncDriftMs','syncRttMs','serverClockOffsetMs'
]
for x in required:
    if x not in s: raise SystemExit('ausente: '+x)
for x in ['playerInstanceId','error("heartbeat HTTP']:
    if x in s: raise SystemExit('resíduo proibido: '+x)

p.write_text(s,encoding='utf-8')
print('OK 0.10.10: contrato histórico de heartbeat restaurado; falha PUT não derruba conectividade.')
