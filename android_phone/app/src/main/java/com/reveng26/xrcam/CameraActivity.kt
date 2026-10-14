package com.reveng26.xrcam

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.graphics.SurfaceTexture
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbManager
import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaFormat
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.HandlerThread
import android.os.Looper
import android.util.Log
import android.view.Surface
import android.view.TextureView
import androidx.appcompat.app.AppCompatActivity
import com.reveng26.xrcam.databinding.ActivityCameraBinding
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.util.concurrent.ConcurrentLinkedQueue

/**
 * Displays the UVC camera stream from the XREAL glasses.
 * Decodes H.265/HEVC NAL units using MediaCodec with VPS/SPS/PPS handling.
 *
 * USB reads and decoding run on separate threads to prevent data loss.
 */
class CameraActivity : AppCompatActivity(), UvcCameraHelper.Listener {

    companion object {
        private var lastRestart = 0L
        private var restarts = 0   // automatic restarts in a row without a picture

        /** Launch options that put an activity on the phone's own screen (display 0). */
        fun onPhoneScreen(): Bundle =
            android.app.ActivityOptions.makeBasic().setLaunchDisplayId(android.view.Display.DEFAULT_DISPLAY).toBundle()

        const val EXTRA_CAMERA_TYPE = "camera_type"
        const val EXTRA_SERVER = "server"
        private const val TAG = "CameraActivity"
        private const val ACTION_CAMERA_PERMISSION = "com.reveng26.xrcam.CAMERA_USB_PERMISSION"
    }

    private lateinit var binding: ActivityCameraBinding
    private lateinit var cameraHelper: UvcCameraHelper
    private lateinit var cameraType: GlassesConnection.CameraType
    private val handler = Handler(Looper.getMainLooper())
    private var usbManager: UsbManager? = null

    private var surface: Surface? = null
    private var uploader: TutorEngine? = null
    private var closing = false
    private var streamed = false   // the camera has streamed at least once in this screen
    private var lastComeBack = 0L
    private var glassesScreen: GlassesScreen? = null
    private var frameCount = 0L
    private var lastFpsTime = 0L
    private var fpsFrameCount = 0

    private var retryCount = 0
    private val maxRetries = 15
    private var pendingDevice: UsbDevice? = null

    // H.265/HEVC decoder state
    private var decoder: MediaCodec? = null
    private var decoderReady = false
    private var vpsNal: ByteArray? = null
    private var spsNal: ByteArray? = null
    private var ppsNal: ByteArray? = null
    private var decodedFrames = 0

    // Decoder runs on its own thread so USB reads are never blocked
    private val nalQueue = ConcurrentLinkedQueue<ByteArray>()
    private var decoderThread: HandlerThread? = null
    private var decoderHandler: Handler? = null

    private val permissionReceiver = object : BroadcastReceiver() {
        override fun onReceive(ctx: Context, intent: Intent) {
            if (intent.action == ACTION_CAMERA_PERMISSION) {
                val granted = intent.getBooleanExtra(UsbManager.EXTRA_PERMISSION_GRANTED, false)
                Log.d(TAG, "Camera USB permission: $granted")
                if (granted) {
                    pendingDevice?.let { dev ->
                        binding.cameraStatusText.text = "Permission granted, starting stream..."
                        cameraHelper.startStream(dev)
                    }
                } else {
                    binding.cameraStatusText.text = "Camera USB permission denied"
                }
                pendingDevice = null
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityCameraBinding.inflate(layoutInflater)
        setContentView(binding.root)

        usbManager = getSystemService(Context.USB_SERVICE) as UsbManager
        cameraType = GlassesConnection.CameraType.valueOf(
            intent.getStringExtra(EXTRA_CAMERA_TYPE) ?: "GREYSCALE"
        )

        // --- Cube Tutor bridge: show the tutor page on top and upload the camera picture to the laptop ---
        window.addFlags(android.view.WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        val server = intent.getStringExtra(EXTRA_SERVER).orEmpty()
        TutorEngine.startServer(this)   // before the pages below ask it for anything
        binding.tutorView.apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.mediaPlaybackRequiresUserGesture = false
            setBackgroundColor(android.graphics.Color.BLACK)
            webViewClient = object : android.webkit.WebViewClient() {
                // The laptop's certificate is one it made itself; accept it for this page.
                override fun onReceivedSslError(view: android.webkit.WebView, handler: android.webkit.SslErrorHandler,
                                                error: android.net.http.SslError) = handler.proceed()
                // The page server starts with the tutor; if the page asked before it was up, ask again.
                override fun onReceivedError(view: android.webkit.WebView, request: android.webkit.WebResourceRequest,
                                             error: android.webkit.WebResourceError) {
                    if (request.isForMainFrame) view.postDelayed({ view.reload() }, 1000)
                }
            }
            if (server.isNotEmpty()) loadUrl("http://$server/glasses/?camera=remote")
        }
        binding.btnToggleView.setOnClickListener {
            val showTutor = binding.tutorView.visibility != android.view.View.VISIBLE
            binding.tutorView.visibility = if (showTutor) android.view.View.VISIBLE else android.view.View.INVISIBLE
            binding.btnToggleView.text = if (showTutor) "Camera" else "Tutor"
        }
        if (server.isNotEmpty()) {
            startForegroundService(Intent(this, TutorService::class.java))   // all processor cores (see TutorService)
            uploader = TutorEngine(this) { status ->
                handler.post { binding.uploadStatusText.text = status }
            }.also { it.start() }
            binding.btnZoom.setOnClickListener {  // how much of the wide camera view is sent: 2x -> 3x -> 1x
                val up = uploader ?: return@setOnClickListener
                up.zoom = if (up.zoom >= 3) 1 else up.zoom + 1
                binding.btnZoom.text = "Zoom ${up.zoom}x"
            }
            // The glasses are a second screen: put the tutor there (this phone keeps the buttons).
            glassesScreen = GlassesScreen(this, server).also { screen ->
                screen.onChange = { showing ->
                    binding.btnGlassesView.isEnabled = showing
                    binding.btnGlassesView.text = when {
                        !showing -> "No glasses screen"
                        screen.floatingOnly -> "Glasses: floating"
                        else -> "Glasses: picture"
                    }
                    binding.btnGlassesView.alpha = if (showing) 1f else 0.5f
                }
                binding.btnGlassesView.setOnClickListener {
                    screen.floatingOnly = !screen.floatingOnly
                    binding.btnGlassesView.text = if (screen.floatingOnly) "Glasses: floating" else "Glasses: picture"
                }
                screen.start()
            }
        }

        binding.cameraStatusText.text = "Searching for ${cameraType.name} camera..."
        cameraHelper = UvcCameraHelper(this)
        cameraHelper.listener = this

        binding.btnClose.setOnClickListener {
            closing = true
            uploader?.stop()
            cameraHelper.stopStream()
            finish()
        }

        val filter = IntentFilter(ACTION_CAMERA_PERMISSION)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(permissionReceiver, filter, Context.RECEIVER_EXPORTED)
        } else {
            registerReceiver(permissionReceiver, filter)
        }

        binding.cameraPreview.surfaceTextureListener = object : TextureView.SurfaceTextureListener {
            override fun onSurfaceTextureAvailable(st: SurfaceTexture, w: Int, h: Int) {
                surface = Surface(st)
                tryFindCamera()
            }
            override fun onSurfaceTextureSizeChanged(st: SurfaceTexture, w: Int, h: Int) {}
            override fun onSurfaceTextureDestroyed(st: SurfaceTexture): Boolean {
                surface = null
                return true
            }
            override fun onSurfaceTextureUpdated(st: SurfaceTexture) {}
        }

        // Start decoder thread
        decoderThread = HandlerThread("HEVC-Decoder").also { it.start() }
        decoderHandler = Handler(decoderThread!!.looper)
    }

    private fun tryFindCamera() {
        handler.post {
            // Already streaming: this screen's camera view is rebuilt when XREAL's app moves the screen
            // to another display and back, which asked again; a second stream stopped the picture.
            if (cameraHelper.streaming || pendingDevice != null) return@post
            binding.cameraStatusText.text = "Searching for camera... (attempt ${retryCount + 1}/$maxRetries)"
            val device = cameraHelper.findCamera(cameraType)
            if (device != null) {
                val mgr = usbManager!!
                if (mgr.hasPermission(device)) {
                    streamed = true
                    binding.cameraStatusText.text = "Camera found! Starting stream..."
                    cameraHelper.startStream(device)
                } else {
                    binding.cameraStatusText.text = "Requesting camera permission..."
                    pendingDevice = device
                    val permIntent = Intent(ACTION_CAMERA_PERMISSION).apply { setPackage(packageName) }
                    val flags = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) PendingIntent.FLAG_MUTABLE else 0
                    mgr.requestPermission(device, PendingIntent.getBroadcast(this, 1, permIntent, flags))
                }
            } else if (retryCount < (if (streamed) 3 else maxRetries)) {
                retryCount++
                handler.postDelayed({ tryFindCamera() }, 2000)
            } else {
                // The glasses reset their USB link now and then (about every 20 minutes in one session)
                // and come back with the camera switched off. Switch it on again: start over.
                binding.cameraStatusText.text = "Camera gone — switching it on again…"
                restartTutor("camera not found")
            }
        }
    }

    /**
     * XREAL's app puts the phone into "controller mode" (its trackpad) when the glasses connect,
     * which covers this screen: no tutor and no buttons on the phone. While the tutor runs, come
     * back to the front (at most every few seconds, so this never fights XREAL's app in a loop).
     */
    override fun onStop() {
        super.onStop()
        if (!closing && !isFinishing && uploader != null) handler.postDelayed({ comeBack() }, 1500)
    }

    /** Back to the start screen, which switches the glasses' camera on and opens the tutor again. */
    private fun restartTutor(reason: String) {
        if (closing || isFinishing) return
        val now = System.currentTimeMillis()
        if (now - lastRestart < 15000) {   // not in a loop: try again a bit later
            handler.postDelayed({ retryCount = 0; tryFindCamera() }, 5000)
            return
        }
        if (restarts >= 3) {   // switching the camera off and on didn't help: only a replug resets it
            Log.w(TAG, "camera still not working after $restarts restarts: asking for a replug")
            binding.cameraStatusText.text = "The glasses' camera is stuck. Unplug the glasses, wait 5 seconds, plug them back in."
            binding.uploadStatusText.text = binding.cameraStatusText.text
            return
        }
        restarts++
        lastRestart = now
        Log.w(TAG, "restarting the tutor: $reason")
        closing = true
        startActivity(Intent(this, MainActivity::class.java)
            .putExtra("autostart", true)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP),
            onPhoneScreen())
        finish()
    }

    override fun onResume() {
        super.onResume()
        // XREAL's app can move this screen onto its own virtual screen inside the glasses: bring it back.
        if ((display?.displayId ?: android.view.Display.DEFAULT_DISPLAY) != android.view.Display.DEFAULT_DISPLAY) {
            Log.d(TAG, "opened on display ${display?.displayId}, not the phone's: moving to the phone's screen")
            handler.postDelayed({ comeBack() }, 300)
        }
    }

    private val onPhone: Boolean
        get() = (display?.displayId ?: android.view.Display.DEFAULT_DISPLAY) == android.view.Display.DEFAULT_DISPLAY

    private fun comeBack() {
        if (closing || isFinishing || isDestroyed || (onPhone && hasWindowFocus())) return
        val now = System.currentTimeMillis()
        if (now - lastComeBack < 4000) return
        lastComeBack = now
        Log.d(TAG, "covered by another app: coming back to the front")
        try {
            startActivity(Intent(this, CameraActivity::class.java)
                .addFlags(Intent.FLAG_ACTIVITY_REORDER_TO_FRONT or Intent.FLAG_ACTIVITY_NEW_TASK), onPhoneScreen())
        } catch (e: Exception) {
            Log.w(TAG, "could not come back to the front: ${e.message}")
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        stopService(Intent(this, TutorService::class.java))
        uploader?.stop()
        uploader = null
        glassesScreen?.stop()
        glassesScreen = null
        binding.tutorView.destroy()
        cameraHelper.stopStream()
        releaseDecoder()
        decoderThread?.quitSafely()
        decoderThread = null
        decoderHandler = null
        surface?.release()
        try { unregisterReceiver(permissionReceiver) } catch (_: Exception) {}
    }

    // --- H.265/HEVC Decoder ---

    private fun initDecoder() {
        if (vpsNal == null || spsNal == null || ppsNal == null) {
            Log.d(TAG, "Cannot init decoder: need VPS+SPS+PPS (have VPS=${vpsNal != null} SPS=${spsNal != null} PPS=${ppsNal != null})")
            return
        }

        try {
            val format = MediaFormat.createVideoFormat(MediaFormat.MIMETYPE_VIDEO_HEVC, 1920, 1080)

            // HEVC csd-0 = VPS + SPS + PPS concatenated (all with start codes)
            val csd0 = ByteArrayOutputStream()
            csd0.write(vpsNal!!)
            csd0.write(spsNal!!)
            csd0.write(ppsNal!!)
            format.setByteBuffer("csd-0", ByteBuffer.wrap(csd0.toByteArray()))

            Log.d(TAG, "HEVC csd-0: VPS=${vpsNal!!.size}b + SPS=${spsNal!!.size}b + PPS=${ppsNal!!.size}b = ${csd0.size()}b")

            val codec = MediaCodec.createDecoderByType(MediaFormat.MIMETYPE_VIDEO_HEVC)
            // Decoded into memory (not onto the screen): the tutor reads each picture itself, and gets it
            // even while XREAL's app covers this screen (a covered view stops updating). Drawing into
            // an ImageReader instead gave pictures in the decoder's own compressed layout, unreadable.
            format.setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible)
            codec.configure(format, null, null, 0)
            codec.start()
            decoder = codec
            decoderReady = true
            Log.d(TAG, "HEVC decoder initialized with VPS/SPS/PPS")
            handler.post { binding.cameraStatusText.text = "HEVC decoder ready, waiting for frames..." }

            // Start the decode loop on the decoder thread
            scheduleDecodeDrain()
        } catch (e: Exception) {
            Log.e(TAG, "Decoder init failed", e)
            handler.post { binding.cameraStatusText.text = "Decoder error: ${e.message}" }
        }
    }

    private fun releaseDecoder() {
        decoderReady = false
        nalQueue.clear()
        try {
            decoder?.stop()
            decoder?.release()
        } catch (_: Exception) {}
        decoder = null
    }

    /**
     * Feed queued NAL units to the decoder and drain outputs.
     * Runs on the decoder thread, never blocking the USB read thread.
     */
    private fun scheduleDecodeDrain() {
        decoderHandler?.post { decodeDrainLoop() }
    }

    private fun decodeDrainLoop() {
        val codec = decoder ?: return
        if (!decoderReady) return

        try {
            // Feed as many queued NALs as we can
            var fed = 0
            while (fed < 8) { // batch up to 8 per cycle
                val nal = nalQueue.poll() ?: break
                val inIndex = codec.dequeueInputBuffer(0) // non-blocking
                if (inIndex >= 0) {
                    val inputBuffer = codec.getInputBuffer(inIndex) ?: break
                    inputBuffer.clear()
                    inputBuffer.put(nal)
                    val pts = decodedFrames * 33333L
                    codec.queueInputBuffer(inIndex, 0, nal.size, pts, 0)
                    decodedFrames++
                    fed++
                } else {
                    // No input buffer available, put NAL back and drain outputs first
                    nalQueue.offer(nal) // re-queue at head... actually offer adds to tail
                    break
                }
            }

            // Drain all available outputs
            val info = MediaCodec.BufferInfo()
            while (true) {
                val outIndex = codec.dequeueOutputBuffer(info, 0)
                if (outIndex >= 0) {
                    try {
                        codec.getOutputImage(outIndex)?.let { image -> uploader?.offer(image) }
                    } catch (e: Exception) {
                        Log.w(TAG, "could not read a decoded picture: ${e.message}")
                    }
                    codec.releaseOutputBuffer(outIndex, false)
                } else if (outIndex == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    val newFormat = codec.outputFormat
                    Log.d(TAG, "Decoder output format: $newFormat")
                    handler.post {
                        val w = newFormat.getInteger(MediaFormat.KEY_WIDTH)
                        val h = newFormat.getInteger(MediaFormat.KEY_HEIGHT)
                        binding.cameraStatusText.text = "Decoding ${w}x${h} HEVC"
                    }
                } else {
                    break
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Decoder error: ${e.message}")
        }

        // Re-schedule: run again soon if there's queued data, otherwise slower poll
        if (decoderReady) {
            val delay = if (nalQueue.isNotEmpty()) 0L else 1L
            decoderHandler?.postDelayed({ decodeDrainLoop() }, delay)
        }
    }

    // --- UvcCameraHelper.Listener ---

    override fun onCameraFound(description: String) {
        handler.post { binding.cameraStatusText.text = "Found: $description" }
    }

    override fun onStreamStarted() {
        handler.post {
            binding.cameraStatusText.text = "Streaming — waiting for VPS/SPS/PPS..."
            lastFpsTime = System.currentTimeMillis()
            fpsFrameCount = 0
        }
    }

    override fun onStreamStopped() {
        handler.post {
            binding.cameraStatusText.text = "Stream stopped"
            binding.fpsText.text = ""
        }
        releaseDecoder()
    }

    override fun onError(message: String) {
        handler.post {
            binding.cameraStatusText.text = "Error: $message"
            if (message.startsWith("No data")) restartTutor("camera sends nothing")
        }
    }

    override fun onLog(message: String) {
        handler.post {
            Log.d(TAG, message)
            binding.cameraStatusText.text = message
            // The camera is open but sends nothing (10 s): switch it off and on again.
            if (message.startsWith("20 timeouts")) restartTutor("camera sends nothing")
        }
    }

    /**
     * Called from the USB read thread. Must return quickly to avoid missing data.
     * NAL parsing happens here (fast), decoding is queued to the decoder thread.
     */
    override fun onFrameReceived(width: Int, height: Int, data: ByteArray) {
        restarts = 0   // the camera works: automatic restarts may be used again later
        frameCount++
        fpsFrameCount++

        val now = System.currentTimeMillis()
        if (now - lastFpsTime >= 1000) {
            val fps = fpsFrameCount * 1000.0 / (now - lastFpsTime)
            lastFpsTime = now
            fpsFrameCount = 0
            handler.post {
                binding.fpsText.text = "%.1f fps | %d bytes | #%d | dec:%d | q:%d".format(
                    fps, data.size, frameCount, decodedFrames, nalQueue.size)
            }
        }

        // Process HEVC access unit — parse NALs and queue for decoding
        processHevcAccessUnit(data)
    }

    /**
     * Process an HEVC access unit that may contain multiple NAL units.
     * Extract VPS/SPS/PPS, init decoder, then queue slice NALs for decoding.
     *
     * HEVC NAL type = (first_byte_after_start_code >> 1) & 0x3F
     *   VPS = 32 (0x40), SPS = 33 (0x42), PPS = 34 (0x44)
     *   IDR_W_RADL = 19, IDR_N_LP = 20, TRAIL_R = 1, TRAIL_N = 0
     */
    private fun processHevcAccessUnit(data: ByteArray) {
        val nalUnits = splitNalUnits(data)

        for (nal in nalUnits) {
            if (nal.size < 5) continue

            // Find NAL header byte (byte after start code)
            val nalTypeIdx = if (nal[2] == 1.toByte()) 3 else 4
            if (nalTypeIdx >= nal.size) continue

            // HEVC: NAL type is bits 1-6 of first byte after start code
            val nalType = (nal[nalTypeIdx].toInt() shr 1) and 0x3F

            when (nalType) {
                32 -> { // VPS
                    vpsNal = nal.copyOf()
                    if (!decoderReady) initDecoder()
                }
                33 -> { // SPS
                    spsNal = nal.copyOf()
                    if (!decoderReady) initDecoder()
                }
                34 -> { // PPS
                    ppsNal = nal.copyOf()
                    if (!decoderReady) initDecoder()
                }
                19, 20 -> { // IDR_W_RADL, IDR_N_LP (keyframes)
                    if (!decoderReady) initDecoder()
                    if (decoderReady) nalQueue.offer(nal)
                }
                0, 1 -> { // TRAIL_N, TRAIL_R (non-IDR slices)
                    if (decoderReady) nalQueue.offer(nal)
                }
                else -> {
                    if (decoderReady) nalQueue.offer(nal)
                    if (frameCount <= 20) {
                        Log.d(TAG, "HEVC NAL type $nalType: ${nal.size} bytes")
                    }
                }
            }
        }
    }

    /**
     * Split a byte array into individual NAL units.
     * Each NAL unit starts with 00 00 00 01 or 00 00 01.
     */
    private fun splitNalUnits(data: ByteArray): List<ByteArray> {
        val units = mutableListOf<ByteArray>()
        val startPositions = mutableListOf<Int>()

        // Find all start code positions
        var i = 0
        while (i < data.size - 3) {
            if (data[i] == 0.toByte() && data[i + 1] == 0.toByte()) {
                if (i + 3 < data.size && data[i + 2] == 0.toByte() && data[i + 3] == 1.toByte()) {
                    startPositions.add(i)
                    i += 4
                    continue
                }
                if (data[i + 2] == 1.toByte()) {
                    startPositions.add(i)
                    i += 3
                    continue
                }
            }
            i++
        }

        // Extract each NAL unit
        for (j in startPositions.indices) {
            val start = startPositions[j]
            val end = if (j + 1 < startPositions.size) startPositions[j + 1] else data.size
            if (end > start) {
                units.add(data.copyOfRange(start, end))
            }
        }

        // If no start codes found, treat entire data as one unit
        if (units.isEmpty() && data.isNotEmpty()) {
            units.add(data)
        }

        return units
    }
}
