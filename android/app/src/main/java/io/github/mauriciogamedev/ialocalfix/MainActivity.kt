package io.github.mauriciogamedev.ialocalfix

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.weight
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Chat
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { LocalfixTheme { LocalfixApp() } }
    }
}

private enum class AppTab { Chat, Projects, Settings }
private data class ChatMessage(val fromUser: Boolean, val text: String)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun LocalfixApp() {
    val context = LocalContext.current
    val settings = remember { SecureSettings(context) }
    val scope = rememberCoroutineScope()

    var baseUrl by remember { mutableStateOf(settings.baseUrl) }
    var apiToken by remember { mutableStateOf(settings.readToken()) }
    var revision by remember { mutableIntStateOf(0) }
    val api = remember(baseUrl, apiToken, revision) { ApiClient(baseUrl, apiToken) }

    var tab by remember { mutableStateOf(AppTab.Chat) }
    var projects by remember { mutableStateOf<List<ApiProject>>(emptyList()) }
    var selectedProjectId by remember { mutableStateOf("") }
    var activeRun by remember { mutableStateOf<AgentRun?>(null) }
    var messages by remember { mutableStateOf(listOf<ChatMessage>()) }
    var busy by remember { mutableStateOf(false) }
    var notice by remember { mutableStateOf("") }
    var settingsNotice by remember { mutableStateOf("") }
    var connectionLabel by remember { mutableStateOf("Configure API") }

    LaunchedEffect(api) {
        if (baseUrl.isBlank()) {
            projects = emptyList()
            selectedProjectId = ""
            connectionLabel = "Configure API"
        } else {
            try {
                projects = api.listProjects()
                if (projects.none { it.id == selectedProjectId }) {
                    selectedProjectId = projects.firstOrNull()?.id.orEmpty()
                }
                connectionLabel = "API connected"
                notice = ""
            } catch (error: Exception) {
                connectionLabel = "Connection failed"
                notice = error.message ?: "Could not load projects."
            }
        }
    }

    val selectedProject = projects.firstOrNull { it.id == selectedProjectId }

    fun refreshProjects() {
        if (busy || baseUrl.isBlank()) return
        scope.launch {
            busy = true
            try {
                projects = api.listProjects()
                if (projects.none { it.id == selectedProjectId }) {
                    selectedProjectId = projects.firstOrNull()?.id.orEmpty()
                }
                connectionLabel = "API connected"
                notice = ""
            } catch (error: Exception) {
                notice = error.message ?: "Could not refresh projects."
            } finally {
                busy = false
            }
        }
    }

    fun createProject(name: String) {
        if (name.isBlank() || busy) return
        scope.launch {
            busy = true
            notice = ""
            try {
                val created = api.createProject(name)
                projects = (projects + created).sortedBy { it.name.lowercase() }
                selectedProjectId = created.id
                activeRun = null
                messages = emptyList()
                tab = AppTab.Chat
            } catch (error: Exception) {
                notice = error.message ?: "Project creation failed."
            } finally {
                busy = false
            }
        }
    }

    fun sendPrompt(prompt: String) {
        if (prompt.isBlank() || busy) return
        val projectId = selectedProjectId
        if (projectId.isBlank()) {
            notice = "Create or select a project before asking the AI."
            tab = AppTab.Projects
            return
        }
        messages = messages + ChatMessage(true, prompt.trim())
        activeRun = null
        notice = ""
        scope.launch {
            busy = true
            try {
                activeRun = api.createAgentRun(projectId, prompt)
                messages = messages + ChatMessage(
                    false,
                    "Proposal generated. Review the plan and files below, then approve or reject it."
                )
            } catch (error: Exception) {
                messages = messages + ChatMessage(false, error.message ?: "The AI request failed.")
            } finally {
                busy = false
            }
        }
    }

    fun approveRun() {
        val run = activeRun ?: return
        if (busy || run.status != "awaiting_approval") return
        scope.launch {
            busy = true
            notice = ""
            try {
                activeRun = api.approveAgentRun(run.id)
                messages = messages + ChatMessage(false, "Approved. The proposed files were applied to the project.")
            } catch (error: Exception) {
                notice = error.message ?: "Could not approve this proposal."
            } finally {
                busy = false
            }
        }
    }

    fun rejectRun() {
        val run = activeRun ?: return
        if (busy || run.status != "awaiting_approval") return
        scope.launch {
            busy = true
            notice = ""
            try {
                activeRun = api.rejectAgentRun(run.id)
                messages = messages + ChatMessage(false, "Proposal rejected. No files were changed.")
            } catch (error: Exception) {
                notice = error.message ?: "Could not reject this proposal."
            } finally {
                busy = false
            }
        }
    }

    fun saveConnection(url: String, token: String) {
        val normalized = url.trim().trimEnd('/')
        if (!(normalized.startsWith("http://") || normalized.startsWith("https://"))) {
            settingsNotice = "Enter a full address beginning with http:// or https://."
            return
        }
        try {
            val tokenToSave = if (token.isBlank() && apiToken.isNotBlank()) apiToken else token.trim()
            settings.baseUrl = normalized
            settings.saveToken(tokenToSave)
            baseUrl = settings.baseUrl
            apiToken = tokenToSave
            revision += 1
            settingsNotice = "Connection settings saved."
            notice = ""
        } catch (error: Exception) {
            settingsNotice = "Could not securely save the token: " + (error.message ?: "unknown error")
        }
    }

    fun testConnection(url: String, token: String) {
        scope.launch {
            busy = true
            settingsNotice = "Checking API health..."
            try {
                val result = ApiClient(url, token).health()
                settingsNotice = if (result == "ok") "API is reachable." else "API replied: " + result
            } catch (error: Exception) {
                settingsNotice = error.message ?: "Connection test failed."
            } finally {
                busy = false
            }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column(verticalArrangement = Arrangement.spacedBy(1.dp)) {
                        Text("IA LOCALFIX", fontWeight = FontWeight.Bold, letterSpacing = 1.3.sp)
                        Text(
                            connectionLabel.uppercase(),
                            style = MaterialTheme.typography.labelSmall,
                            color = if (connectionLabel == "API connected") MaterialTheme.colorScheme.primary
                            else MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                },
                actions = {
                    TextButton(onClick = { refreshProjects() }, enabled = !busy && baseUrl.isNotBlank()) {
                        Icon(Icons.Default.Refresh, contentDescription = "Refresh")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = MaterialTheme.colorScheme.background)
            )
        },
        bottomBar = {
            NavigationBar(containerColor = MaterialTheme.colorScheme.surface, windowInsets = WindowInsets.navigationBars) {
                NavigationBarItem(
                    selected = tab == AppTab.Chat,
                    onClick = { tab = AppTab.Chat },
                    icon = { Icon(Icons.Default.Chat, contentDescription = null) },
                    label = { Text("Chat") }
                )
                NavigationBarItem(
                    selected = tab == AppTab.Projects,
                    onClick = { tab = AppTab.Projects },
                    icon = { Icon(Icons.Default.Folder, contentDescription = null) },
                    label = { Text("Projects") }
                )
                NavigationBarItem(
                    selected = tab == AppTab.Settings,
                    onClick = { tab = AppTab.Settings },
                    icon = { Icon(Icons.Default.Settings, contentDescription = null) },
                    label = { Text("Settings") }
                )
            }
        }
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).background(MaterialTheme.colorScheme.background)
        ) {
            if (notice.isNotBlank()) NoticeBanner(notice) { notice = "" }
            when (tab) {
                AppTab.Chat -> ChatScreen(
                    projects = projects,
                    selectedProjectId = selectedProjectId,
                    selectedProject = selectedProject,
                    onSelectProject = { selectedProjectId = it; activeRun = null },
                    messages = messages,
                    agentRun = activeRun,
                    busy = busy,
                    onSend = ::sendPrompt,
                    onApprove = ::approveRun,
                    onReject = ::rejectRun,
                    onOpenProjects = { tab = AppTab.Projects }
                )
                AppTab.Projects -> ProjectsScreen(
                    projects = projects,
                    selectedProjectId = selectedProjectId,
                    busy = busy,
                    onSelect = { selectedProjectId = it; activeRun = null; tab = AppTab.Chat },
                    onCreate = ::createProject
                )
                AppTab.Settings -> SettingsScreen(
                    baseUrl = baseUrl,
                    tokenConfigured = apiToken.isNotBlank(),
                    busy = busy,
                    notice = settingsNotice,
                    onSave = ::saveConnection,
                    onTest = ::testConnection
                )
            }
        }
    }
}

@Composable
private fun NoticeBanner(text: String, onDismiss: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 6.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(text, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodySmall)
            TextButton(onClick = onDismiss) { Icon(Icons.Default.Close, contentDescription = "Dismiss") }
        }
    }
}

@Composable
private fun ChatScreen(
    projects: List<ApiProject>,
    selectedProjectId: String,
    selectedProject: ApiProject?,
    onSelectProject: (String) -> Unit,
    messages: List<ChatMessage>,
    agentRun: AgentRun?,
    busy: Boolean,
    onSend: (String) -> Unit,
    onApprove: () -> Unit,
    onReject: () -> Unit,
    onOpenProjects: () -> Unit
) {
    var prompt by remember { mutableStateOf("") }
    Column(modifier = Modifier.fillMaxSize().imePadding()) {
        Column(modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
            Text("ACTIVE PROJECT", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (projects.isEmpty()) {
                Text("No projects yet. Create one to start.", style = MaterialTheme.typography.bodyMedium)
                OutlinedButton(onClick = onOpenProjects) { Text("Create project") }
            } else {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    projects.take(3).forEach { project ->
                        FilterChip(
                            selected = project.id == selectedProjectId,
                            onClick = { onSelectProject(project.id) },
                            label = { Text(project.name, maxLines = 1) }
                        )
                    }
                }
                if (selectedProject != null) {
                    Text(selectedProject.slug, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }

        LazyColumn(
            modifier = Modifier.weight(1f).fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(10.dp),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 16.dp, vertical = 8.dp)
        ) {
            if (messages.isEmpty()) item { WelcomeCard(onOpenProjects) }
            items(messages) { message -> MessageBubble(message) }
            if (agentRun != null) {
                item {
                    ProposalCard(agentRun, busy, onApprove, onReject)
                }
            }
            if (busy) {
                item {
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(10.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        CircularProgressIndicator(modifier = Modifier.size(18.dp), strokeWidth = 2.dp)
                        Text("Working with the local AI API...", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }

        Surface(color = MaterialTheme.colorScheme.surface, tonalElevation = 2.dp) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp),
                verticalAlignment = Alignment.Bottom,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedTextField(
                    value = prompt,
                    onValueChange = { prompt = it },
                    modifier = Modifier.weight(1f),
                    placeholder = { Text("Ask Localfix to build or change something...") },
                    minLines = 1,
                    maxLines = 4,
                    enabled = !busy && selectedProject != null
                )
                Button(
                    onClick = {
                        val value = prompt.trim()
                        if (value.isNotEmpty()) {
                            prompt = ""
                            onSend(value)
                        }
                    },
                    enabled = !busy && prompt.isNotBlank() && selectedProject != null,
                    modifier = Modifier.height(54.dp)
                ) { Icon(Icons.Default.Send, contentDescription = "Send") }
            }
        }
    }
}

@Composable
private fun WelcomeCard(onOpenProjects: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().padding(top = 24.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
    ) {
        Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Build with your local AI.", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold)
            Text(
                "Describe a project or a change. Localfix prepares a file proposal first; nothing is applied until you approve it.",
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Button(onClick = onOpenProjects) { Text("Create your first project") }
        }
    }
}

@Composable
private fun MessageBubble(message: ChatMessage) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (message.fromUser) Arrangement.End else Arrangement.Start
    ) {
        Card(
            modifier = Modifier.fillMaxWidth(0.9f),
            shape = RoundedCornerShape(18.dp),
            colors = CardDefaults.cardColors(
                containerColor = if (message.fromUser) MaterialTheme.colorScheme.primary.copy(alpha = 0.15f)
                else MaterialTheme.colorScheme.surface
            )
        ) {
            Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(
                    if (message.fromUser) "YOU" else "LOCALFIX",
                    style = MaterialTheme.typography.labelSmall,
                    color = if (message.fromUser) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.secondary
                )
                Text(message.text, style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

@Composable
private fun ProposalCard(run: AgentRun, busy: Boolean, onApprove: () -> Unit, onReject: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("AI PROPOSAL", fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                AssistChip(onClick = {}, enabled = false, label = { Text(run.status.replace('_', ' ')) })
            }
            Text(run.summary, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text(run.plan, style = MaterialTheme.typography.bodyMedium)
            if (run.steps.isNotEmpty()) {
                Text("IMPLEMENTATION PLAN", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                run.steps.forEachIndexed { index, step ->
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text((index + 1).toString() + ".", color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
                        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text(step.title, fontWeight = FontWeight.Medium)
                            Text(step.description, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
            if (run.files.isNotEmpty()) {
                Text("FILES (" + run.files.size + ")", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                run.files.forEach { file ->
                    Column(
                        modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp))
                            .background(MaterialTheme.colorScheme.surface).padding(10.dp),
                        verticalArrangement = Arrangement.spacedBy(5.dp)
                    ) {
                        Text(file.operation.uppercase() + " · " + file.path, fontWeight = FontWeight.Medium, fontSize = 12.sp)
                        Text(
                            file.preview,
                            fontFamily = FontFamily.Monospace,
                            fontSize = 10.sp,
                            lineHeight = 14.sp,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                        Text(file.sizeBytes.toString() + " bytes", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
            if (run.status == "awaiting_approval") {
                Text(
                    "Review the proposed files before applying them to this project.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Button(onClick = onApprove, enabled = !busy, modifier = Modifier.weight(1f)) {
                        Icon(Icons.Default.CheckCircle, contentDescription = null)
                        Spacer(Modifier.width(6.dp))
                        Text("Approve")
                    }
                    OutlinedButton(onClick = onReject, enabled = !busy, modifier = Modifier.weight(1f)) {
                        Icon(Icons.Default.Close, contentDescription = null)
                        Spacer(Modifier.width(6.dp))
                        Text("Reject")
                    }
                }
            } else {
                Text(
                    if (run.status == "completed") "Files applied successfully."
                    else "Proposal status: " + run.status,
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Medium
                )
            }
            if (!run.error.isNullOrBlank()) {
                Text(run.error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
private fun ProjectsScreen(
    projects: List<ApiProject>,
    selectedProjectId: String,
    busy: Boolean,
    onSelect: (String) -> Unit,
    onCreate: (String) -> Unit
) {
    var projectName by remember { mutableStateOf("") }
    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text("Projects", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Text(
            "Each project has an isolated workspace and its own approval history.",
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
            Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("NEW PROJECT", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                OutlinedTextField(
                    value = projectName,
                    onValueChange = { projectName = it.take(80) },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("Project name") },
                    singleLine = true,
                    enabled = !busy
                )
                Button(
                    onClick = {
                        onCreate(projectName.trim())
                        projectName = ""
                    },
                    enabled = !busy && projectName.isNotBlank(),
                    modifier = Modifier.fillMaxWidth()
                ) { Text("Create project") }
            }
        }
        Text("YOUR PROJECTS", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
        if (projects.isEmpty()) {
            Text("No projects are available. Check the API connection in Settings.")
        } else {
            projects.forEach { project ->
                Card(
                    modifier = Modifier.fillMaxWidth().clickable { onSelect(project.id) },
                    colors = CardDefaults.cardColors(
                        containerColor = if (project.id == selectedProjectId) MaterialTheme.colorScheme.primary.copy(alpha = 0.13f)
                        else MaterialTheme.colorScheme.surface
                    )
                ) {
                    Row(modifier = Modifier.fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                        Column(modifier = Modifier.weight(1f)) {
                            Text(project.name, fontWeight = FontWeight.SemiBold)
                            Text(project.slug, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        if (project.id == selectedProjectId) {
                            Icon(Icons.Default.CheckCircle, contentDescription = "Selected", tint = MaterialTheme.colorScheme.primary)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SettingsScreen(
    baseUrl: String,
    tokenConfigured: Boolean,
    busy: Boolean,
    notice: String,
    onSave: (String, String) -> Unit,
    onTest: (String, String) -> Unit
) {
    var draftUrl by remember { mutableStateOf(baseUrl) }
    var draftToken by remember { mutableStateOf("") }
    var tokenVisible by remember { mutableStateOf(false) }
    LaunchedEffect(baseUrl) { draftUrl = baseUrl }

    Column(
        modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text("Connection", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
        Text(
            "Connect this phone to the computer or Linux host running the Localfix API.",
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)) {
            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = draftUrl,
                    onValueChange = { draftUrl = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("API base URL") },
                    placeholder = { Text("http://192.168.1.10:8000") },
                    singleLine = true,
                    enabled = !busy
                )
                OutlinedTextField(
                    value = draftToken,
                    onValueChange = { draftToken = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text(if (tokenConfigured) "API token (blank keeps saved token)" else "API token (optional)") },
                    singleLine = true,
                    visualTransformation = if (tokenVisible) VisualTransformation.None else PasswordVisualTransformation(),
                    enabled = !busy,
                    trailingIcon = {
                        TextButton(onClick = { tokenVisible = !tokenVisible }) {
                            Text(if (tokenVisible) "Hide" else "Show")
                        }
                    }
                )
                Text(
                    "The token is encrypted with Android Keystore before it is stored on this device.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                Text(
                    "HTTP is unencrypted. Use it only on a trusted local network; use HTTPS for remote access.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error
                )
                Button(
                    onClick = { onTest(draftUrl, draftToken) },
                    enabled = !busy && draftUrl.isNotBlank(),
                    modifier = Modifier.fillMaxWidth()
                ) { Text("Test connection") }
                OutlinedButton(
                    onClick = {
                        onSave(draftUrl, draftToken)
                        draftToken = ""
                    },
                    enabled = !busy && draftUrl.isNotBlank(),
                    modifier = Modifier.fillMaxWidth()
                ) { Text("Save settings") }
                if (notice.isNotBlank()) {
                    Text(notice, color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.bodySmall)
                }
            }
        }
        Text(
            "The API server must be reachable from the phone. For Wi-Fi testing, use the host computer's LAN IP and port 8000. If API authentication is enabled, enter its IA_API_TOKEN here.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}
