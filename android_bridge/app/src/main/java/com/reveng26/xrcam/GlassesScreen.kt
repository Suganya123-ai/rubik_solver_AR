package com.reveng26.xrcam

import android.annotation.SuppressLint
import android.app.Presentation
import android.content.Context
import android.graphics.Color
import android.hardware.display.DisplayManager
import android.net.http.SslError
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.Display
import android.view.ViewGroup
import android.view.WindowManager
import android.webkit.SslErrorHandler
import android.webkit.WebView
import android.webkit.WebViewClient

/**
 * Puts the tutor on the glasses' own screen.
 *
 * The Beam Pro treats the glasses as a second display, not a mirror of the
 * phone, so an app only appears there if it puts something there on purpose.
 * Android's Presentation does exactly that. The page is opened in its
 * "glasses screen" form: no buttons (the glasses can't be touched; the phone
 * keeps the buttons) and, by default, no camera picture on a black ground --
 * black is invisible on see-through glasses, so the ghost cube and the
 * instruction float in view.
 *
 * The display can go away and come back (the glasses reconnect when their
 * camera is switched on), so this follows displays being added and removed.
 */
class GlassesScreen(private val context: Context, private val server: String) {

    companion object { private const val TAG = "GlassesScreen" }

    private val displays = context.getSystemService(Context.DISPLAY_SERVICE) as DisplayManager
    private val main = Handler(Looper.getMainLooper())
    private var presentation: TutorPresentation? = null
    /** true: only the ghost cube and instructions; false: the camera picture with the arrows too. */
    var floatingOnly = true
        set(value) { field = value; presentation?.load(url()) }

    var onChange: (showing: Boolean) -> Unit = {}

    private val listener = object : DisplayManager.DisplayListener {
        override fun onDisplayAdded(displayId: Int) = main.post { show() }.let {}
        override fun onDisplayRemoved(displayId: Int) {
            if (presentation?.display?.displayId == displayId) main.post { hide(); show() }
        }
        override fun onDisplayChanged(displayId: Int) {}
    }

    fun start() {
        displays.registerDisplayListener(listener, main)
        show()
    }

    fun stop() {
        displays.unregisterDisplayListener(listener)
        hide()
    }

    val showing: Boolean get() = presentation != null

    private fun url() = "https://$server/glasses/?camera=remote&display=glasses" + if (floatingOnly) "&hud=1" else ""

    private fun show() {
        if (presentation != null) return
        val display = displays.getDisplays(DisplayManager.DISPLAY_CATEGORY_PRESENTATION).firstOrNull() ?: run {
            onChange(false)
            return
        }
        try {
            presentation = TutorPresentation(context, display, url()).also { it.show() }
            Log.d(TAG, "tutor shown on display ${display.displayId} (${display.name})")
            onChange(true)
        } catch (e: WindowManager.InvalidDisplayException) {  // the display went away while we were opening it
            Log.w(TAG, "glasses display not usable: ${e.message}")
            presentation = null
            onChange(false)
        }
    }

    private fun hide() {
        try { presentation?.dismiss() } catch (_: Exception) {}
        presentation = null
        onChange(false)
    }

    private class TutorPresentation(context: Context, display: Display, private val url: String) :
        Presentation(context, display) {

        private var web: WebView? = null

        @SuppressLint("SetJavaScriptEnabled")
        override fun onCreate(savedInstanceState: Bundle?) {
            super.onCreate(savedInstanceState)
            val view = WebView(context).apply {
                settings.javaScriptEnabled = true
                settings.domStorageEnabled = true
                settings.mediaPlaybackRequiresUserGesture = false
                setBackgroundColor(Color.BLACK)
                webViewClient = object : WebViewClient() {
                    // The laptop's certificate is one it made itself; accept it for this page.
                    override fun onReceivedSslError(v: WebView, handler: SslErrorHandler, error: SslError) = handler.proceed()
                }
            }
            setContentView(view, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
            web = view
            view.loadUrl(url)
        }

        fun load(newUrl: String) { web?.loadUrl(newUrl) }

        override fun onStop() {
            web?.destroy()
            web = null
            super.onStop()
        }
    }
}
