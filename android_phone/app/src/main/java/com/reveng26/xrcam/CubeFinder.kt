package com.reveng26.xrcam

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import android.content.Context
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Rect
import android.graphics.RectF
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.FloatBuffer

/**
 * Finds the cube and its 7 corner points in a picture, on the phone.
 *
 * The same model the laptop uses (models/cube_pose_v3.pt), converted to ONNX
 * at 256x256 (models/cube_pose_v3_256.onnx; the size is read from the file)
 * and run by ONNX Runtime. At that size it takes a sixth of the work of the
 * laptop's 640, but its corner points are too coarse on a whole frame. So it looks twice as closely where it matters: once the cube has
 * been found, only a square around it is given to the model, where the cube
 * fills the picture (as it did in the model's training pictures) and the
 * corners come out sharp. The whole frame is searched only when the cube is
 * not being followed.
 */
class CubeFinder(
    context: Context,
    /** Another model file to try instead of the bundled one (SelfTest). */
    modelFile: java.io.File? = null,
) {

    class Found(val points: FloatArray, val confidence: Float)   // 7 corners: x0, y0, x1, y1, ...

    companion object {
        const val DEFAULT_MODEL = "cube_pose_v3_256.onnx"
        /** files/finder.txt as key=value pairs (empty if there is none). */
        fun tuning(context: Context): Map<String, String> = try {
            java.io.File(context.filesDir, "finder.txt").readText().split(Regex("\\s+")).filter { "=" in it }
                .associate { it.substringBefore("=") to it.substringAfter("=") }
        } catch (_: Exception) { emptyMap() }
        private const val KEEP = 0.5f      // keep following the cube while the model is at least this sure
        private const val MIN = 0.25f      // below this: nothing found
        private const val AROUND = 1.5f    // the square given to the model: this many times the cube's size
    }

    private val env = OrtEnvironment.getEnvironment()
    private val session: OrtSession
    private val inputName: String
    /** The model's picture size (its input is 1 x 3 x SIZE x SIZE). */
    val SIZE: Int
    /** Which model file is in use (assets/models/, or files/finder.txt "model=..."). */
    val modelName: String
    private val square: Bitmap
    private val canvas: Canvas
    private val paint = Paint(Paint.FILTER_BITMAP_FLAG)
    private val pixels: IntArray
    private val values: FloatArray
    private val input: FloatBuffer
    private var around: RectF? = null     // where the cube was, in the frame's pixels

    /** The cube is being followed: the next look is a close one around it. */
    val following: Boolean get() = around != null
    /** How long the model took on the last frame, in ms. */
    var lastMs = 0L
        private set
    var prepareNs = 0L
    var modelNs = 0L
    var runs = 0

    init {
        // Tuning, without rebuilding: files/finder.txt may hold e.g. "threads=2 spin=0 model=cube_pose_v3_256_int8.onnx"
        // (SelfTest / adb).
        val tuning = tuning(context)
        modelName = modelFile?.name ?: (tuning["model"] ?: DEFAULT_MODEL)
        val model = modelFile?.readBytes() ?: context.assets.open("models/$modelName").use { it.readBytes() }
        val options = OrtSession.SessionOptions().apply {
            // 4 threads on the processor: 26 ms a look on the Beam Pro on its own. Its neural accelerator
            // (NNAPI) was 9 times slower with this model, and more threads than big cores was slower too.
            setIntraOpNumThreads(tuning["threads"]?.toIntOrNull() ?: 4)
            setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT)
            // Threads that wait by spinning keep a core busy; with the glasses' own software and the
            // camera decoder also running, letting them sleep leaves those cores to the others.
            addConfigEntry("session.intra_op.allow_spinning", tuning["spin"] ?: "1")
            // Other engines to try on the phone (files/finder.txt): "nnapi=1" the phone's neural engine
            // (Android NNAPI: best with an 8-bit model), "xnnpack=1" a faster processor engine for 8-bit
            // models. Either falls back to the processor for what it can't run.
            if (tuning["nnapi"] == "1") addNnapi()
            if (tuning["xnnpack"] == "1") addXnnpack(mapOf("intra_op_num_threads" to (tuning["threads"] ?: "4")))
        }
        session = env.createSession(model, options)
        inputName = session.inputNames.first()
        SIZE = ((session.inputInfo[inputName]!!.info as ai.onnxruntime.TensorInfo).shape[2]).toInt()
        square = Bitmap.createBitmap(SIZE, SIZE, Bitmap.Config.ARGB_8888)
        canvas = Canvas(square)
        pixels = IntArray(SIZE * SIZE)
        values = FloatArray(3 * SIZE * SIZE)
        input = ByteBuffer.allocateDirect(3 * SIZE * SIZE * 4).order(ByteOrder.nativeOrder()).asFloatBuffer()
        android.util.Log.i("CubeFinder", "model=$modelName size=$SIZE threads=${tuning["threads"] ?: 4} spin=${tuning["spin"] ?: "1"} " +
            "nnapi=${tuning["nnapi"] ?: 0} xnnpack=${tuning["xnnpack"] ?: 0}")
    }

    /** The cube was followed to these corners (TutorEngine, between looks): look around them next. */
    fun followTo(points: FloatArray?) {
        around = points?.let { squareAround(Found(it, 1f), null) }
    }

    fun find(frame: Bitmap): Found? {
        val start = System.nanoTime()
        var found: Found? = null
        around?.let { box ->
            found = run(frame, box)
            if (found == null || found!!.confidence < KEEP) found = null
        }
        if (found == null) {  // not following it (or it slipped away): look at the whole frame, then closer
            val coarse = run(frame, RectF(0f, 0f, frame.width.toFloat(), frame.height.toFloat()))
            found = if (coarse != null && coarse.confidence >= MIN) run(frame, squareAround(coarse, frame)) ?: coarse else null
        }
        val result = found?.takeIf { it.confidence >= MIN }
        around = result?.takeIf { it.confidence >= KEEP }?.let { squareAround(it, frame) }
        lastMs = (System.nanoTime() - start) / 1_000_000
        return result
    }

    private fun squareAround(found: Found, @Suppress("UNUSED_PARAMETER") frame: Bitmap?): RectF {
        var x0 = Float.MAX_VALUE; var y0 = Float.MAX_VALUE; var x1 = -Float.MAX_VALUE; var y1 = -Float.MAX_VALUE
        for (i in 0 until 7) {
            x0 = minOf(x0, found.points[2 * i]); x1 = maxOf(x1, found.points[2 * i])
            y0 = minOf(y0, found.points[2 * i + 1]); y1 = maxOf(y1, found.points[2 * i + 1])
        }
        val half = maxOf(x1 - x0, y1 - y0, 40f) * AROUND / 2
        val cx = (x0 + x1) / 2
        val cy = (y0 + y1) / 2
        return RectF(cx - half, cy - half, cx + half, cy + half)   // may reach past the frame: that part is drawn grey
    }

    /** Runs the model on one part of the frame (drawn to fit the model's square, grey around it). */
    private fun run(frame: Bitmap, box: RectF): Found? {
        val scale = minOf(SIZE / box.width(), SIZE / box.height())
        val padX = (SIZE - box.width() * scale) / 2
        val padY = (SIZE - box.height() * scale) / 2
        val t0 = System.nanoTime()
        canvas.drawColor(Color.rgb(114, 114, 114))
        // The part of the box that is inside the frame, and where it lands in the square.
        val src = Rect(maxOf(box.left, 0f).toInt(), maxOf(box.top, 0f).toInt(),
            minOf(box.right, frame.width.toFloat()).toInt(), minOf(box.bottom, frame.height.toFloat()).toInt())
        if (src.width() <= 0 || src.height() <= 0) return null
        val dst = RectF(padX + (src.left - box.left) * scale, padY + (src.top - box.top) * scale,
            padX + (src.right - box.left) * scale, padY + (src.bottom - box.top) * scale)
        canvas.drawBitmap(frame, src, dst, paint)
        square.getPixels(pixels, 0, SIZE, 0, 0, SIZE, SIZE)
        val plane = SIZE * SIZE
        for (i in 0 until plane) {   // filled as a plain array, then copied in one go (much faster than one put per number)
            val p = pixels[i]
            values[i] = ((p shr 16) and 0xFF) * (1f / 255f)
            values[plane + i] = ((p shr 8) and 0xFF) * (1f / 255f)
            values[2 * plane + i] = (p and 0xFF) * (1f / 255f)
        }
        input.rewind()
        input.put(values)
        input.rewind()
        val t1 = System.nanoTime()
        prepareNs += t1 - t0
        runs++
        OnnxTensor.createTensor(env, input, longArrayOf(1, 3, SIZE.toLong(), SIZE.toLong())).use { tensor ->
            session.run(mapOf(inputName to tensor)).use { output ->
                modelNs += System.nanoTime() - t1
                // [1, 26, N]: for each of N candidates, 4 box numbers, how sure, then 7 x (x, y, visible).
                val out = (output[0] as OnnxTensor).floatBuffer
                val n = out.remaining() / 26
                var best = 0
                var confidence = -1f
                for (i in 0 until n) {
                    val c = out.get(4 * n + i)
                    if (c > confidence) { confidence = c; best = i }
                }
                val points = FloatArray(14)
                for (k in 0 until 7) {
                    points[2 * k] = (out.get((5 + 3 * k) * n + best) - padX) / scale + box.left
                    points[2 * k + 1] = (out.get((6 + 3 * k) * n + best) - padY) / scale + box.top
                }
                return Found(points, confidence)
            }
        }
    }

    fun close() {
        session.close()
    }
}
