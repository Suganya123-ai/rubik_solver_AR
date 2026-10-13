package com.reveng26.xrcam

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Rect
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.TextureView
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString.Companion.toByteString
import java.io.ByteArrayOutputStream
import java.security.SecureRandom
import java.security.cert.X509Certificate
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import javax.net.ssl.SSLContext
import javax.net.ssl.X509TrustManager

/**
 * Sends the camera picture to the Cube Tutor server on the laptop.
 *
 * Takes the picture the decoder is already drawing (the TextureView) and uploads
 * the middle of it as JPEG over a WebSocket (/ws/feed: 4-byte frame number +
 * JPEG). The glasses' camera is wide-angle (2048x1512): shrunk whole to 640
 * wide, a cube held at arm's length is only ~120 pixels across and the cube
 * finder misses it, so a window is cut out at [zoom]x instead (sharp, because
 * it comes from the full-size picture).
 *
 * The window follows the cube: the server says where the cube is in each
 * frame, and when it drifts toward the window's edge the window moves onto it.
 * While the cube is not found the window stays still, where the cube last was,
 * and after a few seconds returns to its usual place a little below the
 * middle of the view (hands are usually lower than the middle). One frame is in flight at a time: the next is sent when the server
 * has answered, so a slow network never builds a queue.
 *
 * The server uses a certificate it made itself (browsers only allow cameras on
 * https), so the certificate is accepted without checking. This app only talks
 * to the address the user typed, on their own network.
 */
class FrameUploader(
    private val picture: TextureView,
    private val address: String,
    private val onStatus: (String) -> Unit,
) {
    companion object {
        private const val TAG = "FrameUploader"
        const val WIDTH = 640
        const val HEIGHT = 472          // the camera is 2048x1512
        private const val QUALITY = 70
        private const val REPLY_TIMEOUT_MS = 2500L
        /** Where the window sits when there is no cube to follow: a little below the middle (hands are low). */
        private const val HOME_X = 0.50f
        private const val HOME_Y = 0.58f
        private const val HOME_AFTER_MS = 4000L      // no cube for this long: go back there, once
        private const val EDGE = 0.22f               // the cube this far from the window's middle: re-centre on it
    }

    private val main = Handler(Looper.getMainLooper())
    private val worker = Executors.newSingleThreadExecutor()
    private val bitmap = Bitmap.createBitmap(WIDTH, HEIGHT, Bitmap.Config.ARGB_8888)
    private var full: Bitmap? = null
    /** 1 = the whole view; 2 = the middle half, twice as large; 3 = the middle third. */
    @Volatile var zoom = 2
        set(value) { field = value.coerceIn(1, 3) }

    // Where the window is: its centre, as a fraction of the camera's view.
    @Volatile private var windowX = HOME_X
    @Volatile private var windowY = HOME_Y
    // The window as it was for the frame now with the server (to place the cube it reports).
    private var sentX = windowX
    private var sentY = windowY
    private var sentZoom = 2
    private var lastFound = 0L
    private val client: OkHttpClient
    private var socket: WebSocket? = null
    @Volatile private var running = false
    @Volatile private var waitingSince = 0L
    private var frameId = 0
    private var sent = 0
    private var windowStart = 0L
    private var lastRoundTrip = 0L

    init {
        val trustAll = object : X509TrustManager {
            override fun checkClientTrusted(chain: Array<X509Certificate>, authType: String) {}
            override fun checkServerTrusted(chain: Array<X509Certificate>, authType: String) {}
            override fun getAcceptedIssuers(): Array<X509Certificate> = arrayOf()
        }
        val ssl = SSLContext.getInstance("TLS").apply { init(null, arrayOf(trustAll), SecureRandom()) }
        client = OkHttpClient.Builder()
            .sslSocketFactory(ssl.socketFactory, trustAll)
            .hostnameVerifier { _, _ -> true }
            .connectTimeout(5, TimeUnit.SECONDS)
            .pingInterval(10, TimeUnit.SECONDS)
            .build()
    }

    fun start() {
        running = true
        connect()
        main.postDelayed(watchdog, 1000)
    }

    fun stop() {
        running = false
        main.removeCallbacksAndMessages(null)
        socket?.close(1000, null)
        socket = null
        worker.shutdown()
    }

    private fun connect() {
        if (!running) return
        onStatus("Connecting to $address…")
        socket = client.newWebSocket(Request.Builder().url("wss://$address/ws/feed").build(), listener)
    }

    private val listener = object : WebSocketListener() {
        override fun onOpen(webSocket: WebSocket, response: Response) {
            onStatus("Connected to the laptop")
            windowStart = System.currentTimeMillis()
            sent = 0
            sendNext()
        }

        override fun onMessage(webSocket: WebSocket, text: String) {  // the server finished that frame
            follow(text)
            lastRoundTrip = System.currentTimeMillis() - waitingSince
            waitingSince = 0
            sent++
            val now = System.currentTimeMillis()
            if (now - windowStart >= 2000) {
                onStatus("Sending %.0f frames/s · %d ms".format(sent * 1000.0 / (now - windowStart), lastRoundTrip))
                windowStart = now
                sent = 0
            }
            sendNext()
        }

        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
            Log.w(TAG, "connection failed: ${t.message}")
            onStatus("Can't reach $address (${t.message ?: t.javaClass.simpleName}) — retrying")
            waitingSince = 0
            main.postDelayed({ connect() }, 2000)
        }

        override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
            waitingSince = 0
            main.postDelayed({ connect() }, 2000)
        }
    }

    /** Keeps the window on the cube (from the server's reply). */
    private fun follow(reply: String) {
        val now = System.currentTimeMillis()
        try {
            val json = org.json.JSONObject(reply)
            if (json.optBoolean("found") && json.has("cx")) {
                lastFound = now
                val z = sentZoom.toFloat()
                // The cube's place in the whole view: the window's corner plus its place inside the window.
                val cubeX = sentX + (json.getDouble("cx").toFloat() - 0.5f) / z
                val cubeY = sentY + (json.getDouble("cy").toFloat() - 0.5f) / z
                val offX = (cubeX - windowX) * z
                val offY = (cubeY - windowY) * z
                // Only move when the cube nears the edge: a window that moved every frame would
                // make a cube held still look as if it were moving.
                if (kotlin.math.abs(offX) > EDGE || kotlin.math.abs(offY) > EDGE) {
                    windowX = cubeX
                    windowY = cubeY
                }
                return
            }
        } catch (_: Exception) { /* a reply that isn't a frame result */ }
        // Not found: stay where the cube last was (hands come back to the same place). Only after a
        // while go back to the usual place, in one step. (An earlier version looked around the
        // view for the cube, which made the picture jump from corner to corner.)
        if (now - lastFound > HOME_AFTER_MS) {
            windowX = HOME_X
            windowY = HOME_Y
        }
    }

    /** Grabs the current picture (must be on the main thread), then encodes and sends it off the main thread. */
    private fun sendNext() {
        if (!running) return
        main.post {
            if (!running) return@post
            if (!picture.isAvailable) {  // the decoder hasn't drawn anything yet
                main.postDelayed({ sendNext() }, 200)
                return@post
            }
            val z = zoom
            if (z == 1) {
                picture.getBitmap(bitmap)
            } else {  // read the picture z times larger, keep its middle
                var big = full
                if (big == null || big.width != WIDTH * z) {
                    big?.recycle()
                    big = Bitmap.createBitmap(WIDTH * z, HEIGHT * z, Bitmap.Config.ARGB_8888)
                    full = big
                }
                picture.getBitmap(big)
                // The window, kept inside the picture.
                val x = (windowX * big.width - WIDTH / 2f).toInt().coerceIn(0, big.width - WIDTH)
                val y = (windowY * big.height - HEIGHT / 2f).toInt().coerceIn(0, big.height - HEIGHT)
                Canvas(bitmap).drawBitmap(big, Rect(x, y, x + WIDTH, y + HEIGHT), Rect(0, 0, WIDTH, HEIGHT), null)
                sentX = (x + WIDTH / 2f) / big.width
                sentY = (y + HEIGHT / 2f) / big.height
            }
            sentZoom = z
            if (z == 1) { sentX = 0.5f; sentY = 0.5f }
            worker.execute {
                try {
                    val out = ByteArrayOutputStream(48 * 1024)
                    val id = ++frameId
                    out.write(byteArrayOf((id ushr 24).toByte(), (id ushr 16).toByte(), (id ushr 8).toByte(), id.toByte()))
                    bitmap.compress(Bitmap.CompressFormat.JPEG, QUALITY, out)
                    waitingSince = System.currentTimeMillis()
                    if (socket?.send(out.toByteArray().toByteString()) != true) waitingSince = 0
                } catch (e: Exception) {
                    Log.w(TAG, "send failed", e)
                    waitingSince = 0
                }
            }
        }
    }

    /** If a reply never comes (a dropped packet), carry on with a fresh frame. */
    private val watchdog = object : Runnable {
        override fun run() {
            if (!running) return
            val since = waitingSince
            if (since != 0L && System.currentTimeMillis() - since > REPLY_TIMEOUT_MS) {
                waitingSince = 0
                sendNext()
            }
            main.postDelayed(this, 1000)
        }
    }
}
