package com.reveng26.xrcam

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Rect
import android.os.Handler
import android.os.HandlerThread
import android.os.Looper
import android.util.Log
import android.view.PixelCopy
import android.view.Surface
import android.view.TextureView
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer

/**
 * The whole tutor on the phone: no laptop, no network.
 *
 * For each camera frame, on its own thread:
 *   1. a window of the glasses' wide camera picture is copied out (640x472),
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
    private val picture: TextureView,
    /** The surface the decoder draws into (the picture at full size). */
    private val surface: () -> Surface?,
    private val onStatus: (String) -> Unit,
) {
    companion object {
        private const val TAG = "TutorEngine"
        const val PORT = 5273
        const val WIDTH = 640
        const val HEIGHT = 472          // the camera is 2048x1512
        private const val VIDEO_WIDTH = 2048
        private const val VIDEO_HEIGHT = 1512
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
    private var full: Bitmap? = null
    @Volatile private var fastCopy = true
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
    val server = LocalServer(context, PORT) { text ->
        synchronized(pythonLock) { session?.callAttr("command", text)?.toString() }
    }

    // What is reported on the phone's status line.
    private var frames = 0
    private var foundFrames = 0
    private var copyMs = 0L
    private var findMs = 0L
    private var pythonMs = 0L
    private var since = 0L

    fun start() {
        running = true
        server.start(0, true)   // 0: connections never time out (the page's link is quiet between commands)
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
        server.stop()
        work.post {
            finder?.close()
            thread.quitSafely()
        }
    }

    /** Takes the next picture, then [process] runs on the tutor thread. */
    private fun next() {
        if (!running) return
        val started = System.nanoTime()
        val source = surface()
        val z = zoom
        sentZoom = z
        if (source == null || !source.isValid || !picture.isAvailable) {   // the decoder hasn't drawn anything yet
            server.feeding = false
            work.postDelayed({ next() }, 200)
            return
        }
        if (!fastCopy) {
            main.post {   // reading through the view has to happen on the main thread
                if (!running) return@post
                grabSlow(z)
                work.post { process(started) }
            }
            return
        }
        // Only the window is copied out of the decoder's full-size picture, already shrunk to the
        // size that is used: the graphics chip does it.
        val w = VIDEO_WIDTH / z
        val h = VIDEO_HEIGHT / z
        val x = (windowX * VIDEO_WIDTH - w / 2f).toInt().coerceIn(0, VIDEO_WIDTH - w)   // keep the window inside the picture
        val y = (windowY * VIDEO_HEIGHT - h / 2f).toInt().coerceIn(0, VIDEO_HEIGHT - h)
        sentX = (x + w / 2f) / VIDEO_WIDTH
        sentY = (y + h / 2f) / VIDEO_HEIGHT
        try {
            PixelCopy.request(source, Rect(x, y, x + w, y + h), bitmap, { result ->
                if (result == PixelCopy.SUCCESS) {
                    process(started)
                } else {  // not supported for this surface: read through the view from now on
                    Log.w(TAG, "fast copy failed ($result), using the slow way")
                    fastCopy = false
                    next()
                }
            }, work)
        } catch (e: Exception) {
            Log.w(TAG, "fast copy refused, using the slow way", e)
            fastCopy = false
            work.post { next() }
        }
    }

    /** The window read through the view: the picture z times larger, then its window cut out. */
    private fun grabSlow(z: Int) {
        if (z == 1) {
            picture.getBitmap(bitmap)
            sentX = 0.5f; sentY = 0.5f
            return
        }
        var big = full
        if (big == null || big.width != WIDTH * z) {
            big?.recycle()
            big = Bitmap.createBitmap(WIDTH * z, HEIGHT * z, Bitmap.Config.ARGB_8888)
            full = big
        }
        picture.getBitmap(big)
        val x = (windowX * big.width - WIDTH / 2f).toInt().coerceIn(0, big.width - WIDTH)
        val y = (windowY * big.height - HEIGHT / 2f).toInt().coerceIn(0, big.height - HEIGHT)
        Canvas(bitmap).drawBitmap(big, Rect(x, y, x + WIDTH, y + HEIGHT), Rect(0, 0, WIDTH, HEIGHT), null)
        sentX = (x + WIDTH / 2f) / big.width
        sentY = (y + HEIGHT / 2f) / big.height
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
            frames++
            if (found != null) foundFrames++
            copyMs += (copied - started) / 1_000_000
            findMs += (looked - copied) / 1_000_000
            pythonMs += (done - looked) / 1_000_000
            val now = System.currentTimeMillis()
            if (now - since >= 2000) {
                val status = "%.0f frames/s · cube in %d of %d · copy %d, find %d, tutor %d ms".format(
                    frames * 1000.0 / (now - since), foundFrames, frames, copyMs / frames, findMs / frames, pythonMs / frames)
                Log.i(TAG, status)
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
