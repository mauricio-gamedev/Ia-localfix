package io.github.mauriciogamedev.ialocalfix

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

data class ApiProject(
    val id: String,
    val name: String,
    val slug: String,
    val createdAt: String
)

data class AgentStep(val title: String, val description: String)

data class AgentFile(
    val path: String,
    val operation: String,
    val sizeBytes: Int,
    val preview: String
)

data class AgentRun(
    val id: String,
    val projectId: String,
    val status: String,
    val model: String,
    val summary: String,
    val plan: String,
    val steps: List<AgentStep>,
    val files: List<AgentFile>,
    val error: String?
)

class ApiClient(baseUrl: String, private val token: String) {
    private val root = baseUrl.trim().trimEnd('/')

    private suspend fun request(
        method: String,
        path: String,
        body: JSONObject? = null
    ): String = withContext(Dispatchers.IO) {
        if (root.isBlank()) throw IOException("Configure the API address in Settings first.")
        val connection = (URL(root + path).openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = 12_000
            readTimeout = 180_000
            setRequestProperty("Accept", "application/json")
            if (token.isNotBlank()) setRequestProperty("Authorization", "Bearer $token")
            if (body != null) {
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
            }
        }
        try {
            if (body != null) {
                connection.outputStream.bufferedWriter(Charsets.UTF_8).use { it.write(body.toString()) }
            }
            val code = connection.responseCode
            val stream = if (code in 200..299) connection.inputStream else connection.errorStream
            val response = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
            if (code !in 200..299) {
                val detail = runCatching {
                    val value = JSONObject(response).opt("detail")
                    when (value) {
                        is String -> value
                        null -> response
                        else -> value.toString()
                    }
                }.getOrDefault(response)
                val message = when (code) {
                    401 -> "Authentication failed. Check the API token in Settings."
                    404 -> "The requested API resource was not found."
                    503 -> "The AI model is unavailable on the API host."
                    else -> detail.ifBlank { "API request failed (HTTP $code)." }
                }
                throw ApiException(message, code)
            }
            response
        } finally {
            connection.disconnect()
        }
    }

    suspend fun health(): String {
        val response = request("GET", "/health")
        return JSONObject(response).optString("status", "unknown")
    }

    suspend fun listProjects(): List<ApiProject> {
        val response = JSONArray(request("GET", "/v1/projects"))
        return buildList {
            for (index in 0 until response.length()) {
                val item = response.getJSONObject(index)
                add(
                    ApiProject(
                        id = item.getString("id"),
                        name = item.getString("name"),
                        slug = item.getString("slug"),
                        createdAt = item.optString("created_at")
                    )
                )
            }
        }
    }

    suspend fun createProject(name: String): ApiProject {
        val body = JSONObject().put("name", name.trim())
        val item = JSONObject(request("POST", "/v1/projects", body))
        return ApiProject(
            id = item.getString("id"),
            name = item.getString("name"),
            slug = item.getString("slug"),
            createdAt = item.optString("created_at")
        )
    }

    suspend fun createAgentRun(projectId: String, prompt: String): AgentRun {
        val body = JSONObject()
            .put("project_id", projectId)
            .put("request", prompt.trim())
        return parseRun(JSONObject(request("POST", "/v1/agent/runs", body)))
    }

    suspend fun approveAgentRun(runId: String): AgentRun {
        return parseRun(JSONObject(request("POST", "/v1/agent/runs/$runId/approve")))
    }

    suspend fun rejectAgentRun(runId: String): AgentRun {
        val body = JSONObject().put("reason", "Rejected from the Android client.")
        return parseRun(JSONObject(request("POST", "/v1/agent/runs/$runId/reject", body)))
    }

    private fun parseRun(item: JSONObject): AgentRun {
        val stepsJson = item.optJSONArray("steps") ?: JSONArray()
        val filesJson = item.optJSONArray("files") ?: JSONArray()
        val steps = buildList {
            for (index in 0 until stepsJson.length()) {
                val step = stepsJson.getJSONObject(index)
                add(AgentStep(step.optString("title"), step.optString("description")))
            }
        }
        val files = buildList {
            for (index in 0 until filesJson.length()) {
                val file = filesJson.getJSONObject(index)
                add(
                    AgentFile(
                        path = file.optString("path"),
                        operation = file.optString("operation", "create"),
                        sizeBytes = file.optInt("size_bytes"),
                        preview = file.optString("preview")
                    )
                )
            }
        }
        return AgentRun(
            id = item.getString("id"),
            projectId = item.getString("project_id"),
            status = item.optString("status"),
            model = item.optString("model"),
            summary = item.optString("summary"),
            plan = item.optString("plan"),
            steps = steps,
            files = files,
            error = item.optString("error").takeIf { it.isNotBlank() && it != "null" }
        )
    }
}

class ApiException(message: String, val statusCode: Int) : IOException(message)
