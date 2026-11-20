package io.github.mauriciogamedev.ialocalfix

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import org.json.JSONArray
import org.json.JSONObject
import java.util.UUID

data class LocalProject(val id: String, val name: String, val createdAt: Long)
data class LocalChatMessage(val id: String, val projectId: String, val role: String, val content: String, val createdAt: Long)
data class ProposedFile(val path: String, val content: String)
data class LocalProposal(
    val id: String, val projectId: String, val prompt: String, val summary: String,
    val files: List<ProposedFile>, val status: String, val createdAt: Long
)

/** Durable, private, on-device project/chat/memory store. No network database is involved. */
class LocalStore(context: Context) :
    SQLiteOpenHelper(context.applicationContext, "ia_localfix_device.db", null, 1) {

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("""CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at INTEGER NOT NULL)""")
        db.execSQL("""CREATE TABLE messages (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user','assistant')),
            content TEXT NOT NULL, created_at INTEGER NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        )""")
        db.execSQL("CREATE INDEX idx_messages_project_time ON messages(project_id, created_at)")
        db.execSQL("""CREATE TABLE memories (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL, content TEXT NOT NULL, created_at INTEGER NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        )""")
        db.execSQL("CREATE INDEX idx_memories_project_time ON memories(project_id, created_at)")
        db.execSQL("""CREATE TABLE proposals (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL, prompt TEXT NOT NULL, summary TEXT NOT NULL,
            files_json TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected')),
            created_at INTEGER NOT NULL, FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        )""")
        db.execSQL("CREATE INDEX idx_proposals_project_time ON proposals(project_id, created_at)")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        // Version 1 is the first phone-local schema. Future upgrades must use explicit migrations.
    }

    fun listProjects(): List<LocalProject> {
        val result = mutableListOf<LocalProject>()
        readableDatabase.rawQuery(
            "SELECT id, name, created_at FROM projects ORDER BY name COLLATE NOCASE", null
        ).use { cursor ->
            while (cursor.moveToNext()) result += LocalProject(cursor.getString(0), cursor.getString(1), cursor.getLong(2))
        }
        return result
    }

    fun createProject(name: String): LocalProject {
        val cleanName = name.trim().take(80)
        require(cleanName.isNotBlank()) { "Project name cannot be empty." }
        val project = LocalProject(UUID.randomUUID().toString(), cleanName, System.currentTimeMillis())
        val values = ContentValues().apply {
            put("id", project.id); put("name", project.name); put("created_at", project.createdAt)
        }
        writableDatabase.insertOrThrow("projects", null, values)
        return project
    }

    fun deleteProject(projectId: String) {
        writableDatabase.beginTransaction()
        try {
            writableDatabase.delete("messages", "project_id = ?", arrayOf(projectId))
            writableDatabase.delete("memories", "project_id = ?", arrayOf(projectId))
            writableDatabase.delete("proposals", "project_id = ?", arrayOf(projectId))
            writableDatabase.delete("projects", "id = ?", arrayOf(projectId))
            writableDatabase.setTransactionSuccessful()
        } finally {
            writableDatabase.endTransaction()
        }
    }

    fun addMessage(projectId: String, role: String, content: String): LocalChatMessage {
        require(role == "user" || role == "assistant")
        val message = LocalChatMessage(UUID.randomUUID().toString(), projectId, role, content.take(40_000), System.currentTimeMillis())
        val values = ContentValues().apply {
            put("id", message.id); put("project_id", projectId); put("role", role)
            put("content", message.content); put("created_at", message.createdAt)
        }
        writableDatabase.insertOrThrow("messages", null, values)
        return message
    }

    fun recentMessages(projectId: String, limit: Int = 10): List<LocalChatMessage> {
        val result = mutableListOf<LocalChatMessage>()
        readableDatabase.rawQuery(
            """SELECT id, project_id, role, content, created_at
               FROM messages WHERE project_id = ? ORDER BY created_at DESC, rowid DESC LIMIT ?""",
            arrayOf(projectId, limit.coerceIn(1, 30).toString())
        ).use { cursor ->
            while (cursor.moveToNext()) {
                result += LocalChatMessage(cursor.getString(0), cursor.getString(1), cursor.getString(2), cursor.getString(3), cursor.getLong(4))
            }
        }
        return result.asReversed()
    }

    fun addMemory(projectId: String, content: String) {
        val clean = content.trim().take(4_000)
        require(clean.isNotBlank()) { "Memory cannot be empty." }
        val values = ContentValues().apply {
            put("id", UUID.randomUUID().toString()); put("project_id", projectId)
            put("content", clean); put("created_at", System.currentTimeMillis())
        }
        writableDatabase.insertOrThrow("memories", null, values)
    }

    fun recentMemories(projectId: String, limit: Int = 8): List<String> {
        val result = mutableListOf<String>()
        readableDatabase.rawQuery(
            "SELECT content FROM memories WHERE project_id = ? ORDER BY created_at DESC, rowid DESC LIMIT ?",
            arrayOf(projectId, limit.coerceIn(1, 20).toString())
        ).use { cursor -> while (cursor.moveToNext()) result += cursor.getString(0) }
        return result.asReversed()
    }

    fun saveProposal(projectId: String, prompt: String, summary: String, files: List<ProposedFile>): String {
        val json = JSONArray()
        files.forEach { file -> json.put(JSONObject().put("path", file.path).put("content", file.content)) }
        val id = UUID.randomUUID().toString()
        val values = ContentValues().apply {
            put("id", id); put("project_id", projectId); put("prompt", prompt.take(8_000))
            put("summary", summary.take(4_000)); put("files_json", json.toString())
            put("status", "pending"); put("created_at", System.currentTimeMillis())
        }
        writableDatabase.insertOrThrow("proposals", null, values)
        return id
    }

    fun pendingProposal(projectId: String): LocalProposal? {
        readableDatabase.rawQuery(
            """SELECT id, project_id, prompt, summary, files_json, status, created_at
               FROM proposals WHERE project_id = ? AND status = 'pending'
               ORDER BY created_at DESC, rowid DESC LIMIT 1""",
            arrayOf(projectId)
        ).use { cursor ->
            if (!cursor.moveToFirst()) return null
            return parseProposal(cursor)
        }
    }

    fun updateProposalStatus(proposalId: String, status: String) {
        require(status == "approved" || status == "rejected")
        writableDatabase.update(
            "proposals", ContentValues().apply { put("status", status) },
            "id = ? AND status = 'pending'", arrayOf(proposalId)
        )
    }

    private fun parseProposal(cursor: android.database.Cursor): LocalProposal {
        val json = JSONArray(cursor.getString(4))
        val files = buildList {
            for (index in 0 until json.length()) {
                val item = json.getJSONObject(index)
                add(ProposedFile(item.getString("path"), item.getString("content")))
            }
        }
        return LocalProposal(
            cursor.getString(0), cursor.getString(1), cursor.getString(2), cursor.getString(3),
            files, cursor.getString(5), cursor.getLong(6)
        )
    }
}
