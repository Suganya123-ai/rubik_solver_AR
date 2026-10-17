package com.reveng26.xrcam

import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import android.webkit.JavascriptInterface
import android.webkit.WebView
import org.json.JSONObject
import java.lang.ref.WeakReference
import java.util.Locale

/**
 * The tutor's voice in the app: Android's text-to-speech says the instructions and its speech
 * recognition listens for the spoken commands ("next", "repeat"...), for the tutor page, which
 * Android's web view gives neither (web/src/voice.ts uses this as window.TutorVoice).
 *
 * One voice for the whole app: the tutor page is open on the glasses (one copy per eye in 3D mode)
 * and on the phone, and only one of them may speak and get what is heard, or each instruction
 * would be said twice and each "next" done twice. The glasses' first copy has it when it is open,
 * otherwise the phone's.
 */
object TutorVoice {
    private const val TAG = "TutorVoice"
    const val GLASSES = 2
    const val PHONE = 1

    private val main = Handler(Looper.getMainLooper())
    private var tts: TextToSpeech? = null
    private var ttsReady = false
    private var pending: String? = null                // said before the speech engine was ready
    private var owner: WeakReference<WebView>? = null
    private var ownerRank = 0
    private var recognizer: SpeechRecognizer? = null
    private var listening = false
    private lateinit var app: Context

    /** Offers the voice to a tutor page (call before it loads). rank: GLASSES or PHONE. */
    fun attach(view: WebView, rank: Int) {
        app = view.context.applicationContext
        view.addJavascriptInterface(Bridge(view, rank), "TutorVoice")
        if (tts == null) {
            tts = TextToSpeech(app) { status ->
                ttsReady = status == TextToSpeech.SUCCESS
                tts?.language = Locale.US
                tts?.setSpeechRate(1.05f)
                tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                    override fun onStart(id: String?) {}
                    override fun onDone(id: String?) = toPage("window.tutorSpoke && tutorSpoke()")
                    @Deprecated("Deprecated in Java")
                    override fun onError(id: String?) = toPage("window.tutorSpoke && tutorSpoke()")
                })
                Log.i(TAG, "text-to-speech ready: $ttsReady")
                pending?.let { say(it) }
                pending = null
            }
        }
    }

    private fun isOwner(view: WebView): Boolean = owner?.get() === view

    /** The page with the highest rank that asked last owns the voice (a page that was closed loses it). */
    private fun claim(view: WebView, rank: Int) {
        val current = owner?.get()
        if (current == null || !current.isAttachedToWindow || rank >= ownerRank) {
            owner = WeakReference(view)
            ownerRank = rank
            Log.i(TAG, "voice now with the ${if (rank == GLASSES) "glasses" else "phone"} page")
        }
    }

    private fun toPage(js: String) { main.post { owner?.get()?.evaluateJavascript(js, null) } }

    private fun say(text: String) {
        val engine = tts
        if (engine == null || !ttsReady) { pending = text; return }
        engine.speak(text, TextToSpeech.QUEUE_FLUSH, null, "tutor")   // the newest instruction is the one that matters
    }

    private class Bridge(view: WebView, private val rank: Int) {
        private val view = WeakReference(view)

        @JavascriptInterface
        fun say(text: String) {
            val v = view.get() ?: return
            main.post {
                if (owner?.get() == null) claim(v, rank)
                if (isOwner(v)) TutorVoice.say(text)
            }
        }

        @JavascriptInterface
        fun listen(on: Boolean) {
            val v = view.get() ?: return
            main.post {
                claim(v, rank)
                if (on && isOwner(v)) startListening() else if (!on && isOwner(v)) stopListening()
            }
        }
    }

    // ---------- listening ----------
    private fun startListening() {
        if (listening) return
        if (app.checkSelfPermission(android.Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            Log.w(TAG, "no microphone permission: voice commands off")
            return
        }
        if (!SpeechRecognizer.isRecognitionAvailable(app)) {
            Log.w(TAG, "no speech recognition on this phone: voice commands off")
            return
        }
        listening = true
        val onDevice = android.os.Build.VERSION.SDK_INT >= 31 && SpeechRecognizer.isOnDeviceRecognitionAvailable(app)
        recognizer = if (onDevice) SpeechRecognizer.createOnDeviceSpeechRecognizer(app) else SpeechRecognizer.createSpeechRecognizer(app)
        Log.i(TAG, "listening for commands (${if (onDevice) "on the phone" else "Google's service"})")
        recognizer!!.setRecognitionListener(object : RecognitionListener {
            override fun onResults(results: Bundle?) {
                val heard = results?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION).orEmpty()
                if (heard.isNotEmpty()) {
                    Log.i(TAG, "heard: $heard")
                    // every guess, best first: the page takes the first that is a command
                    toPage("window.tutorHeard && tutorHeard(${JSONObject.quote(heard.joinToString(" | "))})")
                }
                again(200)
            }
            override fun onError(error: Int) {
                // no speech / nothing matched: listen again at once; busy: give it a moment
                again(if (error == SpeechRecognizer.ERROR_RECOGNIZER_BUSY || error == SpeechRecognizer.ERROR_CLIENT) 1000 else 200)
            }
            override fun onReadyForSpeech(params: Bundle?) {}
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(rmsdB: Float) {}
            override fun onBufferReceived(buffer: ByteArray?) {}
            override fun onEndOfSpeech() {}
            override fun onPartialResults(partialResults: Bundle?) {}
            override fun onEvent(eventType: Int, params: Bundle?) {}
        })
        listenOnce()
    }

    private val intent by lazy {
        Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH).apply {
            putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            putExtra(RecognizerIntent.EXTRA_LANGUAGE, "en-US")
            putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)
            putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
        }
    }

    private fun listenOnce() {
        try { recognizer?.startListening(intent) } catch (e: Exception) { Log.w(TAG, "listen failed: ${e.message}"); again(1000) }
    }

    private fun again(delayMs: Long) {
        if (!listening) return
        main.postDelayed({ if (listening) listenOnce() }, delayMs)
    }

    private fun stopListening() {
        listening = false
        try { recognizer?.destroy() } catch (_: Exception) {}
        recognizer = null
    }
}
