package com.reveng26.xrcam

import android.content.Context
import android.graphics.Bitmap
import android.os.Handler
import android.os.HandlerThread
import android.os.Looper
import android.util.Log
import android.media.Image
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer

/**
 * The whole tutor on the phone: no laptop, no network.
 *
 * For each camera frame, on its own thread:
 *   1. a window of the glasses' wide camera picture is cut out (640x472),
 *   2. the cube finder (CubeFinder, ONNX Runtime) gives the 7 corner points,
 *   3. the tutor's Python code (vision/phone.py, through Chaquopy) reads the
 *      colours and runs the scan / the move tracking,
 *   4. the result goes to the tutor page(s) through LocalServer.
 *
 * The glasses' camera is wide-angle (2048x1512): shrunk whole to 640 wide, a
 * cube held at arm's length is only ~120 pixels across, so a window is cut
 * out at [zoom]x instead. The window follows the cube: when the cube drifts
 * toward the window's edge the window moves onto it; while the cube is not
 * found the window stays where it was, and after a few seconds returns to its
 * usual place a little below the middle of the view (hands are low).
 */
class TutorEngine(
    private val context: Context,
    private val onStatus: (String) -> Unit,
) {
    companion object {
        private const val TAG = "TutorEngine"

        /** The engine that is running now (at most one): the page's commands go to it. */
        @Volatile private var active: TutorEngine? = null
        private var shared: LocalServer? = null

        /**
         * One page server for the whole app, started once and kept: a second tutor screen opened
         * while the last one was still closing used to crash on the port being taken.
         */
        fun startServer(context: Context) { server(context) }

        @Synchronized private fun server(context: Context): LocalServer = shared ?: LocalServer(context.applicationContext, PORT) { text ->
            active?.command(text)
        }.also {
            it.start(0, true)   // 0: connections never time out (the page's link is quiet between commands)
            shared = it
        }
        const val PORT = 5273
        const val WIDTH = 640
        const val HEIGHT = 472          // the camera is 2048x1512
        private const val QUALITY = 60
        private const val HOME_X = 0.50f
        private const val HOME_Y = 0.58f
        private const val HOME_AFTER_MS = 4000L      // no cube for this long: go back there, once
        private const val EDGE = 0.22f               // the cube this far from the window's middle: re-centre on it
    }

    private val main = Handler(Looper.getMainLooper())
    private val thread = HandlerThread("Tutor").also { it.start() }
    private val work = Handler(thread.looper)
    private val bitmap = Bitmap.createBitmap(WIDTH, HEIGHT, Bitmap.Config.ARGB_8888)
    private val bytes = ByteArray(WIDTH * HEIGHT * 4)
    private val argb = IntArray(WIDTH * HEIGHT)
    private val columns = IntArray(WIDTH)
    private var yPlane = ByteArray(0)
    private var uPlane = ByteArray(0)
    private var vPlane = ByteArray(0)
    private var lastSaved = 0L
    @Volatile private var running = false

    /** 1 = the whole view; 2 = the middle half, twice as large; 3 = the middle third. */
    @Volatile var zoom = 2
        set(value) { field = value.coerceIn(1, 3) }
    private var windowX = HOME_X
    private var windowY = HOME_Y
    private var sentX = windowX
    private var sentY = windowY
    private var sentZoom = 2
    private var lastFound = 0L

    private var finder: CubeFinder? = null
    private var session: PyObject? = null
    private val pythonLock = Any()   // one frame or command in the Python code at a time
    private val server = server(context)

    private fun command(text: String): String? = synchronized(pythonLock) { session?.callAttr("command", text)?.toString() }

    // What is reported on the phone's status line.
    private var frames = 0
    private var foundFrames = 0
    private var copyMs = 0L
    private var findMs = 0L
    private var pythonMs = 0L
    private var since = 0L

    fun start() {
        running = true
        active = this
        onStatus("Starting the tutor…")
        work.post {
            try {
                if (!Python.isStarted()) Python.start(AndroidPlatform(context.applicationContext))
                session = Python.getInstance().getModule("vision.phone").callAttr("PhoneSession")
                finder = CubeFinder(context)
                since = System.currentTimeMillis()
                next()
            } catch (e: Throwable) {
                Log.e(TAG, "could not start", e)
                onStatus("Could not start: ${e.message}")
            }
        }
    }

    fun stop() {
        running = false
        main.removeCallbacksAndMessages(null)
        work.removeCallbacksAndMessages(null)
        if (active === this) active = null
        server.feeding = false
        work.post {
            finder?.close()
            thread.quitSafely()
        }
    }

    @Volatile private var wantPicture = false

    /** Ready for the next picture: [offer] fills it in from the decoder. */
    private fun next() {
        if (!running) return
        wantPicture = true
        work.postDelayed(noPicture, 1500)
    }

    private val noPicture = Runnable { if (wantPicture) server.feeding = false }

    /**
     * A decoded camera picture (full size, YUV), from the decoder's thread. Taken only when the
     * tutor is ready for one (the others are skipped, so it never falls behind); the window is cut
     * out right here, and the rest runs on the tutor's thread. The picture comes straight from the
     * decoder, not from a view on the screen: XREAL's own app covers this app's screen while the
     * glasses are in use, and a covered view stops updating.
     */
    fun offer(image: Image) {
        if (!running || !wantPicture) return
        wantPicture = false
        work.removeCallbacks(noPicture)
        val started = System.nanoTime()
        cutWindow(image)
        work.post { process(started) }
    }

    /**
     * Cuts the window out of the decoder's full-size picture into [bitmap] (640x472), converting
     * from the decoder's YUV (BT.601, full range: what the glasses' camera sends) to RGB.
     */
    private fun cutWindow(image: Image) {
        val z = zoom
        sentZoom = z
        val iw = image.width
        val ih = image.height
        val w = iw / z
        val h = ih / z
        val x = (windowX * iw - w / 2f).toInt().coerceIn(0, iw - w)   // keep the window inside the picture
        val y = (windowY * ih - h / 2f).toInt().coerceIn(0, ih - h)
        sentX = (x + w / 2f) / iw
        sentY = (y + h / 2f) / ih
        val planes = image.planes
        yPlane = copy(planes[0].buffer, yPlane)
        uPlane = copy(planes[1].buffer, uPlane)
        vPlane = copy(planes[2].buffer, vPlane)
        val yRow = planes[0].rowStride
        val yStep = planes[0].pixelStride
        val uvRow = planes[1].rowStride
        val uvStep = planes[1].pixelStride
        for (ox in 0 until WIDTH) columns[ox] = x + ox * w / WIDTH
        var i = 0
        for (oy in 0 until HEIGHT) {
            val sy = y + oy * h / HEIGHT
            val yLine = sy * yRow
            val uvLine = (sy shr 1) * uvRow
            for (ox in 0 until WIDTH) {
                val sx = columns[ox]
                val luma = yPlane[yLine + sx * yStep].toInt() and 0xFF
                val uv = uvLine + (sx shr 1) * uvStep
                val u = (uPlane[uv].toInt() and 0xFF) - 128
                val v = (vPlane[uv].toInt() and 0xFF) - 128
                val r = (luma + ((359 * v) shr 8)).coerceIn(0, 255)
                val g = (luma - ((88 * u + 183 * v) shr 8)).coerceIn(0, 255)
                val b = (luma + ((454 * u) shr 8)).coerceIn(0, 255)
                argb[i++] = (0xFF shl 24) or (r shl 16) or (g shl 8) or b
            }
        }
        bitmap.setPixels(argb, 0, WIDTH, 0, 0, WIDTH, HEIGHT)
    }

    private fun copy(buffer: java.nio.ByteBuffer, into: ByteArray): ByteArray {
        buffer.rewind()
        val out = if (into.size >= buffer.remaining()) into else ByteArray(buffer.remaining())
        buffer.get(out, 0, buffer.remaining())
        return out
    }

    private fun process(started: Long) {
        if (!running) return
        try {
            val copied = System.nanoTime()
            val found = finder!!.find(bitmap)
            val looked = System.nanoTime()
            bitmap.copyPixelsToBuffer(ByteBuffer.wrap(bytes))
            val reply = synchronized(pythonLock) {
                session!!.callAttr("frame", bytes, WIDTH, HEIGHT, found?.points, found?.confidence ?: 0f).toString()
            }
            val done = System.nanoTime()
            server.feeding = true
            server.broadcast(reply)
            if (server.wantsPicture) {
                val out = ByteArrayOutputStream(48 * 1024)
                bitmap.compress(Bitmap.CompressFormat.JPEG, QUALITY, out)
                server.picture(out.toByteArray())
            }
            follow(found)
            if (System.currentTimeMillis() - lastSaved > 3000) {   // the latest picture, for checking (adb: run-as ... cat files/last.jpg)
                lastSaved = System.currentTimeMillis()
                java.io.File(context.filesDir, "last.jpg").outputStream().use { bitmap.compress(Bitmap.CompressFormat.JPEG, 80, it) }
            }
            frames++
            if (found != null) foundFrames++
            copyMs += (copied - started) / 1_000_000
            findMs += (looked - copied) / 1_000_000
            pythonMs += (done - looked) / 1_000_000
            val now = System.currentTimeMillis()
            if (now - since >= 2000) {
                val status = "%.0f frames/s · cube in %d of %d · copy %d, find %d, tutor %d ms".format(
                    frames * 1000.0 / (now - since), foundFrames, frames, copyMs / frames, findMs / frames, pythonMs / frames)
                val group = try { java.io.File("/proc/self/cpuset").readText().trim() } catch (_: Exception) { "?" }
                Log.i(TAG, "$status · $group")
                onStatus(status)
                since = now; frames = 0; foundFrames = 0; copyMs = 0; findMs = 0; pythonMs = 0
            }
        } catch (e: Throwable) {
            Log.e(TAG, "frame failed", e)
            onStatus("Error: ${e.message}")
            work.postDelayed({ next() }, 500)
            return
        }
        next()
    }

    /** Keeps the window on the cube. */
    private fun follow(found: CubeFinder.Found?) {
        val now = System.currentTimeMillis()
        if (found != null && found.confidence >= 0.5f) {
            lastFound = now
            var x0 = Float.MAX_VALUE; var y0 = Float.MAX_VALUE; var x1 = -Float.MAX_VALUE; var y1 = -Float.MAX_VALUE
            for (i in 0 until 7) {
                x0 = minOf(x0, found.points[2 * i]); x1 = maxOf(x1, found.points[2 * i])
                y0 = minOf(y0, found.points[2 * i + 1]); y1 = maxOf(y1, found.points[2 * i + 1])
            }
            val z = sentZoom.toFloat()
            // The cube's place in the whole view: the window's middle plus its place inside the window.
            val cubeX = sentX + ((x0 + x1) / 2 / WIDTH - 0.5f) / z
            val cubeY = sentY + ((y0 + y1) / 2 / HEIGHT - 0.5f) / z
            // Only move when the cube nears the edge: a window that moved every frame would make a
            // cube held still look as if it were moving.
            if (kotlin.math.abs((cubeX - windowX) * z) > EDGE || kotlin.math.abs((cubeY - windowY) * z) > EDGE) {
                windowX = cubeX
                windowY = cubeY
            }
        } else if (now - lastFound > HOME_AFTER_MS) {
            windowX = HOME_X
            windowY = HOME_Y
        }
    }
}
