from pathlib import Path
import re

p = Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
s = p.read_text(encoding='utf-8')
original = s

# 0.10.6: logo fixa + sincronização opcional por TV.
# Este patch é deliberadamente restritivo: aborta se a base funcional esperada mudar.

def once(old, new, label):
    global s
    count = s.count(old)
    if count != 1:
        raise SystemExit(f'{label}: esperado 1 ocorrência, encontrado {count}')
    s = s.replace(old, new, 1)

# Imports: elimina Base64 dinâmico e recupera relógio monotônico/abs da implementação sincronizada já testada.
once('import android.os.StatFs\nimport android.util.Base64\n', 'import android.os.StatFs\nimport android.os.SystemClock\n', 'imports logo/clock')
once('import java.util.concurrent.TimeUnit\nimport kotlin.random.Random\n', 'import java.util.concurrent.TimeUnit\nimport kotlin.math.abs\nimport kotlin.random.Random\n', 'import abs')

# Estado de sincronização isolado; modo padrão continua desligado.
once('''    private var imageJob: Job? = null
    private var connectivityJob: Job? = null
    private var pairedTv: JSONObject? = null
    private var currentPlaylistId = ""
    private var playSequence = 0L
''','''    private var imageJob: Job? = null
    private var connectivityJob: Job? = null
    private var syncJob: Job? = null
    private var pairedTv: JSONObject? = null
    private var currentPlaylistId = ""
    private var playSequence = 0L
    private var syncEnabled = false
    private var syncAnchorMs = 0L
    private var serverClockOffsetMs = 0L
    private var lastSyncRttMs = 0L
    private var playbackStarted = false
''','sync vars')

# Quando a mídia termina, TVs sincronizadas voltam à posição global; TVs normais mantêm playNext original.
once('player.addListener(object:Player.Listener{ override fun onPlaybackStateChanged(state:Int){ if(state==Player.STATE_ENDED) playNext() } })',
     'player.addListener(object:Player.Listener{ override fun onPlaybackStateChanged(state:Int){ if(state==Player.STATE_ENDED){ if(syncEnabled) syncPlayback(true) else playNext() } } })',
     'listener')

# Inicia verificação local de drift; cache mantém o último estado de sync para reinício offline.
once('''        updateNetworkInfo(); loadCachedPlaylist()
        if(serverUrl.isBlank()) showServerSettings() else { if(activeItems.isNotEmpty()) playItem(0,0) else showPairingState("Conectando ao Console..."); startConnectivityLoop() }
''','''        updateNetworkInfo(); loadCachedPlaylist(); startLocalSyncLoop()
        if(serverUrl.isBlank()) showServerSettings() else { if(activeItems.isNotEmpty()){ if(syncEnabled && syncAnchorMs>0L) syncPlayback(true) else playItem(0,0) } else showPairingState("Conectando ao Console..."); startConnectivityLoop() }
''','startup')

# Logo definitiva: usa somente o drawable estático; nunca esconde o ImageView.
old_logo = re.compile(r'    private fun loadOfficialLogo\(\)\{.*?\}\n    private fun enterImmersive', re.S)
m = old_logo.search(s)
if not m:
    raise SystemExit('loadOfficialLogo não encontrado')
replacement = '''    private fun loadOfficialLogo(){ brandLogo.setImageResource(R.drawable.logo_conecta_transparente); brandLogo.visibility=View.VISIBLE }
    private fun enterImmersive'''
s = s[:m.start()] + replacement + s[m.end():]

# Loop de conectividade funcional 8799 + /api/state permanece, agora medindo RTT/offset sem trocar protocolo.
old_loop = re.compile(r'    private fun startConnectivityLoop\(\)\{.*?\}\n\n    private suspend fun applyState', re.S)
m = old_loop.search(s)
if not m:
    raise SystemExit('startConnectivityLoop não encontrado')
new_loop = '''    private fun startConnectivityLoop(){
        connectivityJob?.cancel()
        connectivityJob=scope.launch{
            while(isActive){
                updateNetworkInfo()
                try{
                    val wallStart=System.currentTimeMillis()
                    val monoStart=SystemClock.elapsedRealtime()
                    val state=withContext(Dispatchers.IO){getJson("$serverUrl/api/state")}
                    val rtt=(SystemClock.elapsedRealtime()-monoStart).coerceAtLeast(0L)
                    val localMidpoint=wallStart+(rtt/2L)
                    val serverTime=state.optLong("serverTimeMs",localMidpoint)
                    val measuredOffset=serverTime-localMidpoint
                    serverClockOffsetMs=if(serverClockOffsetMs==0L)measuredOffset else ((serverClockOffsetMs*3L)+measuredOffset)/4L
                    lastSyncRttMs=rtt
                    val anchor=state.optLong("syncAnchorMs",0L)
                    if(anchor>0L)syncAnchorMs=anchor
                    offlineBadge.visibility=View.GONE
                    applyState(state)
                    withContext(Dispatchers.IO){postHeartbeat()}
                }catch(_:Exception){
                    if(activeItems.isNotEmpty()){
                        offlineBadge.visibility=View.VISIBLE
                        if(syncEnabled && syncAnchorMs>0L)syncPlayback(false)
                    }else showPairingState("Sem conexão com o Console em ${serverUrl.removePrefix("http://")}")
                }
                delay(5000)
            }
        }
    }

    private suspend fun applyState'''
s = s[:m.start()] + new_loop + s[m.end():]

# Aplica sync individual por TV. Sentinela em groupIds evita alterar o schema do backend atual;
# também aceita syncEnabled boolean para compatibilidade futura.
old_apply = re.compile(r'    private suspend fun applyState\(state:JSONObject\)\{.*?\}\n    private fun targetsTV', re.S)
m = old_apply.search(s)
if not m:
    raise SystemExit('applyState não encontrado')
new_apply = '''    private suspend fun applyState(state:JSONObject){
        val tvs=state.optJSONArray("tvs")?:JSONArray()
        val tv=(0 until tvs.length()).mapNotNull{tvs.optJSONObject(it)}.firstOrNull{it.optString("pairingCode")==pairingCode}
        pairedTv=tv
        if(tv==null){showPairingState("Console conectado. Cadastre o código acima no painel.");return}
        val wasSyncEnabled=syncEnabled
        syncEnabled=tvSyncEnabled(tv)
        prefs.edit().putBoolean("sync_enabled",syncEnabled).putLong("sync_anchor_ms",syncAnchorMs).putLong("server_clock_offset_ms",serverClockOffsetMs).apply()
        val playlist=choosePlaylist(state,tv)
        if(playlist==null){showPairingState("Dispositivo pareado. Aguardando playlist...");return}
        val newPid=playlist.optString("id")
        val normalized=normalizePlaylist(state,playlist)
        val signature=normalized.toString().hashCode().toString()
        val changedPlaylist=newPid!=currentPlaylistId
        currentPlaylistId=newPid
        val changedContent=prefs.getString("playlist_signature","")!=signature
        if(changedPlaylist||changedContent||activeItems.isEmpty()){
            val parsed=withContext(Dispatchers.IO){cachePlaylist(normalized)}
            if(parsed.isEmpty()){showPairingState("Playlist sem mídia compatível.");return}
            activeItems=parsed.toMutableList()
            prefs.edit().putString("cached_playlist",normalized.toString()).putString("playlist_signature",signature).apply()
            if(syncEnabled && syncAnchorMs>0L)syncPlayback(true) else playItem(0,0)
        }else if(syncEnabled){
            syncPlayback(!wasSyncEnabled)
        }else if(currentIndex<0&&activeItems.isNotEmpty())playItem(0,0)
    }
    private fun tvSyncEnabled(tv:JSONObject):Boolean{
        if(tv.has("syncEnabled"))return tv.optBoolean("syncEnabled",false)
        val groups=tv.optJSONArray("groupIds")?:JSONArray()
        return (0 until groups.length()).any{groups.optString(it)=="__conecta_sync__"}
    }
    private fun targetsTV'''
s = s[:m.start()] + new_apply + s[m.end():]

# Recupera a lógica de sincronização refinada usada no histórico 0.8.7/0.9.2.
marker = '    private fun playItem(index:Int,offset:Long)'
if s.count(marker) != 1:
    raise SystemExit('playItem não encontrado')
sync_code = '''    private fun startLocalSyncLoop(){
        syncJob?.cancel()
        syncJob=scope.launch{
            while(isActive){
                delay(1000)
                if(syncEnabled && playbackStarted && activeItems.isNotEmpty() && syncAnchorMs>0L)syncPlayback(false)
            }
        }
    }
    private fun synchronizedNowMs():Long=System.currentTimeMillis()+serverClockOffsetMs
    private fun timelinePosition():Pair<Int,Long>{
        val total=activeItems.sumOf{it.durationMs}.coerceAtLeast(1L)
        val elapsed=((synchronizedNowMs()-syncAnchorMs)%total+total)%total
        var cursor=0L
        activeItems.forEachIndexed{index,item->
            if(elapsed<cursor+item.durationMs)return index to (elapsed-cursor)
            cursor+=item.durationMs
        }
        return 0 to 0L
    }
    private fun syncPlayback(force:Boolean){
        if(!syncEnabled||activeItems.isEmpty()||syncAnchorMs<=0L)return
        val(targetIndex,targetOffset)=timelinePosition()
        val target=activeItems[targetIndex]
        val sameItem=currentIndex==targetIndex&&playbackStarted
        if(!force&&sameItem){
            if(target.kind=="video"&&player.playbackState!=Player.STATE_IDLE){
                val drift=abs(player.currentPosition-targetOffset)
                if(drift>650L)player.seekTo(targetOffset.coerceAtMost((target.durationMs-200L).coerceAtLeast(0L)))
            }
            return
        }
        playItem(targetIndex,targetOffset)
    }
    private fun currentSyncDriftMs():Long{
        if(!syncEnabled||activeItems.isEmpty()||syncAnchorMs<=0L||currentIndex<0)return 0L
        val(targetIndex,targetOffset)=timelinePosition()
        if(targetIndex!=currentIndex)return activeItems.getOrNull(currentIndex)?.durationMs?:0L
        val item=activeItems[currentIndex]
        return if(item.kind=="video")player.currentPosition-targetOffset else 0L
    }

'''
s = s.replace(marker, sync_code + marker, 1)

# playItem mantém comportamento original quando sync OFF e respeita offset/restante quando ON.
once('''    private fun playItem(index:Int,offset:Long){if(activeItems.isEmpty())return;currentIndex=index%activeItems.size;playSequence++;val item=activeItems[currentIndex];statusPanel.visibility=View.GONE;settingsButton.visibility=View.GONE;imageJob?.cancel();player.stop();if(item.kind=="video"){imageView.visibility=View.GONE;playerView.visibility=View.VISIBLE;player.setMediaItem(MediaItem.fromUri(Uri.fromFile(File(item.localPath))));player.prepare();player.seekTo(offset.coerceAtLeast(0));player.playWhenReady=true}else{playerView.visibility=View.GONE;imageView.visibility=View.VISIBLE;imageView.setImageBitmap(BitmapFactory.decodeFile(item.localPath));imageJob=scope.launch{delay(item.durationMs);playNext()}}}
    private fun playNext(){if(activeItems.isNotEmpty())playItem((currentIndex+1)%activeItems.size,0)}
''','''    private fun playItem(index:Int,offset:Long){if(activeItems.isEmpty())return;playbackStarted=true;currentIndex=index%activeItems.size;playSequence++;val item=activeItems[currentIndex];statusPanel.visibility=View.GONE;settingsButton.visibility=View.GONE;imageJob?.cancel();player.stop();if(item.kind=="video"){imageView.visibility=View.GONE;playerView.visibility=View.VISIBLE;player.setMediaItem(MediaItem.fromUri(Uri.fromFile(File(item.localPath))));player.prepare();player.seekTo(offset.coerceIn(0L,(item.durationMs-200L).coerceAtLeast(0L)));player.playWhenReady=true}else{playerView.visibility=View.GONE;imageView.visibility=View.VISIBLE;imageView.setImageBitmap(BitmapFactory.decodeFile(item.localPath));imageJob=scope.launch{delay(if(syncEnabled)(item.durationMs-offset).coerceAtLeast(100L) else item.durationMs);if(syncEnabled)syncPlayback(true)else playNext()}}}
    private fun playNext(){if(activeItems.isNotEmpty()){if(syncEnabled)syncPlayback(true)else playItem((currentIndex+1)%activeItems.size,0)}}
''','playback')

# Ao abrir telas de configuração, marca reprodução como parada para o loop não tentar corrigir por trás.
s = s.replace('private fun showPairingState(message:String){player.stop();', 'private fun showPairingState(message:String){playbackStarted=false;player.stop();', 1)
s = s.replace('private fun showServerSettings(){player.pause();', 'private fun showServerSettings(){playbackStarted=false;player.pause();', 1)

# Restaura estado de sincronização junto do cache existente.
once('''    private fun loadCachedPlaylist(){val raw=prefs.getString("cached_playlist",null)?:return;runCatching{''',
     '''    private fun loadCachedPlaylist(){syncEnabled=prefs.getBoolean("sync_enabled",false);syncAnchorMs=prefs.getLong("sync_anchor_ms",0L);serverClockOffsetMs=prefs.getLong("server_clock_offset_ms",0L);val raw=prefs.getString("cached_playlist",null)?:return;runCatching{''',
     'cache sync state')

# Telemetria existente intacta + métricas de sincronização que o Console 0.9.2 já sabe exibir.
old_hb = re.compile(r'    private fun postHeartbeat\(\)\{.*?\}\n    private fun getJson', re.S)
m = old_hb.search(s)
if not m:
    raise SystemExit('postHeartbeat não encontrado')
hb = '''    private fun postHeartbeat(){val tv=pairedTv?:return;val n=networkInfo();val dm=resources.displayMetrics;val stat=StatFs(filesDir.absolutePath);val freeMb=stat.availableBytes/1024L/1024L;val body=JSONObject(tv.toString()).put("lastSeen",Instant.now().toString()).put("wifiSsid",n.ssid).put("wifiRssi",n.rssi).put("wifiFrequency",n.frequency).put("connectionType",if(n.wifi)"Wi-Fi" else "Rede").put("ipAddress",n.ip).put("localIp",n.ip).put("currentPlaylistId",currentPlaylistId).put("currentMediaId",activeItems.getOrNull(currentIndex)?.id?:"").put("playSequence",playSequence).put("totalItems",activeItems.size).put("downloadedItems",activeItems.count{File(it.localPath).exists()}).put("manufacturer",Build.MANUFACTURER).put("model",Build.MODEL).put("androidVersion",Build.VERSION.RELEASE).put("sdkInt",Build.VERSION.SDK_INT).put("appVersion",BuildConfig.VERSION_NAME).put("screenWidth",dm.widthPixels).put("screenHeight",dm.heightPixels).put("storageFreeMB",freeMb).put("syncEnabled",syncEnabled).put("syncDriftMs",currentSyncDriftMs()).put("syncRttMs",lastSyncRttMs).put("serverClockOffsetMs",serverClockOffsetMs);val req=Request.Builder().url("$serverUrl/api/tvs").put(body.toString().toRequestBody("application/json".toMediaType())).build();runCatching{client.newCall(req).execute().close()}}
    private fun getJson'''
s = s[:m.start()] + hb + s[m.end():]

# Cleanup do novo job sem alterar os demais recursos.
once('override fun onDestroy(){connectivityJob?.cancel();imageJob?.cancel();scope.cancel();player.release();super.onDestroy()}',
     'override fun onDestroy(){connectivityJob?.cancel();syncJob?.cancel();imageJob?.cancel();scope.cancel();player.release();super.onDestroy()}',
     'destroy')

# Guard rails finais.
required = [
    ':8799','/api/state','/api/tvs','playSequence','currentMediaId','currentPlaylistId',
    'syncAnchorMs','serverTimeMs','syncPlayback','__conecta_sync__',
    'setImageResource(R.drawable.logo_conecta_transparente)','brandLogo.visibility=View.VISIBLE'
]
for token in required:
    if token not in s: raise SystemExit(f'validação final ausente: {token}')
for forbidden in ['R.raw.logo_conecta_base64','Base64.decode','brandLogo.visibility=View.GONE','/api/player/config','/api/player/heartbeat','/api/player/proof']:
    if forbidden in s: raise SystemExit(f'validação final proibida: {forbidden}')
if s == original:
    raise SystemExit('nenhuma mudança aplicada')

p.write_text(s, encoding='utf-8')
print('OK 0.10.6: logo estática + sincronização opcional por TV aplicadas sobre a base funcional.')
