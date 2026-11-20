package io.github.mauriciogamedev.ialocalfix

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

object LocalModelCatalog {
    const val FILE_NAME = "Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm"
    const val DOWNLOAD_URL = "https://huggingface.co/litert-community/Qwen3-0.6B/resolve/main/Qwen3-0.6B_dynamic_wi4b32_afp32.litertlm"
    const val MODEL_CARD_URL = "https://huggingface.co/litert-community/Qwen3-0.6B"
    const val EXPECTED_SHA256 = "96491bb0f78fa68098bf8f1d3628194c97041aff7894f8cc29303b3acdb877a9"
    const val MIN_BYTES = 340_000_000L
    const val MAX_BYTES = 350_000_000L
    const val EXPECTED_DISPLAY_BYTES = 344_686_592L

    fun modelFile(context: Context): File {
        val directory = File(context.filesDir, "models")
        if (!directory.exists() && !directory.mkdirs()) throw IllegalStateException("Could not create private model storage.")
        return File(directory, FILE_NAME)
    }

    fun isInstalled(context: Context): Boolean {
        val file = modelFile(context)
        return file.isFile && file.length() in MIN_BYTES..MAX_BYTES
    }
}

class LocalModelInstaller(context: Context) {
    private val appContext = context.applicationContext

    suspend fun download(onProgress: (Float) -> Unit): File = withContext(Dispatchers.IO) {
        val target = LocalModelCatalog.modelFile(appContext)
        if (target.isFile && target.length() in LocalModelCatalog.MIN_BYTES..LocalModelCatalog.MAX_BYTES) return@withContext target
        val partial = File(target.parentFile, target.name + ".part")
        partial.delete()
        val connection = (URL(LocalModelCatalog.DOWNLOAD_URL).openConnection() as HttpURLConnection).apply {
            requestMethod = "GET"
            connectTimeout = 25_000
            readTimeout = 120_000
            instanceFollowRedirects = true
            setRequestProperty("User-Agent", "Ia-Localfix-Android/0.2")
            setRequestProperty("Accept", "application/octet-stream")
        }
        try {
            val status = connection.responseCode
            if (status !in 200..299) throw IllegalStateException("Model download failed (HTTP " + status + ").")
            val reportedLength = connection.contentLengthLong
            if (reportedLength > LocalModelCatalog.MAX_BYTES) throw IllegalStateException("The model server returned a file larger than the published model.")
            val digest = MessageDigest.getInstance("SHA-256")
            var downloaded = 0L
            connection.inputStream.buffered().use { input ->
                FileOutputStream(partial).use { output ->
                    val buffer = ByteArray(128 * 1024)
                    while (true) {
                        currentCoroutineContext().ensureActive()
                        val count = input.read(buffer)
                        if (count < 0) break
                        downloaded += count
                        if (downloaded > LocalModelCatalog.MAX_BYTES) throw IllegalStateException("The downloaded model exceeded the expected 328 MiB size.")
                        digest.update(buffer, 0, count)
                        output.write(buffer, 0, count)
                        if (downloaded % (1024 * 1024) < count) {
                            val denominator = if (reportedLength > 0L) reportedLength else LocalModelCatalog.EXPECTED_DISPLAY_BYTES
                            val progress = (downloaded.toFloat() / denominator.toFloat()).coerceIn(0f, 0.99f)
                            withContext(Dispatchers.Main) { onProgress(progress) }
                        }
                    }
                    output.fd.sync()
                }
            }
            require(downloaded in LocalModelCatalog.MIN_BYTES..LocalModelCatalog.MAX_BYTES) {
                "The downloaded model size does not match the published 328 MiB model."
            }
            val actualHash = digest.digest().joinToString("") { "%02x".format(it) }
            require(actualHash.equals(LocalModelCatalog.EXPECTED_SHA256, ignoreCase = true)) {
                "Model integrity verification failed. The partial download was discarded."
            }
            if (target.exists() && !target.delete()) throw IllegalStateException("Could not replace the previous model file.")
            if (!partial.renameTo(target)) throw IllegalStateException("Could not finalize the verified model file.")
            withContext(Dispatchers.Main) { onProgress(1f) }
            target
        } catch (error: Exception) {
            partial.delete()
            throw error
        } finally {
            connection.disconnect()
        }
    }
}
