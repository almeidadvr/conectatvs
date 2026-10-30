from pathlib import Path

boot = Path('app/src/main/java/com/conectasolucoes/conectasign/BootReceiver.kt')
manifest = Path('app/src/main/AndroidManifest.xml')
gradle = Path('app/build.gradle.kts')

boot.write_text(r'''package com.conectasolucoes.conectasign

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.SystemClock

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        val action = intent?.action ?: return
        val supported = setOf(
            Intent.ACTION_BOOT_COMPLETED,
            Intent.ACTION_LOCKED_BOOT_COMPLETED,
            Intent.ACTION_MY_PACKAGE_REPLACED,
            "android.intent.action.QUICKBOOT_POWERON",
            "com.htc.intent.action.QUICKBOOT_POWERON"
        )
        if (action !in supported) return

        val launch = Intent(context, MainActivity::class.java).apply {
            addFlags(
                Intent.FLAG_ACTIVITY_NEW_TASK or
                    Intent.FLAG_ACTIVITY_CLEAR_TOP or
                    Intent.FLAG_ACTIVITY_SINGLE_TOP
            )
            putExtra("started_from_boot", true)
        }

        // 1) Tenta abrir imediatamente.
        runCatching { context.startActivity(launch) }

        // 2) Agenda uma segunda tentativa após o Android terminar de carregar a interface.
        runCatching {
            val pending = PendingIntent.getActivity(
                context,
                9701,
                launch,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
            )
            val alarm = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
            alarm.setAndAllowWhileIdle(
                AlarmManager.ELAPSED_REALTIME_WAKEUP,
                SystemClock.elapsedRealtime() + 15000L,
                pending
            )
        }
    }
}
''', encoding='utf-8')

m = manifest.read_text(encoding='utf-8')
if 'android:directBootAware="true"' not in m:
    m = m.replace(
        'android:name=".BootReceiver"\n            android:enabled="true"',
        'android:name=".BootReceiver"\n            android:directBootAware="true"\n            android:enabled="true"'
    )
manifest.write_text(m, encoding='utf-8')

g = gradle.read_text(encoding='utf-8')
g = g.replace('versionCode = 26', 'versionCode = 27')
g = g.replace('versionName = "0.9.6"', 'versionName = "0.9.7"')
gradle.write_text(g, encoding='utf-8')

print('Patch 0.9.7 aplicado: auto-start reforçado no boot sem alterar rede.')
