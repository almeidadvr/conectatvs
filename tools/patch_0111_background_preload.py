from pathlib import Path
import re

p=Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
s=p.read_text(encoding='utf-8')

def once(old,new,label):
    global s
    n=s.count(old)
    if n!=1: raise SystemExit(f'{label}: esperado 1, encontrado {n}')
    s=s.replace(old,new,1)

once('''    private val preloadIntervalMs = 5L * 60L * 1000L
    private var lastPreloadMs = 0L
''','''    private val preloadIntervalMs = 5L * 60L * 1000L
    private var lastPreloadMs = 0L
    private var preloadJob: Job? = null
''','campo preloadJob')

once('''        withContext(Dispatchers.IO){cleanupMediaCache(state,tv); predownloadApplicable(state,tv)}
        updateReadiness(state,tv)
        val playlist=choosePlaylist(state,tv)
''','''        withContext(Dispatchers.IO){cleanupMediaCache(state,tv)}
        val playlist=choosePlaylist(state,tv)
''','remover preload bloqueante')

once('''        }else if(syncEnabled){
            syncPlayback(!wasSyncEnabled)
        }else if(currentIndex<0&&activeItems.isNotEmpty())playItem(0,0)
    }
    private fun autoSyncEligible''','''        }else if(syncEnabled){
            syncPlayback(!wasSyncEnabled)
        }else if(currentIndex<0&&activeItems.isNotEmpty())playItem(0,0)
        schedulePredownload(state,tv)
        updateReadiness(state,tv)
    }
    private fun autoSyncEligible''','agendar preload após playlist atual')

pat=re.compile(r'    private fun predownloadApplicable\(state:JSONObject,tv:JSONObject\)\{.*?\n    \}\n\n    private fun updateReadiness',re.S)
m=pat.search(s)
if not m: raise SystemExit('predownloadApplicable não encontrado')
fn='''    private fun schedulePredownload(state:JSONObject,tv:JSONObject){
        val now=synchronizedNowMs()
        if(preloadJob?.isActive==true)return
        if(lastPreloadMs>0L && now>=lastPreloadMs && now-lastPreloadMs<preloadIntervalMs)return
        lastPreloadMs=now
        val stateCopy=JSONObject(state.toString())
        val tvCopy=JSONObject(tv.toString())
        preloadJob=scope.launch(Dispatchers.IO){
            var errors=0
            applicablePlaylists(stateCopy,tvCopy).forEach{pl->
                runCatching{cachePlaylist(normalizePlaylist(stateCopy,pl))}.onFailure{errors++}
            }
            withContext(Dispatchers.Main){
                updateReadiness(stateCopy,tvCopy)
                if(errors>0)postExtensionEvent("preload_error","Falha no pré-download de $errors playlist(s)","warning",JSONObject().put("errors",errors))
                else postExtensionEvent("preload_ok","Pré-download verificado; conteúdo futuro disponível")
            }
        }
    }

    private fun updateReadiness'''
s=s[:m.start()]+fn+s[m.end():]

once('''    override fun onDestroy(){connectivityJob?.cancel();syncJob?.cancel();imageJob?.cancel();scope.cancel();player.release();super.onDestroy()}
''','''    override fun onDestroy(){connectivityJob?.cancel();syncJob?.cancel();preloadJob?.cancel();imageJob?.cancel();scope.cancel();player.release();super.onDestroy()}
''','cancel preload')

p.write_text(s,encoding='utf-8')

g=Path('app/build.gradle.kts');gs=g.read_text(encoding='utf-8')
if 'versionCode = 50' not in gs or 'versionName = "0.11.0"' not in gs: raise SystemExit('base 0.11.0 esperada')
g.write_text(gs.replace('versionCode = 50','versionCode = 51').replace('versionName = "0.11.0"','versionName = "0.11.1"'),encoding='utf-8')

required=['preloadJob','schedulePredownload(state,tv)','scope.launch(Dispatchers.IO)','updateReadiness(stateCopy,tvCopy)','versionName = "0.11.1"']
text=s+g.read_text(encoding='utf-8')
for x in required:
    if x not in text: raise SystemExit('ausente: '+x)
if 'withContext(Dispatchers.IO){cleanupMediaCache(state,tv); predownloadApplicable(state,tv)}' in s: raise SystemExit('preload bloqueante ainda presente')
print('OK 0.11.1: pré-download futuro em background; heartbeat não fica bloqueado.')
