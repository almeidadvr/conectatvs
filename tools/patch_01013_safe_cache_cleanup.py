from pathlib import Path

p=Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
s=p.read_text(encoding='utf-8')

# Executado depois da 0.10.12.
# Política segura de cache:
# - protege mídias de qualquer playlist ativa aplicável à TV/grupo, inclusive agendada/recorrente;
# - protege playlist fixa da TV e qualquer fallback ativo;
# - protege a mídia/lista atualmente carregada;
# - arquivo sem referência vira órfão, mas só é apagado após 7 dias contínuos sem referência;
# - se voltar a ser referenciado antes disso, o contador de órfão é removido.

old='''    private var syncError = ""
'''
new='''    private var syncError = ""
    private val cacheOrphanGraceMs = 7L * 24L * 60L * 60L * 1000L
    private val cacheCleanupIntervalMs = 6L * 60L * 60L * 1000L
'''
if s.count(old)!=1: raise SystemExit('campos de diagnóstico 0.10.12 não encontrados')
s=s.replace(old,new,1)

# Executa a manutenção somente após a TV ser identificada e um /api/state válido ser recebido.
needle='''        pairedTv=tv
        if(tv!=null){
            val resolvedId=tv.optString("id")
            if(resolvedId.isNotBlank()&&resolvedId!=pairedTvId){pairedTvId=resolvedId;prefs.edit().putString("paired_tv_id",pairedTvId).apply()}
        }
        if(tv==null){showPairingState("Console conectado. Cadastre o código acima no painel.");return}
        val playlist=choosePlaylist(state,tv)
'''
replacement='''        pairedTv=tv
        if(tv!=null){
            val resolvedId=tv.optString("id")
            if(resolvedId.isNotBlank()&&resolvedId!=pairedTvId){pairedTvId=resolvedId;prefs.edit().putString("paired_tv_id",pairedTvId).apply()}
        }
        if(tv==null){showPairingState("Console conectado. Cadastre o código acima no painel.");return}
        withContext(Dispatchers.IO){cleanupMediaCache(state,tv)}
        val playlist=choosePlaylist(state,tv)
'''
if s.count(needle)!=1: raise SystemExit('ponto de manutenção em applyState não encontrado')
s=s.replace(needle,replacement,1)

# Insere política antes de cachePlaylist.
marker='''    private fun cachePlaylist(p:JSONObject):List<PlaylistItem>{'''
if s.count(marker)!=1: raise SystemExit('cachePlaylist não encontrado')
code='''    private fun protectedMediaIds(state:JSONObject,tv:JSONObject):Set<String>{
        val protected=mutableSetOf<String>()
        // Nunca remover algo que já está carregado/reproduzindo localmente.
        activeItems.mapTo(protected){it.id}
        val fixedPlaylistId=tv.optString("playlistId")
        val playlists=state.optJSONArray("playlists")?:JSONArray()
        for(i in 0 until playlists.length()){
            val pl=playlists.optJSONObject(i)?:continue
            if(!pl.optBoolean("active",true))continue
            val pid=pl.optString("id")
            val fallback=pl.optBoolean("fallback",false)
            // Agendamento/recorrência não é filtrado por data/hora aqui de propósito:
            // se a playlist continua cadastrada e aplicável, sua mídia fica protegida.
            val applies=fallback || pid==fixedPlaylistId || targetsTV(pl,tv)
            if(!applies)continue
            val items=pl.optJSONArray("items")?:JSONArray()
            for(j in 0 until items.length()){
                val item=items.optJSONObject(j)?:continue
                val mediaId=item.optString("mediaId").ifBlank{item.optString("id")}
                if(mediaId.isNotBlank())protected+=mediaId
            }
        }
        return protected
    }

    private fun mediaIdFromCacheFile(file:File):String{
        val name=file.name
        if(name.endsWith(".part"))return ""
        val dot=name.lastIndexOf('.')
        return if(dot>0)name.substring(0,dot) else name
    }

    private fun cleanupMediaCache(state:JSONObject,tv:JSONObject){
        val dir=File(filesDir,"media")
        if(!dir.exists()||!dir.isDirectory)return
        val now=synchronizedNowMs()
        val last=prefs.getLong("cache_cleanup_last_ms",0L)
        // Evita varrer armazenamento a cada heartbeat; primeira execução é imediata.
        if(last>0L && now>=last && now-last<cacheCleanupIntervalMs)return
        prefs.edit().putLong("cache_cleanup_last_ms",now).apply()
        val protected=protectedMediaIds(state,tv)
        dir.listFiles()?.forEach{file->
            if(!file.isFile)return@forEach
            val mediaId=mediaIdFromCacheFile(file)
            if(mediaId.isBlank())return@forEach
            val key="cache_orphan_since_"+mediaId
            if(mediaId in protected){
                if(prefs.contains(key))prefs.edit().remove(key).apply()
                return@forEach
            }
            val since=prefs.getLong(key,0L)
            if(since<=0L || now<since){
                prefs.edit().putLong(key,now).apply()
                return@forEach
            }
            if(now-since>=cacheOrphanGraceMs){
                if(file.delete())prefs.edit().remove(key).apply()
            }
        }
    }

'''
s=s.replace(marker,code+marker,1)

# versão
g=Path('app/build.gradle.kts')
gs=g.read_text(encoding='utf-8')
if 'versionCode = 42' not in gs or 'versionName = "0.10.12"' not in gs:
    raise SystemExit('build.gradle não está na 0.10.12 esperada')
g.write_text(gs.replace('versionCode = 42','versionCode = 43').replace('versionName = "0.10.12"','versionName = "0.10.13"'),encoding='utf-8')

required=[
    'cleanupMediaCache(state,tv)','protectedMediaIds','cacheOrphanGraceMs = 7L * 24L',
    'cacheCleanupIntervalMs = 6L * 60L','cache_orphan_since_','cache_cleanup_last_ms',
    'fallback || pid==fixedPlaylistId || targetsTV(pl,tv)','activeItems.mapTo(protected)',
    '/api/state','/api/tvs',':8799','syncEligible','syncReason'
]
for x in required:
    if x not in s: raise SystemExit('ausente: '+x)

p.write_text(s,encoding='utf-8')
print('OK 0.10.13: cache protegido por referências válidas; órfãos removidos só após 7 dias contínuos.')
