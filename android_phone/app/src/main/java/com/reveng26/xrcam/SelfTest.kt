package com.reveng26.xrcam

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.util.Log
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.nio.ByteBuffer

/**
 * Tries every part of the phone-only tutor without the glasses, on a saved
 * picture, and writes the timings to the log (tag SelfTest):
 *
 *   adb shell "run-as com.cubetutor.phone sh -c 'cat > files/test.jpg'" < some_frame.jpg
 *   adb shell am start -n com.cubetutor.phone/com.reveng26.xrcam.MainActivity --ez selftest true
 *   adb logcat -s SelfTest
 */
object SelfTest {
    private const val TAG = "SelfTest"

    fun run(context: Context) {
        try {
            var t = System.nanoTime()
            fun lap(): Long { val now = System.nanoTime(); val ms = (now - t) / 1_000_000; t = now; return ms }

            if (!Python.isStarted()) Python.start(AndroidPlatform(context.applicationContext))
            val module = Python.getInstance().getModule("vision.phone")
            val session = module.callAttr("PhoneSession")
            Log.i(TAG, "python started and tutor loaded in ${lap()} ms")
            Log.i(TAG, "solver: " + module.callAttr("self_check").toString())
            lap()
            val finder = CubeFinder(context)
            Log.i(TAG, "cube finder loaded in ${lap()} ms")

            val file = File(context.filesDir, "test.jpg")
            val picture = if (file.isFile) BitmapFactory.decodeFile(file.path) else null
            val frame = Bitmap.createBitmap(TutorEngine.WIDTH, TutorEngine.HEIGHT, Bitmap.Config.ARGB_8888)
            if (picture != null) {
                android.graphics.Canvas(frame).drawBitmap(picture, null,
                    android.graphics.Rect(0, 0, frame.width, frame.height), null)
            } else {
                Log.w(TAG, "no files/test.jpg: timing on an empty picture (no cube to find)")
            }
            val bytes = ByteArray(frame.width * frame.height * 4)
            session.callAttr("command", """{"type":"scan_start"}""")
            var findMs = 0L; var tutorMs = 0L; var found: CubeFinder.Found? = null; var reply = ""
            val rounds = 40
            for (i in 0 until rounds + 5) {
                if (i == 5) { findMs = 0; tutorMs = 0 }   // the first few are slower (warming up)
                lap()
                found = finder.find(frame)
                findMs += lap()
                frame.copyPixelsToBuffer(ByteBuffer.wrap(bytes))
                reply = session.callAttr("frame", bytes, frame.width, frame.height, found?.points, found?.confidence ?: 0f).toString()
                tutorMs += lap()
            }
            Log.i(TAG, "per frame: find ${findMs / rounds} ms, tutor ${tutorMs / rounds} ms" +
                " -> about ${1000 * rounds / (findMs + tutorMs).coerceAtLeast(1)} frames/s (without the camera)")
            Log.i(TAG, "cube: " + (found?.let { "confidence %.2f, corners %s".format(it.confidence, it.points.joinToString(" ") { p -> "%.0f".format(p) }) } ?: "not found"))
            Log.i(TAG, "reply: " + reply.take(300))
            Log.i(TAG, "scan: " + reply.substringAfter("\"scan\":", "none").take(300))

            val server = LocalServer(context, TutorEngine.PORT + 1) { text -> session.callAttr("command", text)?.toString() }
            server.start(0, true)
            val page = URL("http://127.0.0.1:${TutorEngine.PORT + 1}/glasses/").openConnection() as HttpURLConnection
            Log.i(TAG, "page: HTTP ${page.responseCode}, ${page.inputStream.use { it.readBytes().size }} bytes")
            server.stop()
            finder.close()
            // Every other model file pushed to files/ (name_SIZE.onnx), to compare sizes.
            val candidates = (context.filesDir.listFiles { f -> f.name.endsWith(".onnx") } ?: arrayOf()).sortedBy { it.name }
            for (file in candidates) {
                try {
                    val size = Regex("_(\\d+)").find(file.name)!!.groupValues[1].toInt()
                    val f = CubeFinder(context, file, size)
                    repeat(4) { f.find(frame) }
                    f.prepareNs = 0; f.modelNs = 0; f.runs = 0
                    var last: CubeFinder.Found? = null
                    repeat(20) { last = f.find(frame) }
                    Log.i(TAG, "%s: prepare %.1f ms, model %.1f ms per run, confidence %.2f".format(file.name,
                        f.prepareNs / 1e6 / f.runs, f.modelNs / 1e6 / f.runs, last?.confidence ?: 0f))
                    f.close()
                } catch (e: Throwable) {
                    Log.w(TAG, "${file.name} failed: ${e.message}")
                }
            }
            Log.i(TAG, "done")
        } catch (e: Throwable) {
            Log.e(TAG, "failed", e)
        }
    }
}
