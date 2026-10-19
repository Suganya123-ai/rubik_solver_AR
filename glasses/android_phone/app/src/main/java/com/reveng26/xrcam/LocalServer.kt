package com.reveng26.xrcam

import android.content.Context
import android.util.Log
import fi.iki.elonen.NanoHTTPD
import fi.iki.elonen.NanoWSD
import java.io.IOException
import java.io.InputStream
import java.util.concurrent.CopyOnWriteArraySet

/**
 * The tutor page's server, inside the app (in the laptop version this is
 * glasses_server.py). Only this phone can reach it (127.0.0.1).
 *
 *   /glasses/...   the built web page (assets/web)
 *   /ws/view       the page's link: it receives every frame's result, and its
 *                  commands (scan_start, scan_accept, ...) go to [onCommand]
 *   /feed.mjpg     the camera picture, for the page's "picture" view
 */
class LocalServer(
    private val context: Context,
    port: Int,
    /** A command from the page; the answer (if any) is sent to every page. */
    private val onCommand: (String) -> String?,
) : NanoWSD("127.0.0.1", port) {

    companion object {
        private const val TAG = "LocalServer"
        private val TYPES = mapOf("html" to "text/html", "js" to "text/javascript", "mjs" to "text/javascript",
            "css" to "text/css", "json" to "application/json", "svg" to "image/svg+xml", "png" to "image/png",
            "jpg" to "image/jpeg", "ico" to "image/x-icon", "wasm" to "application/wasm", "woff2" to "font/woff2")
    }

    private val viewers = CopyOnWriteArraySet<Viewer>()
    // Sending happens on its own thread, in order: callers may be on the main thread, where
    // Android forbids network use (closing the tutor crashed on that).
    private val sender = java.util.concurrent.Executors.newSingleThreadExecutor()
    private val pictureLock = Object()
    private var jpeg: ByteArray? = null
    private var jpegCount = 0
    @Volatile private var pictureViewers = 0
    @Volatile var feeding = false
        set(value) {
            if (field != value) { field = value; broadcast("""{"type":"feed","connected":$value}""") }
        }

    /** Is a page showing the camera picture? (If not, no JPEG needs to be made.) */
    val wantsPicture: Boolean get() = pictureViewers > 0

    fun broadcast(text: String) {
        sender.execute { sendToAll(text) }
    }

    private fun sendToAll(text: String) {
        for (viewer in viewers) {
            try {
                viewer.send(text)
            } catch (e: IOException) {
                viewers.remove(viewer)
            }
        }
    }

    fun picture(newJpeg: ByteArray) {
        synchronized(pictureLock) {
            jpeg = newJpeg
            jpegCount++
            pictureLock.notifyAll()
        }
    }

    override fun openWebSocket(handshake: IHTTPSession): WebSocket = Viewer(handshake)

    private inner class Viewer(handshake: IHTTPSession) : WebSocket(handshake) {
        override fun onOpen() {
            viewers.add(this)
            try { send("""{"type":"feed","connected":$feeding}""") } catch (_: IOException) {}
        }

        override fun onClose(code: WebSocketFrame.CloseCode?, reason: String?, initiatedByRemote: Boolean) {
            viewers.remove(this)
        }

        override fun onMessage(message: WebSocketFrame) {
            val text = message.textPayload ?: return
            try {
                onCommand(text)?.let { broadcast(it) }
            } catch (e: Exception) {
                Log.e(TAG, "command failed: $text", e)
                broadcast("""{"type":"error","code":"SERVER","message":"internal error, see the app's log"}""")
            }
        }

        override fun onPong(pong: WebSocketFrame?) {}

        override fun onException(exception: IOException) {
            viewers.remove(this)
        }
    }

    override fun serveHttp(session: IHTTPSession): Response {
        val uri = session.uri
        if (uri == "/feed.mjpg") {
            return newChunkedResponse(Response.Status.OK, "multipart/x-mixed-replace; boundary=frame", PictureStream())
        }
        if (uri == "/" || uri == "/glasses") {
            return newFixedLengthResponse(Response.Status.REDIRECT, MIME_HTML, "").apply { addHeader("Location", "/glasses/") }
        }
        if (!uri.startsWith("/glasses/") || uri.contains("..")) {
            return newFixedLengthResponse(Response.Status.NOT_FOUND, MIME_PLAINTEXT, "Not found")
        }
        val path = "web/" + uri.removePrefix("/glasses/").ifEmpty { "index.html" }
        return try {
            val bytes = context.assets.open(path).use { it.readBytes() }
            val type = TYPES[path.substringAfterLast('.', "")] ?: "application/octet-stream"
            newFixedLengthResponse(Response.Status.OK, type, bytes.inputStream(), bytes.size.toLong())
        } catch (e: IOException) {
            newFixedLengthResponse(Response.Status.NOT_FOUND, MIME_PLAINTEXT, "Not found")
        }
    }

    /** The camera picture as a never-ending stream of JPEGs: each read waits for the next one. */
    private inner class PictureStream : InputStream() {
        private var part = ByteArray(0)
        private var at = 0
        private var sent = -1
        private var open = true

        init { pictureViewers++ }

        override fun read(): Int {
            val one = ByteArray(1)
            return if (read(one, 0, 1) < 0) -1 else one[0].toInt() and 0xFF
        }

        override fun read(buffer: ByteArray, offset: Int, length: Int): Int {
            if (at >= part.size) {
                val next = synchronized(pictureLock) {
                    while (jpeg == null || jpegCount == sent) pictureLock.wait(1000)
                    sent = jpegCount
                    jpeg!!
                }
                part = "--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ${next.size}\r\n\r\n".toByteArray() +
                    next + "\r\n".toByteArray()
                at = 0
            }
            val n = minOf(length, part.size - at)
            System.arraycopy(part, at, buffer, offset, n)
            at += n
            return n
        }

        override fun close() {
            if (open) { open = false; pictureViewers-- }
        }
    }
}
