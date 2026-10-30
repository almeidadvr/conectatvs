from pathlib import Path

p = Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
s = p.read_text(encoding='utf-8')
old = 'private fun loadOfficialLogo(){ runCatching{ val text=resources.openRawResource(R.raw.logo_conecta_base64).bufferedReader().use{it.readText().trim()}; val bytes=Base64.decode(text,Base64.DEFAULT); brandLogo.setImageBitmap(BitmapFactory.decodeByteArray(bytes,0,bytes.size)) }.onFailure{brandLogo.visibility=View.GONE} }'
new = 'private fun loadOfficialLogo(){ brandLogo.setImageResource(R.drawable.logo_conecta_transparente); brandLogo.visibility=View.VISIBLE }'
if old not in s:
    raise SystemExit('ERRO: função original de logo não encontrada; abortando para não alterar código funcional indevidamente')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')
print('OK: carregamento dinâmico quebrado removido; logo agora usa drawable PNG transparente e permanece visível.')
