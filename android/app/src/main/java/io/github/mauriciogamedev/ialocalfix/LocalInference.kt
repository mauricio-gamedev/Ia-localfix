package io.github.mauriciogamedev.ialocalfix

import android.content.Context
import com.google.ai.edge.litertlm.Backend
import com.google.ai.edge.litertlm.Contents
import com.google.ai.edge.litertlm.ConversationConfig
import com.google.ai.edge.litertlm.Engine
import com.google.ai.edge.litertlm.EngineConfig
import com.google.ai.edge.litertlm.Message
import com.google.ai.edge.litertlm.SamplerConfig
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.asCoroutineDispatcher
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.io.File
import java.util.concurrent.Executors

data class InferenceState(
    val ready: Boolean = false,
    val loading: Boolean = false,
    val modelPath: String? = null,
    val error: String? = null
)

/** One process-wide owner for the native LiteRT-LM engine. Engine calls are serialized on one thread. */
class LocalInference(context: Context) {
    private val appContext = context.applicationContext
    private val executor = Executors.newSingleThreadExecutor { runnable -> Thread(runnable, "ia-localfix-inference") }
    private val dispatcher = executor.asCoroutineDispatcher()
    private val scope = CoroutineScope(SupervisorJob() + dispatcher)
    private val mutex = Mutex()
    private var engine: Engine? = null
    private var loadedPath: String? = null
    private val mutableState = MutableStateFlow(InferenceState())
    val state: StateFlow<InferenceState> = mutableState.asStateFlow()

    fun load(modelPath: String): Job = scope.launch {
        mutex.withLock {
            if (engine != null && loadedPath == modelPath) {
                mutableState.value = InferenceState(ready = true, modelPath = modelPath)
                return@withLock
            }
            mutableState.value = InferenceState(loading = true)
            try {
                engine?.close()
                engine = null
                loadedPath = null
                val modelFile = File(modelPath)
                require(modelFile.isFile && modelFile.length() > 0L) { "The on-device model file is missing or empty." }
                val candidate = Engine(
                    EngineConfig(modelPath = modelFile.absolutePath, backend = Backend.CPU(), cacheDir = appContext.cacheDir.absolutePath)
                )
                // Do not retain or close a candidate if initialize() throws.
                candidate.initialize()
                engine = candidate
                loadedPath = modelFile.absolutePath
                mutableState.value = InferenceState(ready = true, modelPath = loadedPath)
            } catch (error: Exception) {
                mutableState.value = InferenceState(error = error.message ?: "The local model could not be loaded.")
            }
        }
    }

    suspend fun generate(systemInstruction: String, history: List<LocalChatMessage>, prompt: String): String =
        withContext(dispatcher) {
            mutex.withLock {
                val currentEngine = engine ?: throw IllegalStateException("Load the on-device model in Settings before using local AI.")
                val initialMessages = history.takeLast(8).dropWhile { it.role != "user" }.map { message ->
                    if (message.role == "assistant") Message.model(message.content) else Message.user(message.content)
                }.ifEmpty {
                    // Qwen3's chat template expects at least one completed turn in its prefill.
                    listOf(Message.user("Start a new local session."), Message.model("Ready."))
                }
                val conversation = currentEngine.createConversation(
                    ConversationConfig(
                        systemInstruction = Contents.of(systemInstruction),
                        initialMessages = initialMessages,
                        samplerConfig = SamplerConfig(topK = 20, topP = 0.85, temperature = 0.35)
                    )
                )
                try {
                    val result = StringBuilder()
                    conversation.sendMessageAsync(prompt).collect { part -> result.append(part.toString()) }
                    result.toString().trim().ifBlank {
                        throw IllegalStateException("The local model returned an empty response.")
                    }
                } finally {
                    conversation.close()
                }
            }
        }

    fun unload(): Job = scope.launch {
        mutex.withLock {
            engine?.close()
            engine = null
            loadedPath = null
            mutableState.value = InferenceState()
        }
    }

    fun shutdown() {
        scope.launch {
            mutex.withLock {
                engine?.close()
                engine = null
                loadedPath = null
            }
        }.invokeOnCompletion {
            scope.cancel()
            dispatcher.close()
        }
    }
}
