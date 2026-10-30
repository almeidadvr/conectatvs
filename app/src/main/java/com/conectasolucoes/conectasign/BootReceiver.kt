package com.conectasolucoes.conectasign

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

        // Primeira tentativa assim que o Android sinaliza o boot.
        runCatching { context.startActivity(launch) }

        // Segunda tentativa após a interface do TV Box terminar de carregar.
        runCatching {
            val pending = PendingIntent.getActivity(
                context,
                10010,
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
