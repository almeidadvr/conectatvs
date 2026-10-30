from pathlib import Path

main = Path('app/src/main/java/com/conectasolucoes/conectasign/MainActivity.kt')
manifest = Path('app/src/main/AndroidManifest.xml')
gradle = Path('app/build.gradle.kts')

s = main.read_text(encoding='utf-8')

# 0.9.0 - TV Box / digital signage: auto recuperação, soft-kiosk e boot resiliente.
if 'import android.app.AlarmManager' not in s:
    s = s.replace(
        'import android.graphics.BitmapFactory',
        'import android.app.AlarmManager\nimport android.app.PendingIntent\nimport android.content.Context\nimport android.content.Intent\nimport android.graphics.BitmapFactory'
    )
if 'import android.os.Process' not in s:
    s = s.replace('import android.os.SystemClock', 'import android.os.SystemClock\nimport android.os.Process')

# Instala um recovery handler antes de qualquer inicialização pesada.
needle = '''    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)'''
replacement = '''    override fun onCreate(savedInstanceState: Bundle?) {
        installCrashRecovery()
        super.onCreate(savedInstanceState)'''
if needle not in s:
    raise SystemExit('onCreate não encontrado para patch 0.9.0')
s = s.replace(needle, replacement, 1)

# Torna o modo imersivo persistente quando o foco volta à janela.
resume = '    override fun onResume() { super.onResume(); enterImmersive() }'
resume_new = '''    override fun onResume() {
        super.onResume()
        enterImmersive()
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) enterImmersive()
    }

    private fun installCrashRecovery() {
        val previous = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { thread, throwable ->
            runCatching {
                val restartIntent = Intent(applicationContext, MainActivity::class.java).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                    putExtra("recovered_after_crash", true)
                }
                val pending = PendingIntent.getActivity(
                    applicationContext,
                    9001,
                    restartIntent,
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
                )
                val alarm = getSystemService(Context.ALARM_SERVICE) as AlarmManager
                alarm.set(AlarmManager.ELAPSED_REALTIME_WAKEUP, SystemClock.elapsedRealtime() + 2000L, pending)
            }
            previous?.uncaughtException(thread, throwable) ?: run {
                Process.killProcess(Process.myPid())
                kotlin.system.exitProcess(10)
            }
        }
    }'''
if resume not in s:
    raise SystemExit('onResume não encontrado para patch 0.9.0')
s = s.replace(resume, resume_new, 1)

# Soft kiosk: BACK curto não encerra o player. BACK longo continua abrindo manutenção.
old_keys = '''    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_BACK && event?.isLongPress == true) { showServerSettings(); return true }
        return super.onKeyDown(keyCode, event)
    }'''
new_keys = '''    override fun onKeyDown(keyCode: Int, event: KeyEvent?): Boolean {
        if (keyCode == KeyEvent.KEYCODE_BACK) {
            if (event?.isLongPress == true) {
                showServerSettings()
                return true
            }
            // Digital signage: evita saída acidental do player.
            enterImmersive()
            return true
        }
        return super.onKeyDown(keyCode, event)
    }'''
if old_keys not in s:
    raise SystemExit('onKeyDown não encontrado para patch 0.9.0')
s = s.replace(old_keys, new_keys, 1)

main.write_text(s, encoding='utf-8')

m = manifest.read_text(encoding='utf-8')
m = m.replace(
    '<uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />',
    '<uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED" />\n    <uses-permission android:name="android.permission.WAKE_LOCK" />'
) if '<uses-permission android:name="android.permission.WAKE_LOCK" />' not in m else m

m = m.replace(
    'android:name=".MainActivity"\n            android:screenOrientation="landscape"',
    'android:name=".MainActivity"\n            android:launchMode="singleTask"\n            android:screenOrientation="landscape"'
)

old_receiver = '''        <receiver android:name=".BootReceiver" android:enabled="true" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED" />
            </intent-filter>
        </receiver>'''
new_receiver = '''        <receiver
            android:name=".BootReceiver"
            android:enabled="true"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED" />
                <action android:name="android.intent.action.LOCKED_BOOT_COMPLETED" />
                <action android:name="android.intent.action.MY_PACKAGE_REPLACED" />
                <action android:name="android.intent.action.QUICKBOOT_POWERON" />
                <action android:name="com.htc.intent.action.QUICKBOOT_POWERON" />
                <category android:name="android.intent.category.DEFAULT" />
            </intent-filter>
        </receiver>'''
if old_receiver not in m:
    raise SystemExit('BootReceiver não encontrado no manifest para patch 0.9.0')
m = m.replace(old_receiver, new_receiver, 1)
manifest.write_text(m, encoding='utf-8')

# BootReceiver resiliente a diferentes firmwares de TV Box.
boot = Path('app/src/main/java/com/conectasolucoes/conectasign/BootReceiver.kt')
boot.write_text('''package com.conectasolucoes.conectasign

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        val supported = setOf(
            Intent.ACTION_BOOT_COMPLETED,
            Intent.ACTION_LOCKED_BOOT_COMPLETED,
            Intent.ACTION_MY_PACKAGE_REPLACED,
            "android.intent.action.QUICKBOOT_POWERON",
            "com.htc.intent.action.QUICKBOOT_POWERON"
        )
        if (intent?.action !in supported) return

        val launch = Intent(context, MainActivity::class.java).apply {
            addFlags(
                Intent.FLAG_ACTIVITY_NEW_TASK or
                    Intent.FLAG_ACTIVITY_CLEAR_TOP or
                    Intent.FLAG_ACTIVITY_SINGLE_TOP
            )
            putExtra("started_from_boot", true)
        }
        runCatching { context.startActivity(launch) }
    }
}
''', encoding='utf-8')

# Versiona esta geração separadamente das versões anteriores.
g = gradle.read_text(encoding='utf-8')
g = g.replace('versionCode = 19', 'versionCode = 20')
g = g.replace('versionName = "0.8.8"', 'versionName = "0.9.0"')
gradle.write_text(g, encoding='utf-8')

print('Patch 0.9.0 TV Box / auto-start / soft-kiosk aplicado.')
