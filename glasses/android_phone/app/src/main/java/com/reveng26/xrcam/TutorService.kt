package com.reveng26.xrcam

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder

/**
 * Keeps the app at foreground priority while the tutor runs.
 *
 * With the glasses plugged in, XREAL's own app takes the front of the screen
 * stack, and Android then treats this app as "in the background": on the Beam
 * Pro that limits it to the 4 slow processor cores, and finding the cube took
 * 250-530 ms instead of 27. A foreground service (the notification "Cube
 * Tutor is running") lets it use all 8 cores. It does no work itself.
 */
class TutorService : Service() {

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.createNotificationChannel(NotificationChannel("tutor", "Cube Tutor", NotificationManager.IMPORTANCE_LOW))
        val notification = Notification.Builder(this, "tutor")
            .setContentTitle("Cube Tutor is running")
            .setSmallIcon(android.R.drawable.ic_menu_camera)
            .setOngoing(true)
            .build()
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(1, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        } else {
            startForeground(1, notification)
        }
        return START_NOT_STICKY
    }
}
