from pathlib import Path
import re

p=Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
s=p.read_text(encoding='utf-8')

# Executado depois de 0.10.8. Faz o Player memorizar o id do registro de TV
# após o primeiro pareamento. Nas leituras futuras, id salvo tem prioridade
# sobre pairingCode. O código de pareamento vira apenas fallback do primeiro vínculo.

# adiciona campo de id persistente
old='''    private var pairedTv: JSONObject? = null
    private var currentPlaylistId = ""
'''
new='''    private var pairedTv: JSONObject? = null
    private var pairedTvId = ""
    private var currentPlaylistId = ""
'''
if s.count(old)!=1: raise SystemExit('campo pairedTv esperado não encontrado')
s=s.replace(old,new,1)

# carrega id persistente no onCreate
old='''        pairingCode=prefs.getString("pairing_code",null) ?: Random.nextInt(100000,999999).toString().also{prefs.edit().putString("pairing_code",it).apply()}
        codeText.text="${pairingCode.take(3)} ${pairingCode.takeLast(3)}"
'''
new='''        pairingCode=prefs.getString("pairing_code",null) ?: Random.nextInt(100000,999999).toString().also{prefs.edit().putString("pairing_code",it).apply()}
        pairedTvId=prefs.getString("paired_tv_id","") ?: ""
        codeText.text="${pairingCode.take(3)} ${pairingCode.takeLast(3)}"
'''
if s.count(old)!=1: raise SystemExit('onCreate pairing não encontrado')
s=s.replace(old,new,1)

# troca localização da TV no applyState: id salvo primeiro; código apenas fallback
pat=re.compile(r'''        val tvs=state\.optJSONArray\("tvs"\)\?:JSONArray\(\)\n        val tv=\(0 until tvs\.length\(\)\)\.mapNotNull\{tvs\.optJSONObject\(it\)\}\.firstOrNull\{it\.optString\("pairingCode"\)==pairingCode\}\n        pairedTv=tv''')
m=pat.search(s)
if not m: raise SystemExit('localização de TV no applyState não encontrada')
rep='''        val tvs=state.optJSONArray("tvs")?:JSONArray()
        val allTvs=(0 until tvs.length()).mapNotNull{tvs.optJSONObject(it)}
        var tv=if(pairedTvId.isNotBlank())allTvs.firstOrNull{it.optString("id")==pairedTvId}else null
        if(tv==null){
            val matches=allTvs.filter{it.optString("pairingCode")==pairingCode}
            tv=when{
                matches.size==1->matches.first()
                matches.size>1->matches.firstOrNull{it.optString("id")==pairedTvId}
                else->null
            }
        }
        pairedTv=tv
        if(tv!=null){
            val resolvedId=tv.optString("id")
            if(resolvedId.isNotBlank()&&resolvedId!=pairedTvId){pairedTvId=resolvedId;prefs.edit().putString("paired_tv_id",pairedTvId).apply()}
        }'''
s=s[:m.start()]+rep+s[m.end():]

# heartbeat deve recusar PUT sem id conhecido, para nunca atualizar registro ambíguo
old='''        val tv=pairedTv?:return
        val n=networkInfo()
'''
new='''        val tv=pairedTv?:return
        val stableId=pairedTvId.ifBlank{tv.optString("id")}
        if(stableId.isBlank())return
        val n=networkInfo()
'''
if s.count(old)!=1: raise SystemExit('início heartbeat não encontrado')
s=s.replace(old,new,1)
s=s.replace('.put("id",tv.optString("id"))','.put("id",stableId)',1)

# envia também uma identidade da instalação para diagnóstico futuro; backend antigo pode ignorar.
needle='''            .put("pairingCode",tv.optString("pairingCode",pairingCode))
            .put("playlistId",tv.optString("playlistId"))
'''
replacement='''            .put("pairingCode",tv.optString("pairingCode",pairingCode))
            .put("playerInstanceId",stableId+":"+pairingCode)
            .put("playlistId",tv.optString("playlistId"))
'''
if s.count(needle)!=1: raise SystemExit('trecho heartbeat identidade não encontrado')
s=s.replace(needle,replacement,1)

# versão
g=Path('app/build.gradle.kts')
gs=g.read_text(encoding='utf-8')
if 'versionCode = 38' not in gs or 'versionName = "0.10.8"' not in gs:
    raise SystemExit('build.gradle não está na 0.10.8 esperada')
g.write_text(gs.replace('versionCode = 38','versionCode = 39').replace('versionName = "0.10.8"','versionName = "0.10.9"'),encoding='utf-8')

required=['pairedTvId','paired_tv_id','stableId','.put("id",stableId)','playerInstanceId','autoSyncEligible','/api/tvs',':8799']
for x in required:
    if x not in s: raise SystemExit('ausente: '+x)
if 'firstOrNull{it.optString("pairingCode")==pairingCode}' in s:
    raise SystemExit('match exclusivo antigo por pairingCode ainda presente')

p.write_text(s,encoding='utf-8')
print('OK 0.10.9: identidade persistente por id, pairingCode apenas fallback inicial.')
