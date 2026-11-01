from pathlib import Path
import re

p=Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
s=p.read_text(encoding='utf-8')

def once(old,new,label):
    global s
    n=s.count(old)
    if n!=1: raise SystemExit(f'{label}: esperado 1, encontrado {n}')
    s=s.replace(old,new,1)

once('import android.content.Context\n','import android.content.Context\nimport android.content.Intent\n','intent import')
once('import androidx.core.app.ActivityCompat\n','import androidx.core.app.ActivityCompat\nimport androidx.core.content.FileProvider\n','fileprovider import')
once('import androidx.media3.common.MediaItem\n','import androidx.media3.common.MediaItem\nimport androidx.media3.common.PlaybackException\n','playback import')
once('import java.io.FileOutputStream\n','import java.io.FileOutputStream\nimport java.security.MessageDigest\n','digest import')

once('''    private val cacheOrphanGraceMs = 7L * 24L * 60L * 60L * 1000L
    private val cacheCleanupIntervalMs = 6L * 60L * 60L * 1000L
''','''    private val cacheOrphanGraceMs = 7L * 24L * 60L * 60L * 1000L
    private val cacheCleanupIntervalMs = 6L * 60L * 60L * 1000L
    private val preloadIntervalMs = 5L * 60L * 1000L
    private var lastPreloadMs = 0L
    private var readyStatus = "checking"
    private var readyPercent = 0
    private var readyTotalItems = 0
    private var readyDownloadedItems = 0
    private var preloadPending = 0
    private var nextPlaylistId = ""
    private var nextPlaylistName = ""
    private var lastCommandId = 0L
    private var autoRepairAttempts = 0
    private var screenBlack = false
    private var proofStartedAtMs = 0L
    private var proofMediaId = ""
    private var lastProtectedMediaIds:Set<String> = emptySet()
''','etapa2 fields')

once('''        player=ExoPlayer.Builder(this).build(); playerView.player=player; player.repeatMode=Player.REPEAT_MODE_OFF
        player.addListener(object:Player.Listener{ override fun onPlaybackStateChanged(state:Int){ if(state==Player.STATE_ENDED){ if(syncEnabled) syncPlayback(true) else playNext() } } })
''','''        player=ExoPlayer.Builder(this).build(); playerView.player=player; player.repeatMode=Player.REPEAT_MODE_OFF
        player.addListener(object:Player.Listener{
            override fun onPlaybackStateChanged(state:Int){
                if(state==Player.STATE_READY) autoRepairAttempts=0
                if(state==Player.STATE_ENDED){ finishProof("completed",""); if(syncEnabled) syncPlayback(true) else playNext() }
            }
            override fun onPlayerError(error:PlaybackException){ handlePlaybackError(error) }
        })
''','listener autorepair')

once('''        serverUrl=prefs.getString("server_url","") ?: ""
''','''        serverUrl=prefs.getString("server_url","") ?: ""
        lastCommandId=prefs.getLong("last_command_id",0L)
''','load command id')

once('''                    applyState(snap.first)
                    // ExoPlayer só pode ser consultado na thread principal.
''','''                    applyState(snap.first)
                    pollAndExecuteCommands()
                    // ExoPlayer só pode ser consultado na thread principal.
''','poll commands')

once('''        withContext(Dispatchers.IO){cleanupMediaCache(state,tv)}
        val playlist=choosePlaylist(state,tv)
''','''        withContext(Dispatchers.IO){cleanupMediaCache(state,tv); predownloadApplicable(state,tv)}
        updateReadiness(state,tv)
        val playlist=choosePlaylist(state,tv)
''','predownload hook')

marker='    private fun cachePlaylist(p:JSONObject):List<PlaylistItem>{'
if s.count(marker)!=1: raise SystemExit('cachePlaylist marker não encontrado')
helpers=r'''    private fun extensionUrl():String=serverUrl.replace(Regex(":8799$"),":8800")

    private fun applicablePlaylists(state:JSONObject,tv:JSONObject):List<JSONObject>{
        val fixed=tv.optString("playlistId")
        val arr=state.optJSONArray("playlists")?:JSONArray()
        return (0 until arr.length()).mapNotNull{arr.optJSONObject(it)}.filter{pl->
            pl.optBoolean("active",true) && (pl.optBoolean("fallback",false) || pl.optString("id")==fixed || targetsTV(pl,tv))
        }
    }

    private fun predownloadApplicable(state:JSONObject,tv:JSONObject){
        val now=synchronizedNowMs()
        if(lastPreloadMs>0L && now>=lastPreloadMs && now-lastPreloadMs<preloadIntervalMs)return
        lastPreloadMs=now
        var errors=0
        applicablePlaylists(state,tv).forEach{pl->
            runCatching{cachePlaylist(normalizePlaylist(state,pl))}.onFailure{errors++}
        }
        if(errors>0)postExtensionEvent("preload_error","Falha no pré-download de $errors playlist(s)","warning",JSONObject().put("errors",errors))
    }

    private fun updateReadiness(state:JSONObject,tv:JSONObject){
        val protected=protectedMediaIds(state,tv)
        lastProtectedMediaIds=protected
        readyTotalItems=protected.size
        val dir=File(filesDir,"media")
        val cached=dir.listFiles()?.filter{it.isFile&&it.length()>0}.orEmpty().map{mediaIdFromCacheFile(it)}.toSet()
        readyDownloadedItems=protected.count{it in cached}
        preloadPending=(readyTotalItems-readyDownloadedItems).coerceAtLeast(0)
        readyPercent=if(readyTotalItems==0)100 else ((readyDownloadedItems*100.0)/readyTotalItems).toInt().coerceIn(0,100)
        readyStatus=when{readyTotalItems==0->"ready";preloadPending==0->"ready";readyDownloadedItems>0->"downloading";else->"pending"}
        val current=currentPlaylistId
        val candidates=applicablePlaylists(state,tv).filter{it.optString("id")!=current}
        val next=candidates.minByOrNull{pl->
            runCatching{java.time.OffsetDateTime.parse(pl.optString("startDateTime")).toInstant().toEpochMilli()}.getOrDefault(Long.MAX_VALUE-1)
        }
        nextPlaylistId=next?.optString("id").orEmpty()
        nextPlaylistName=next?.optString("name").orEmpty()
    }

    private fun postExtension(path:String,body:JSONObject):Boolean{
        if(serverUrl.isBlank())return false
        val req=Request.Builder().url(extensionUrl()+path).post(body.toString().toRequestBody("application/json".toMediaType())).build()
        return runCatching{client.newCall(req).execute().use{it.isSuccessful}}.getOrDefault(false)
    }

    private fun postExtensionEvent(type:String,message:String,level:String="info",data:JSONObject?=null){
        val tvId=pairedTvId.ifBlank{pairedTv?.optString("id").orEmpty()}; if(tvId.isBlank())return
        val body=JSONObject().put("tvId",tvId).put("type",type).put("message",message).put("level",level).put("playlistId",currentPlaylistId).put("mediaId",activeItems.getOrNull(currentIndex)?.id?:"")
        if(data!=null)body.put("data",data)
        scope.launch(Dispatchers.IO){postExtension("/api/v2/events",body)}
    }

    private fun startProof(item:PlaylistItem){
        proofStartedAtMs=synchronizedNowMs(); proofMediaId=item.id
        val tvId=pairedTvId.ifBlank{pairedTv?.optString("id").orEmpty()}; if(tvId.isBlank())return
        val body=JSONObject().put("tvId",tvId).put("mediaId",item.id).put("playlistId",currentPlaylistId).put("startedAt",Instant.ofEpochMilli(proofStartedAtMs).toString()).put("status","started")
        scope.launch(Dispatchers.IO){postExtension("/api/v2/proof",body)}
    }

    private fun finishProof(status:String,error:String){
        if(proofMediaId.isBlank()||proofStartedAtMs<=0L)return
        val tvId=pairedTvId.ifBlank{pairedTv?.optString("id").orEmpty()}; val end=synchronizedNowMs()
        val body=JSONObject().put("tvId",tvId).put("mediaId",proofMediaId).put("playlistId",currentPlaylistId).put("startedAt",Instant.ofEpochMilli(proofStartedAtMs).toString()).put("endedAt",Instant.ofEpochMilli(end).toString()).put("durationMs",(end-proofStartedAtMs).coerceAtLeast(0L)).put("status",status).put("error",error)
        proofMediaId="";proofStartedAtMs=0L
        if(tvId.isNotBlank())scope.launch(Dispatchers.IO){postExtension("/api/v2/proof",body)}
    }

    private fun handlePlaybackError(error:PlaybackException){
        finishProof("error",error.message?:error.errorCodeName)
        autoRepairAttempts++
        postExtensionEvent("player_error","Erro de reprodução: ${error.errorCodeName}","error",JSONObject().put("attempt",autoRepairAttempts).put("detail",error.message?:""))
        scope.launch{
            delay(1200)
            if(activeItems.isEmpty())return@launch
            if(autoRepairAttempts<=2){
                val idx=currentIndex.coerceAtLeast(0)
                val pos=runCatching{player.currentPosition}.getOrDefault(0L)
                playItem(idx,pos)
                postExtensionEvent("auto_repair","Reprodução recarregada automaticamente (tentativa $autoRepairAttempts)")
            }else{
                autoRepairAttempts=0
                postExtensionEvent("auto_repair_skip","Mídia ignorada após falhas repetidas","warning")
                playItem((currentIndex+1).coerceAtLeast(0)%activeItems.size,0)
            }
        }
    }

    private suspend fun pollAndExecuteCommands(){
        val tvId=pairedTvId;if(tvId.isBlank())return
        val url=extensionUrl()+"/api/v2/commands?tvId="+Uri.encode(tvId)+"&after="+lastCommandId
        val arr=withContext(Dispatchers.IO){runCatching{getJsonArray(url)}.getOrDefault(JSONArray())}
        for(i in 0 until arr.length()){
            val c=arr.optJSONObject(i)?:continue
            val id=c.optLong("id"); val command=c.optString("command"); val payload=c.optJSONObject("payload")?:JSONObject()
            var status="ok"; var msg="executado"
            runCatching{executeCommand(command,payload)}.onFailure{status="error";msg=it.message?:it.javaClass.simpleName}
            lastCommandId=maxOf(lastCommandId,id);prefs.edit().putLong("last_command_id",lastCommandId).apply()
            val ack=JSONObject().put("id",id).put("status",status).put("message",msg)
            withContext(Dispatchers.IO){postExtension("/api/v2/commands/ack",ack)}
        }
    }

    private fun executeCommand(command:String,payload:JSONObject){
        when(command){
            "restartPlayback"->{screenBlack=false;playItem(currentIndex.coerceAtLeast(0),0)}
            "next"->{screenBlack=false;playNext()}
            "reload"->{prefs.edit().putString("playlist_signature","").apply();postExtensionEvent("remote_reload","Recarregamento solicitado pelo Console")}
            "syncNow"->{screenBlack=false;if(syncEnabled)syncPlayback(true)else playItem(currentIndex.coerceAtLeast(0),0)}
            "clearCache"->{clearUnusedCacheNow();postExtensionEvent("cache_clear","Limpeza manual de cache executada")}
            "screenBlack"->{finishProof("interrupted","screenBlack");screenBlack=true;player.pause();playerView.visibility=View.GONE;imageView.visibility=View.GONE;statusPanel.visibility=View.GONE;window.decorView.setBackgroundColor(android.graphics.Color.BLACK)}
            "resume"->{screenBlack=false;window.decorView.setBackgroundColor(android.graphics.Color.BLACK);playItem(currentIndex.coerceAtLeast(0),runCatching{player.currentPosition}.getOrDefault(0L))}
            "updatePlayer"->{val url=payload.optString("url");if(url.isBlank())error("URL de atualização ausente");startPlayerUpdate(url,payload.optString("sha256"),payload.optString("version"))}
            else->error("Comando desconhecido: $command")
        }
    }

    private fun clearUnusedCacheNow(){
        val keep=lastProtectedMediaIds + activeItems.map{it.id}
        File(filesDir,"media").listFiles()?.forEach{f->if(f.isFile&&mediaIdFromCacheFile(f) !in keep)f.delete()}
    }

    private fun startPlayerUpdate(url:String,expectedSha:String,version:String){
        scope.launch(Dispatchers.IO){
            runCatching{
                val dir=File(filesDir,"updates").apply{mkdirs()};val apk=File(dir,"Conecta-Midia-Player-$version.apk")
                downloadTo(url,apk)
                if(expectedSha.isNotBlank()){
                    val md=MessageDigest.getInstance("SHA-256");apk.inputStream().use{input->val buf=ByteArray(1024*1024);while(true){val n=input.read(buf);if(n<=0)break;md.update(buf,0,n)}}
                    val got=md.digest().joinToString(""){"%02x".format(it)};if(!got.equals(expectedSha,true))error("SHA-256 inválido")
                }
                withContext(Dispatchers.Main){
                    val uri=FileProvider.getUriForFile(this@MainActivity,packageName+".fileprovider",apk)
                    val intent=Intent(Intent.ACTION_VIEW).setDataAndType(uri,"application/vnd.android.package-archive").addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK)
                    startActivity(intent);postExtensionEvent("update_started","Atualização $version preparada; aguardando confirmação do Android")
                }
            }.onFailure{postExtensionEvent("update_error","Falha ao preparar atualização: ${it.message}","error")}
        }
    }

'''
s=s.replace(marker,helpers+marker,1)

pat=re.compile(r'    private fun playItem\(index:Int,offset:Long\)\{.*?\}\n    private fun playNext',re.S)
m=pat.search(s)
if not m: raise SystemExit('playItem não encontrado')
newplay='''    private fun playItem(index:Int,offset:Long){
        if(activeItems.isEmpty()||screenBlack)return
        finishProof("completed","")
        playbackStarted=true;currentIndex=index%activeItems.size;playSequence++
        val item=activeItems[currentIndex];startProof(item)
        statusPanel.visibility=View.GONE;settingsButton.visibility=View.GONE;imageJob?.cancel();player.stop()
        if(item.kind=="video"){
            imageView.visibility=View.GONE;playerView.visibility=View.VISIBLE
            player.setMediaItem(MediaItem.fromUri(Uri.fromFile(File(item.localPath))));player.prepare();player.seekTo(offset.coerceIn(0L,(item.durationMs-200L).coerceAtLeast(0L)));player.playWhenReady=true
        }else{
            playerView.visibility=View.GONE;imageView.visibility=View.VISIBLE;imageView.setImageBitmap(BitmapFactory.decodeFile(item.localPath))
            imageJob=scope.launch{delay(if(syncEnabled)(item.durationMs-offset).coerceAtLeast(100L) else item.durationMs);finishProof("completed","");if(syncEnabled)syncPlayback(true)else playNext()}
        }
    }
    private fun playNext'''
s=s[:m.start()]+newplay+s[m.end():]

once('''            .put("deviceClockNowMs",System.currentTimeMillis())
''','''            .put("deviceClockNowMs",System.currentTimeMillis())
            .put("readyStatus",readyStatus)
            .put("readyPercent",readyPercent)
            .put("readyTotalItems",readyTotalItems)
            .put("readyDownloadedItems",readyDownloadedItems)
            .put("preloadPending",preloadPending)
            .put("nextPlaylistId",nextPlaylistId)
            .put("nextPlaylistName",nextPlaylistName)
            .put("cacheBytes",File(filesDir,"media").listFiles()?.filter{it.isFile}?.sumOf{it.length()}?:0L)
            .put("autoRepairAttempts",autoRepairAttempts)
            .put("etapa2Extension",true)
''','heartbeat readiness')

needle='''    private fun getJson(url:String):JSONObject{client.newCall(Request.Builder().url(url).build()).execute().use{r->val txt=r.body?.string()?:"{}";if(!r.isSuccessful)error("HTTP ${r.code}");return JSONObject(txt)}}
'''
if s.count(needle)!=1: raise SystemExit('getJson não encontrado')
s=s.replace(needle,needle+'''    private fun getJsonArray(url:String):JSONArray{client.newCall(Request.Builder().url(url).build()).execute().use{r->val txt=r.body?.string()?:"[]";if(!r.isSuccessful)error("HTTP ${r.code}");return JSONArray(txt)}}\n''',1)

p.write_text(s,encoding='utf-8')

m=Path('app/src/main/AndroidManifest.xml')
ms=m.read_text(encoding='utf-8')
if 'REQUEST_INSTALL_PACKAGES' not in ms:
    ms=ms.replace('    <uses-permission android:name="android.permission.WAKE_LOCK" />\n','    <uses-permission android:name="android.permission.WAKE_LOCK" />\n    <uses-permission android:name="android.permission.REQUEST_INSTALL_PACKAGES" />\n',1)
provider='''        <provider
            android:name="androidx.core.content.FileProvider"
            android:authorities="${applicationId}.fileprovider"
            android:exported="false"
            android:grantUriPermissions="true">
            <meta-data android:name="android.support.FILE_PROVIDER_PATHS" android:resource="@xml/file_paths" />
        </provider>

'''
if 'androidx.core.content.FileProvider' not in ms:
    ms=ms.replace('        <receiver\n            android:name=".BootReceiver"\n',provider+'        <receiver\n            android:name=".BootReceiver"\n',1)
m.write_text(ms,encoding='utf-8')
xml=Path('app/src/main/res/xml');xml.mkdir(parents=True,exist_ok=True)
(xml/'file_paths.xml').write_text('''<?xml version="1.0" encoding="utf-8"?>\n<paths xmlns:android="http://schemas.android.com/apk/res/android">\n    <files-path name="updates" path="updates/" />\n</paths>\n''',encoding='utf-8')

g=Path('app/build.gradle.kts');gs=g.read_text(encoding='utf-8')
if 'versionCode = 43' not in gs or 'versionName = "0.10.13"' not in gs: raise SystemExit('base 0.10.13 esperada')
g.write_text(gs.replace('versionCode = 43','versionCode = 50').replace('versionName = "0.10.13"','versionName = "0.11.0"'),encoding='utf-8')

required=['predownloadApplicable','readyStatus','handlePlaybackError','pollAndExecuteCommands','startPlayerUpdate','REQUEST_INSTALL_PACKAGES','FileProvider','/api/v2/events','/api/v2/proof','/api/v2/commands','readyPercent','versionName = "0.11.0"']
alltext=s+ms+g.read_text(encoding='utf-8')
for x in required:
    if x not in alltext: raise SystemExit('ausente: '+x)
print('OK 0.11.0: Etapa 2 - predownload, readiness, eventos, autorreparo, comandos, update e prova de exibição.')
