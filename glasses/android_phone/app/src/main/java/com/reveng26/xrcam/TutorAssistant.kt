package com.reveng26.xrcam

import android.content.Context
import android.util.Log
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/**
 * The assistant's connection to the language model, for the glasses app: the tutor's Python code builds
 * the chat (its rules and the tutor's real state: vision/assistant.py, vision/phone.py assistant_request)
 * and this sends it to Azure OpenAI and returns the answer. Android's own HTTPS (the phone's certificates)
 * rather than Python's.
 *
 * The settings, as on the laptop (~/.cube_tutor_llm.env): AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT,
 * AZURE_OPENAI_DEPLOYMENT, AZURE_OPENAI_API_VERSION, in the app's private files/llm.env, put there from the
 * laptop over adb (README_VOICE.md); never inside the app or in git. No file: questions get a polite
 * "not set up", everything else works.
 */
class TutorAssistant(context: Context) {
    companion object { private const val TAG = "TutorAssistant" }

    private val settings: Map<String, String> = try {
        File(context.filesDir, "llm.env").readLines().mapNotNull { line ->
            Regex("""\s*([A-Z_]+)\s*=\s*"?([^"]*)"?\s*""").matchEntire(line)?.let { it.groupValues[1] to it.groupValues[2] }
        }.toMap()
    } catch (_: Exception) { emptyMap() }

    val available: Boolean get() = listOf("AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_DEPLOYMENT").all { !settings[it].isNullOrBlank() }

    init { Log.i(TAG, if (available) "set up (${settings["AZURE_OPENAI_DEPLOYMENT"]})" else "not set up: no files/llm.env") }

    /** messages: the chat (JSON array of {role, content}); returns the answer text. Throws on failure. */
    fun chat(messages: JSONArray, maxTokens: Int): String {
        val endpoint = settings.getValue("AZURE_OPENAI_ENDPOINT").trimEnd('/')
        val version = settings["AZURE_OPENAI_API_VERSION"] ?: "2024-12-01-preview"
        val url = URL("$endpoint/openai/deployments/${settings.getValue("AZURE_OPENAI_DEPLOYMENT")}/chat/completions?api-version=$version")
        val body = JSONObject().put("messages", messages).put("max_completion_tokens", maxTokens).toString().toByteArray()
        val t0 = System.currentTimeMillis()
        val conn = (url.openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 8000
            readTimeout = 20000
            doOutput = true
            setRequestProperty("Content-Type", "application/json")
            setRequestProperty("api-key", settings.getValue("AZURE_OPENAI_API_KEY"))
        }
        try {
            conn.outputStream.use { it.write(body) }
            if (conn.responseCode !in 200..299) {
                val err = conn.errorStream?.bufferedReader()?.readText()?.take(300)
                throw IllegalStateException("HTTP ${conn.responseCode}: $err")
            }
            val reply = JSONObject(conn.inputStream.bufferedReader().readText())
            val text = reply.getJSONArray("choices").getJSONObject(0).getJSONObject("message").getString("content").trim()
            Log.i(TAG, "answered in ${System.currentTimeMillis() - t0} ms (${reply.optString("model")})")
            return text
        } finally {
            conn.disconnect()
        }
    }
}
