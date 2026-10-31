from pathlib import Path
import re

p=Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
s=p.read_text(encoding='utf-8')

# Executado DEPOIS do patch 0.10.6: troca o sync manual por sync automático
# entre TVs online que compartilham grupo e a mesma playlist escolhida.

def once(old,new,label):
    global s
    n=s.count(old)
    if n!=1: raise SystemExit(f'{label}: esperado 1, encontrado {n}')
    s=s.replace(old,new,1)

# O Console 0.9.2.10 não publica serverTimeMs/syncAnchorMs. Usamos o cabeçalho
# HTTP Date do próprio servidor (relógio comum), com fallback para relógio local.
once('import java.time.Instant\nimport java.util.concurrent.TimeUnit\n',
     'import java.time.Instant\nimport java.time.ZonedDateTime\nimport java.time.format.DateTimeFormatter\nimport java.util.concurrent.TimeUnit\n','clock imports')

# syncAnchorMs deixa de ser necessário: a fase da playlist é calculada pelo relógio do Console.
s=s.replace('    private var syncAnchorMs = 0L\n','',1)
s=s.replace(' && syncAnchorMs>0L','')
s=s.replace('&& syncAnchorMs>0L','')
s=s.replace('.putLong("sync_anchor_ms",syncAnchorMs)','')
s=s.replace('syncAnchorMs=prefs.getLong("sync_anchor_ms",0L);','')

# Busca /api/state e preserva também o Date HTTP do Console.
loop_re=re.compile(r'    private fun startConnectivityLoop\(\)\{.*?\n    private suspend fun applyState',re.S)
m=loop_re.search(s)
if not m: raise SystemExit('loop pós-0.10.6 não encontrado')
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

# Estado automático: mesma playlist escolhida + pelo menos um grupo em comum + peer online.
apply_re=re.compile(r'    private suspend fun applyState\(state:JSONObject\)\{.*?\n    private fun targetsTV',re.S)
m=apply_re.search(s)
if not m: raise SystemExit('applyState pós-0.10.6 não encontrado')
apply='''    private suspend fun applyState(state:JSONObject){
        val tvs=state.optJSONArray("tvs")?:JSONArray()
        val tv=(0 until tvs.length()).mapNotNull{tvs.optJSONObject(it)}.firstOrNull{it.optString("pairingCode")==pairingCode}
        pairedTv=tv
        if(tv==null){showPairingState("Console conectado. Cadastre o código acima no painel.");return}
        val playlist=choosePlaylist(state,tv)
        if(playlist==null){syncEnabled=false;showPairingState("Dispositivo pareado. Aguardando playlist...");return}
        val newPid=playlist.optString("id")
        val wasSyncEnabled=syncEnabled
        syncEnabled=autoSyncEligible(state,tv,newPid)
        prefs.edit().putBoolean("sync_enabled",syncEnabled).putLong("server_clock_offset_ms",serverClockOffsetMs).apply()
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
            if(syncEnabled)syncPlayback(true) else playItem(0,0)
        }else if(syncEnabled){
            syncPlayback(!wasSyncEnabled)
        }else if(currentIndex<0&&activeItems.isNotEmpty())playItem(0,0)
    }
    private fun autoSyncEligible(state:JSONObject,tv:JSONObject,playlistId:String):Boolean{
        if(playlistId.isBlank())return false
        val mineArr=tv.optJSONArray("groupIds")?:JSONArray()
        val mine=(0 until mineArr.length()).map{mineArr.optString(it)}.filter{it.isNotBlank()}.toSet()
        if(mine.isEmpty())return false
        val offlineSec=(state.optJSONObject("settings")?.optLong("offlineAfterSeconds",45L)?:45L).coerceAtLeast(10L)
        val now=System.currentTimeMillis()
        val tvs=state.optJSONArray("tvs")?:JSONArray()
        return (0 until tvs.length()).mapNotNull{tvs.optJSONObject(it)}.any{peer->
            if(peer.optString("id")==tv.optString("id"))false else {
                val seen=runCatching{Instant.parse(peer.optString("lastSeen")).toEpochMilli()}.getOrDefault(0L)
                val online=seen>0L && now-seen<offlineSec*1000L
                val pg=peer.optJSONArray("groupIds")?:JSONArray()
                val sameGroup=(0 until pg.length()).any{pg.optString(it) in mine}
                val peerPid=peer.optString("currentPlaylistId").ifBlank{choosePlaylist(state,peer)?.optString("id").orEmpty()}
                online && sameGroup && peerPid==playlistId
            }
        }
    }
    private fun targetsTV'''
s=s[:m.start()]+apply+s[m.end():]

# Fase global: tempo do servidor módulo duração total da playlist.
timeline_re=re.compile(r'    private fun timelinePosition\(\):Pair<Int,Long>\{.*?\n    \}',re.S)
m=timeline_re.search(s)
if not m: raise SystemExit('timelinePosition não encontrado')
timeline='''    private fun timelinePosition():Pair<Int,Long>{
        val total=activeItems.sumOf{it.durationMs}.coerceAtLeast(1L)
        val now=synchronizedNowMs()
        val elapsed=((now%total)+total)%total
        var cursor=0L
        activeItems.forEachIndexed{index,item->
            if(elapsed<cursor+item.durationMs)return index to (elapsed-cursor)
            cursor+=item.durationMs
        }
        return 0 to 0L
    }'''
s=s[:m.start()]+timeline+s[m.end():]

# Remove qualquer guarda residual de âncora.
s=s.replace('||syncAnchorMs<=0L','')
s=s.replace('&& syncAnchorMs>0L','')

# Estado + relógio HTTP; Date tem resolução de 1 s, então +500 ms centra o erro de quantização.
marker='    private fun getJson(url:String):JSONObject'
if s.count(marker)!=1: raise SystemExit('getJson não encontrado')
clock='''    private fun getStateWithClock(url:String):Pair<JSONObject,Long>{
        client.newCall(Request.Builder().url(url).build()).execute().use{r->
            val txt=r.body?.string()?:"{}"
            if(!r.isSuccessful)error("HTTP ${r.code}")
            val serverMs=runCatching{ZonedDateTime.parse(r.header("Date"),DateTimeFormatter.RFC_1123_DATE_TIME).toInstant().toEpochMilli()+500L}.getOrDefault(System.currentTimeMillis())
            return JSONObject(txt) to serverMs
        }
    }
'''
s=s.replace(marker,clock+marker,1)

# Versão nova.
g=Path('app/build.gradle.kts')
gs=g.read_text(encoding='utf-8')
if 'versionCode = 36' not in gs or 'versionName = "0.10.6"' not in gs: raise SystemExit('build.gradle não está na 0.10.6 esperada')
g.write_text(gs.replace('versionCode = 36','versionCode = 37').replace('versionName = "0.10.6"','versionName = "0.10.7"'),encoding='utf-8')

required=['autoSyncEligible','getStateWithClock','DateTimeFormatter.RFC_1123_DATE_TIME','currentPlaylistId','groupIds','syncEnabled','syncDriftMs','syncRttMs','serverClockOffsetMs',':8799','/api/state','/api/tvs']
for x in required:
    if x not in s: raise SystemExit('ausente: '+x)
for x in ['__conecta_sync__','serverTimeMs','syncAnchorMs','/api/player/config','/api/player/heartbeat','/api/player/proof']:
    if x in s: raise SystemExit('resíduo proibido: '+x)
p.write_text(s,encoding='utf-8')
print('OK 0.10.7: auto-sync por grupo+playlist usando relógio HTTP do Console.')
