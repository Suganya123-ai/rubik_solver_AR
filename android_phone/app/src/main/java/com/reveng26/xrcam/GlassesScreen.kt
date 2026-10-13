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
 *
 * The glasses have two modes: 1920x1080 (one picture for both eyes) and
 * 3840x1080 (side-by-side 3D: the left half goes to the left eye, the right
 * half to the right eye). A page stretched across the wide mode shows each
 * eye a different half. So the normal mode is asked for, and if the glasses
 * stay in the wide mode the page is drawn twice, side by side: each eye then
 * sees the whole tutor.
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
        override fun onDisplayChanged(displayId: Int) {
            // A Presentation closes itself when its display changes size (e.g. the mode switch
            // asked for below, or the glasses going into / out of 3D mode): put the tutor back.
            main.post {
                if (presentation?.isShowing != true) {
                    presentation = null
                    show()
                }
            }
        }
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

    private fun url() = "http://$server/glasses/?camera=remote&display=glasses" + if (floatingOnly) "&hud=1" else ""

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

        private val webs = mutableListOf<WebView>()

        @SuppressLint("SetJavaScriptEnabled")
        private fun page(): WebView = WebView(context).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.mediaPlaybackRequiresUserGesture = false
            setBackgroundColor(Color.BLACK)
            webViewClient = object : WebViewClient() {
                // The laptop's certificate is one it made itself; accept it for this page.
                override fun onReceivedSslError(v: WebView, handler: SslErrorHandler, error: SslError) = handler.proceed()
            }
        }

        override fun onCreate(savedInstanceState: Bundle?) {
            super.onCreate(savedInstanceState)
            // Ask for the normal mode (one picture for both eyes), at its fastest refresh rate.
            val normal = display.supportedModes.filter { it.physicalWidth <= 1920 }.maxByOrNull { it.refreshRate }
            if (normal != null && display.mode.modeId != normal.modeId) {
                window?.let { w -> w.attributes = w.attributes.apply { preferredDisplayModeId = normal.modeId } }
                Log.d(TAG, "asked the glasses for mode " + normal.physicalWidth + "x" + normal.physicalHeight)
            }
            // Still in the side-by-side 3D mode (twice as wide): one copy of the tutor per eye.
            val wide = display.mode.physicalWidth >= 3 * display.mode.physicalHeight
            val row = android.widget.LinearLayout(context).apply { orientation = android.widget.LinearLayout.HORIZONTAL }
            repeat(if (wide) 2 else 1) {
                val view = page()
                row.addView(view, android.widget.LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.MATCH_PARENT, 1f))
                webs.add(view)
            }
            setContentView(row, ViewGroup.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT))
            Log.d(TAG, "glasses screen " + display.mode.physicalWidth + "x" + display.mode.physicalHeight + ": " + webs.size + " copy/copies of the tutor")
            webs.forEach { it.loadUrl(url) }
        }

        fun load(newUrl: String) { webs.forEach { it.loadUrl(newUrl) } }

        override fun onStop() {
            webs.forEach { it.destroy() }
            webs.clear()
            super.onStop()
        }
    }
}
