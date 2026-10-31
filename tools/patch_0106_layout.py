from pathlib import Path

for rel in ['app/src/main/res/layout/activity_main.xml','app/src/main/res/layout-land/activity_main.xml']:
    p=Path(rel)
    s=p.read_text(encoding='utf-8')
    if 'android:id="@+id/brandLogo"' not in s:
        raise SystemExit(f'{rel}: brandLogo ausente')
    if 'Player para Android TV' in s or 'Código deste dispositivo' in s:
        raise SystemExit(f'{rel}: texto removido reapareceu')
    # Adiciona fallback estático somente no ImageView brandLogo, sem alterar dimensões ou posição.
    pos=s.index('android:id="@+id/brandLogo"')
    end=s.index('/>',pos)
    block=s[pos:end]
    if 'android:src="@drawable/logo_conecta_transparente"' not in block:
        marker='android:scaleType="fitCenter"'
        if marker not in block:
            raise SystemExit(f'{rel}: scaleType esperado não encontrado')
        block=block.replace(marker,marker+'\n            android:src="@drawable/logo_conecta_transparente"',1)
        s=s[:pos]+block+s[end:]
    p.write_text(s,encoding='utf-8')

print('OK: drawable estático aplicado aos dois layouts sem alterar geometria.')
