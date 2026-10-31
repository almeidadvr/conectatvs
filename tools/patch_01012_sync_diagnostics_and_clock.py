from pathlib import Path
import re

p=Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
s=p.read_text(encoding='utf-8')

# Executado depois da 0.10.11.
# 1) autoSyncEligible usa o relógio sincronizado do Console.
# 2) expõe diagnóstico detalhado no heartbeat para entender por que um Player não sincroniza.

# Campos de diagnóstico
old='''    private var serverClockOffsetMs = 0L
    private var lastSyncRttMs = 0L
    private var playbackStarted = false
'''
new='''    private var serverClockOffsetMs = 0L
    private var lastSyncRttMs = 0L
    private var playbackStarted = false
    private var syncEligible = false
    private var syncReason = "init"
    private var syncTargetMediaId = ""
    private var syncTargetOffsetMs = 0L
    private var syncLocalPositionMs = 0L
    private var syncError = ""
'''
if s.count(old)!=1: raise SystemExit('campos sync base não encontrados')
s=s.replace(old,new,1)

# Corrige relógio bruto na elegibilidade
old='''        val now=System.currentTimeMillis()
'''
new='''        val now=synchronizedNowMs()
'''
if s.count(old)<1: raise SystemExit('System.currentTimeMillis da elegibilidade não encontrado')
# Substitui somente o primeiro dentro de autoSyncEligible
idx=s.find('private fun autoSyncEligible')
pos=s.find(old,idx)
if pos<0: raise SystemExit('now dentro de autoSyncEligible não encontrado')
s=s[:pos]+new+s[pos+len(old):]

# Reescreve autoSyncEligible com reason detalhado e tolerância a lastSeen em ISO com offset.
pat=re.compile(r'    private fun autoSyncEligible\(state:JSONObject,tv:JSONObject,playlistId:String\):Boolean\{.*?\n    \}\n    private fun targetsTV',re.S)
m=pat.search(s)
if not m: raise SystemExit('autoSyncEligible não encontrado')
fn='''    private fun autoSyncEligible(state:JSONObject,tv:JSONObject,playlistId:String):Boolean{
        syncEligible=false
        syncReason="checking"
        if(playlistId.isBlank()){syncReason="playlist_vazia";return false}
        val mineArr=tv.optJSONArray("groupIds")?:JSONArray()
        val mine=(0 until mineArr.length()).map{mineArr.optString(it)}.filter{it.isNotBlank()}.toSet()
        if(mine.isEmpty()){syncReason="sem_grupo";return false}
        val offlineSec=(state.optJSONObject("settings")?.optLong("offlineAfterSeconds",45L)?:45L).coerceAtLeast(10L)
        val now=synchronizedNowMs()
        val tvs=state.optJSONArray("tvs")?:JSONArray()
        var peerCount=0
        var onlinePeers=0
        var sameGroupPeers=0
        var samePlaylistPeers=0
        for(i in 0 until tvs.length()){
            val peer=tvs.optJSONObject(i)?:continue
            if(peer.optString("id")==tv.optString("id"))continue
            peerCount++
            val seen=runCatching{java.time.OffsetDateTime.parse(peer.optString("lastSeen")).toInstant().toEpochMilli()}.recoverCatching{Instant.parse(peer.optString("lastSeen")).toEpochMilli()}.getOrDefault(0L)
            val online=seen>0L && kotlin.math.abs(now-seen)<offlineSec*1000L
            if(!online)continue
            onlinePeers++
            val pg=peer.optJSONArray("groupIds")?:JSONArray()
            val sameGroup=(0 until pg.length()).any{pg.optString(it) in mine}
            if(!sameGroup)continue
            sameGroupPeers++
            val peerPid=peer.optString("currentPlaylistId").ifBlank{choosePlaylist(state,peer)?.optString("id").orEmpty()}
            if(peerPid!=playlistId)continue
            samePlaylistPeers++
        }
        syncEligible=samePlaylistPeers>0
        syncReason=if(syncEligible)"eligible" else "peers=$peerCount online=$onlinePeers group=$sameGroupPeers playlist=$samePlaylistPeers"
        return syncEligible
    }
    private fun targetsTV'''
s=s[:m.start()]+fn+s[m.end():]

# Captura alvo/local/erro dentro de syncPlayback e currentSyncDriftMs
pat=re.compile(r'    private fun syncPlayback\(force:Boolean\)\{.*?\n    \}\n    private fun currentSyncDriftMs',re.S)
m=pat.search(s)
if not m: raise SystemExit('syncPlayback não encontrado')
fn='''    private fun syncPlayback(force:Boolean){
        if(!syncEnabled||activeItems.isEmpty()){syncReason=if(!syncEnabled)syncReason else "sem_itens";return}
        runCatching{
            val(targetIndex,targetOffset)=timelinePosition()
            val target=activeItems[targetIndex]
            syncTargetMediaId=target.id
            syncTargetOffsetMs=targetOffset
            syncLocalPositionMs=if(currentIndex>=0&&activeItems.getOrNull(currentIndex)?.kind=="video")player.currentPosition else 0L
            val sameItem=currentIndex==targetIndex&&playbackStarted
            if(!force&&sameItem){
                if(target.kind=="video"&&player.playbackState!=Player.STATE_IDLE){
                    val drift=abs(player.currentPosition-targetOffset)
                    if(drift>650L)player.seekTo(targetOffset.coerceAtMost((target.durationMs-200L).coerceAtLeast(0L)))
                }
                syncError=""
                return
            }
            playItem(targetIndex,targetOffset)
            syncError=""
        }.onFailure{syncError=it.javaClass.simpleName+":"+(it.message?:"")}
    }
    private fun currentSyncDriftMs'''
s=s[:m.start()]+fn+s[m.end():]

# heartbeat adiciona diagnósticos
needle='''            .put("serverClockOffsetMs",serverClockOffsetMs)
'''
rep='''            .put("serverClockOffsetMs",serverClockOffsetMs)
            .put("syncEligible",syncEligible)
            .put("syncReason",syncReason)
            .put("syncTargetMediaId",syncTargetMediaId)
            .put("syncTargetOffsetMs",syncTargetOffsetMs)
            .put("syncLocalPositionMs",syncLocalPositionMs)
            .put("syncError",syncError)
            .put("syncClockNowMs",synchronizedNowMs())
            .put("deviceClockNowMs",System.currentTimeMillis())
'''
if s.count(needle)!=1: raise SystemExit('serverClockOffset heartbeat não encontrado')
s=s.replace(needle,rep,1)

# versão
g=Path('app/build.gradle.kts')
gs=g.read_text(encoding='utf-8')
if 'versionCode = 41' not in gs or 'versionName = "0.10.11"' not in gs:
    raise SystemExit('build.gradle não está na 0.10.11 esperada')
g.write_text(gs.replace('versionCode = 41','versionCode = 42').replace('versionName = "0.10.11"','versionName = "0.10.12"'),encoding='utf-8')

required=['synchronizedNowMs()','syncEligible','syncReason','syncTargetMediaId','syncTargetOffsetMs','syncLocalPositionMs','syncError','OffsetDateTime.parse','deviceClockNowMs','syncClockNowMs','/api/state','/api/tvs',':8799']
for x in required:
    if x not in s: raise SystemExit('ausente: '+x)

p.write_text(s,encoding='utf-8')
print('OK 0.10.12: elegibilidade usa relógio do Console e heartbeat inclui diagnóstico de sync.')
