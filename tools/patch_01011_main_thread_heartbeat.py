from pathlib import Path
import re

p=Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
s=p.read_text(encoding='utf-8')

# Executado depois da 0.10.10.
# Corrige a regressão em que currentSyncDriftMs() acessava ExoPlayer dentro de Dispatchers.IO.
# A leitura do Player é feita na Main thread; apenas o PUT HTTP roda em IO.

old='''                    applyState(snap.first)
                    // Heartbeat é independente: rejeição do PUT não significa perda de conexão com o Console.
                    withContext(Dispatchers.IO){postHeartbeat()}
'''
new='''                    applyState(snap.first)
                    // ExoPlayer só pode ser consultado na thread principal.
                    // O snapshot de drift é capturado aqui (scope=Dispatchers.Main) e somente o HTTP roda em IO.
                    val heartbeatDriftMs=runCatching{currentSyncDriftMs()}.getOrDefault(0L)
                    // Heartbeat é independente: rejeição do PUT não significa perda de conexão com o Console.
                    withContext(Dispatchers.IO){postHeartbeat(heartbeatDriftMs)}
'''
if s.count(old)!=1:
    raise SystemExit('trecho de heartbeat no loop 0.10.10 não encontrado')
s=s.replace(old,new,1)

# postHeartbeat passa a receber o drift já calculado na Main thread.
if s.count('private fun postHeartbeat():Boolean')!=1:
    raise SystemExit('assinatura postHeartbeat 0.10.10 não encontrada')
s=s.replace('private fun postHeartbeat():Boolean','private fun postHeartbeat(heartbeatDriftMs:Long):Boolean',1)

if s.count('.put("syncDriftMs",currentSyncDriftMs())')!=1:
    raise SystemExit('syncDriftMs dinâmico no heartbeat não encontrado')
s=s.replace('.put("syncDriftMs",currentSyncDriftMs())','.put("syncDriftMs",heartbeatDriftMs)',1)

# JSONObject(tv.toString()) pode conter playerInstanceId antigo vindo do estado persistido.
# Removemos explicitamente antes de reenviar para não perpetuar identidade diagnóstica obsoleta.
needle='''        val body=JSONObject(tv.toString())
            .put("id",stableId)
'''
replacement='''        val body=JSONObject(tv.toString()).apply{remove("playerInstanceId")}
            .put("id",stableId)
'''
if s.count(needle)!=1:
    raise SystemExit('construção do body 0.10.10 não encontrada')
s=s.replace(needle,replacement,1)

# versão
g=Path('app/build.gradle.kts')
gs=g.read_text(encoding='utf-8')
if 'versionCode = 40' not in gs or 'versionName = "0.10.10"' not in gs:
    raise SystemExit('build.gradle não está na 0.10.10 esperada')
g.write_text(gs.replace('versionCode = 40','versionCode = 41').replace('versionName = "0.10.10"','versionName = "0.10.11"'),encoding='utf-8')

required=[
    'val heartbeatDriftMs=runCatching{currentSyncDriftMs()}.getOrDefault(0L)',
    'withContext(Dispatchers.IO){postHeartbeat(heartbeatDriftMs)}',
    'private fun postHeartbeat(heartbeatDriftMs:Long):Boolean',
    '.put("syncDriftMs",heartbeatDriftMs)',
    'JSONObject(tv.toString()).apply{remove("playerInstanceId")}',
    'pairedTvId','paired_tv_id','autoSyncEligible','/api/state','/api/tvs',':8799'
]
for x in required:
    if x not in s: raise SystemExit('ausente: '+x)

forbidden=[
    'withContext(Dispatchers.IO){postHeartbeat()}',
    '.put("syncDriftMs",currentSyncDriftMs())'
]
for x in forbidden:
    if x in s: raise SystemExit('regressão ainda presente: '+x)

p.write_text(s,encoding='utf-8')
print('OK 0.10.11: leitura do ExoPlayer na Main; PUT em IO; playerInstanceId residual removido.')
