from pathlib import Path

root = Path('app')
layout = root / 'src/main/res/layout/activity_main.xml'
main = root / 'src/main/java/com/conectasolucoes/conectasign/MainActivity.kt'
gradle = root / 'build.gradle.kts'
bg = root / 'src/main/res/drawable/player_background.xml'
panel = root / 'src/main/res/drawable/panel_bg_new.xml'
wifi = root / 'src/main/res/drawable/ic_wifi_modern.xml'

# 1) Layout: remove only the two requested labels, tighten logo/code spacing,
# and replace the placeholder Wi-Fi glyph with a real vector icon.
s = layout.read_text(encoding='utf-8')
s = s.replace('        <TextView android:id="@+id/subtitleText" android:layout_width="wrap_content" android:layout_height="wrap_content" android:text="Player para Android TV" android:textColor="#FFFFFF" android:textSize="14sp" />\n', '')
s = s.replace('        <TextView android:id="@+id/codeLabel" android:layout_width="wrap_content" android:layout_height="wrap_content" android:layout_marginTop="9dp" android:text="Código deste dispositivo" android:textColor="#C7D8EC" android:textSize="12sp" />\n', '')
old_code = '<TextView android:id="@+id/codeText" android:layout_width="wrap_content" android:layout_height="wrap_content" android:text="000 000" android:textColor="#D9EDFF" android:textStyle="bold" android:textSize="38sp" android:letterSpacing="0.08" />'
new_code = '<TextView android:id="@+id/codeText" android:layout_width="wrap_content" android:layout_height="wrap_content" android:layout_marginTop="-7dp" android:text="000 000" android:textColor="#FFFFFF" android:textStyle="bold" android:textSize="38sp" android:letterSpacing="0.08" />'
if old_code not in s:
    raise SystemExit('codeText original layout not found')
s = s.replace(old_code, new_code, 1)
old_wifi = '<TextView android:layout_width="24dp" android:layout_height="wrap_content" android:text="◉" android:textColor="#55C7FF" android:textSize="17sp" android:gravity="center" />'
new_wifi = '<ImageView android:layout_width="30dp" android:layout_height="30dp" android:layout_marginEnd="6dp" android:src="@drawable/ic_wifi_modern" android:contentDescription="Wi-Fi" />'
if old_wifi not in s:
    raise SystemExit('old Wi-Fi placeholder not found')
s = s.replace(old_wifi, new_wifi, 1)
layout.write_text(s, encoding='utf-8')

# 2) Full-screen approved blue-wave visual. Pure drawable; no behavior changes.
bg.write_text('''<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="1920dp" android:height="1080dp"
    android:viewportWidth="1920" android:viewportHeight="1080">
    <path android:fillColor="#07175E" android:pathData="M0,0H1920V1080H0Z"/>
    <path android:fillColor="#101D82" android:pathData="M0,105 C260,220 420,360 690,470 C990,590 1210,555 1450,395 C1640,270 1785,230 1920,255 L1920,600 C1725,555 1580,620 1400,730 C1120,900 810,875 520,735 C280,620 120,555 0,590Z"/>
    <path android:fillColor="#0B49D1" android:fillAlpha="0.52" android:pathData="M0,0 C180,205 320,355 560,435 C780,510 920,470 1110,350 C1330,210 1580,130 1920,190 L1920,300 C1630,255 1430,320 1220,450 C980,600 760,650 520,565 C285,480 145,365 0,220Z"/>
    <path android:fillColor="#1468FF" android:fillAlpha="0.25" android:pathData="M0,780 C245,645 450,655 670,790 C900,930 1115,970 1340,835 C1570,695 1750,640 1920,690 L1920,905 C1715,850 1550,900 1350,1010 C1120,1135 850,1090 610,955 C390,830 205,815 0,940Z"/>
    <path android:strokeColor="#16C8FF" android:strokeAlpha="0.52" android:strokeWidth="3" android:fillColor="#00000000" android:pathData="M0,180 C260,430 430,470 650,420 C930,355 1100,135 1370,145 C1600,155 1760,290 1920,400"/>
    <path android:strokeColor="#2B8CFF" android:strokeAlpha="0.42" android:strokeWidth="2" android:fillColor="#00000000" android:pathData="M0,805 C260,635 480,650 690,790 C920,940 1155,980 1390,825 C1610,680 1780,645 1920,700"/>
    <path android:strokeColor="#59B8FF" android:strokeAlpha="0.22" android:strokeWidth="1.5" android:fillColor="#00000000" android:pathData="M0,840 C250,690 460,700 680,830 C920,970 1150,1010 1400,870 C1620,745 1790,705 1920,735"/>
    <path android:strokeColor="#59B8FF" android:strokeAlpha="0.16" android:strokeWidth="1.5" android:fillColor="#00000000" android:pathData="M0,870 C240,735 455,750 670,860 C910,985 1150,1030 1410,905 C1640,795 1790,760 1920,780"/>
</vector>''', encoding='utf-8')

# 3) Panel color: same deep-blue surface that will show through transparent logo pixels.
panel.write_text('''<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <gradient android:angle="90" android:startColor="#101C6B" android:endColor="#0B185A" />
    <corners android:radius="28dp" />
    <stroke android:width="2dp" android:color="#23DAFF" />
    <padding android:left="2dp" android:top="2dp" android:right="2dp" android:bottom="2dp" />
</shape>''', encoding='utf-8')

# 4) Wi-Fi icon matching approved reference: three cyan arcs + central dot/inner arc.
wifi.write_text('''<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="30dp" android:height="30dp" android:viewportWidth="24" android:viewportHeight="24">
    <path android:fillColor="#31DFFF" android:pathData="M1,9l2,2c4.97,-4.97 13.03,-4.97 18,0l2,-2C16.93,2.93 7.07,2.93 1,9z"/>
    <path android:fillColor="#31DFFF" android:pathData="M5,13l2,2c2.76,-2.76 7.24,-2.76 10,0l2,-2C15.14,9.14 8.87,9.14 5,13z"/>
    <path android:fillColor="#31DFFF" android:pathData="M9,17l3,3 3,-3c-1.65,-1.66 -4.34,-1.66 -6,0z"/>
</vector>''', encoding='utf-8')

# 5) Logo: make blue/cyan pixels transparent after decoding so the exact panel color
# is visible behind it. White lettering and orange accents are preserved.
k = main.read_text(encoding='utf-8')
old_fun = 'private fun loadOfficialLogo(){ runCatching{ val text=resources.openRawResource(R.raw.logo_conecta_base64).bufferedReader().use{it.readText().trim()}; val bytes=Base64.decode(text,Base64.DEFAULT); brandLogo.setImageBitmap(BitmapFactory.decodeByteArray(bytes,0,bytes.size)) }.onFailure{brandLogo.visibility=View.GONE} }'
new_fun = '''private fun loadOfficialLogo(){ runCatching{\n        val text=resources.openRawResource(R.raw.logo_conecta_base64).bufferedReader().use{it.readText().trim()}\n        val bytes=Base64.decode(text,Base64.DEFAULT)\n        val src=BitmapFactory.decodeByteArray(bytes,0,bytes.size) ?: error("logo inválida")\n        val bmp=src.copy(android.graphics.Bitmap.Config.ARGB_8888,true)\n        val hsv=FloatArray(3)\n        for(y in 0 until bmp.height) for(x in 0 until bmp.width){\n            val c=bmp.getPixel(x,y)\n            android.graphics.Color.colorToHSV(c,hsv)\n            if(hsv[0] in 165f..255f && hsv[1] > 0.22f && hsv[2] > 0.18f) bmp.setPixel(x,y,android.graphics.Color.TRANSPARENT)\n        }\n        brandLogo.setImageBitmap(bmp)\n        brandLogo.visibility=View.VISIBLE\n    }.onFailure{brandLogo.setImageResource(R.drawable.logo_conecta_transparente);brandLogo.visibility=View.VISIBLE} }'''
if old_fun not in k:
    raise SystemExit('loadOfficialLogo exact functional method not found; refusing broad MainActivity edit')
k = k.replace(old_fun, new_fun, 1)
main.write_text(k, encoding='utf-8')

# 6) Version only.
g = gradle.read_text(encoding='utf-8')
g = g.replace('versionCode = 32', 'versionCode = 33')
g = g.replace('versionName = "0.10.2"', 'versionName = "0.10.3"')
if 'versionName = "0.10.3"' not in g:
    raise SystemExit('0.10.2 version markers not found')
gradle.write_text(g, encoding='utf-8')

print('0.10.3 visual patch applied: approved waves, transparent logo, tight code spacing, Wi-Fi vector; protocol untouched.')
