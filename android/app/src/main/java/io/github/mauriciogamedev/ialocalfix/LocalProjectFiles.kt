package io.github.mauriciogamedev.ialocalfix

import android.content.Context
import android.net.Uri
import org.json.JSONException
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

data class ParsedProposal(val summary: String, val files: List<ProposedFile>)

object LocalProposalRules {
    const val MAX_FILES = 12
    const val MAX_FILE_BYTES = 65_536
    const val MAX_TOTAL_BYTES = 400_000

    fun validatePath(path: String): Boolean {
        if (path.isBlank() || path.length > 180) return false
        if (path.startsWith("/") || path.startsWith("\\") || path.contains("\\") || path.contains(":")) return false
        val parts = path.split("/")
        if (parts.any { it.isBlank() || it == "." || it == ".." }) return false
        val lower = path.lowercase()
        val forbidden = listOf(".env", ".git/", ".ssh/", "id_rsa", "id_ed25519", ".keystore", "credentials", "secrets.", "private_key", "token.txt")
        return forbidden.none { lower.contains(it) }
    }
}

object LocalProposalParser {
    fun parse(raw: String): ParsedProposal {
        val start = raw.indexOf('{')
        val end = raw.lastIndexOf('}')
        require(start >= 0 && end > start) { "The local model did not return a JSON project proposal." }
        val root = try {
            JSONObject(raw.substring(start, end + 1))
        } catch (error: JSONException) {
            throw IllegalArgumentException("The model returned invalid JSON. Try a smaller, more specific project.", error)
        }
        val summary = root.optString("summary").trim().ifBlank { "Generated project files" }
        val items = root.optJSONArray("files") ?: throw IllegalArgumentException("The proposal is missing its files array.")
        require(items.length() in 1..LocalProposalRules.MAX_FILES) {
            "The proposal must contain between 1 and " + LocalProposalRules.MAX_FILES + " files."
        }
        val seen = mutableSetOf<String>()
        var totalBytes = 0
        val files = buildList {
            for (index in 0 until items.length()) {
                val item = items.optJSONObject(index) ?: throw IllegalArgumentException("A generated file entry is not an object.")
                val path = item.optString("path").trim()
                val content = item.optString("content")
                require(LocalProposalRules.validatePath(path)) { "Unsafe or unsupported file path: " + path }
                require(seen.add(path.lowercase())) { "The model returned a duplicate path: " + path }
                val size = content.toByteArray(Charsets.UTF_8).size
                require(size in 1..LocalProposalRules.MAX_FILE_BYTES) { "Generated file is empty or too large: " + path }
                totalBytes += size
                require(totalBytes <= LocalProposalRules.MAX_TOTAL_BYTES) { "The proposal exceeds the total source-size limit." }
                add(ProposedFile(path, content))
            }
        }
        return ParsedProposal(summary, files)
    }
}

object LocalProjectFiles {
    fun root(context: Context, projectId: String): File {
        require(projectId.matches(Regex("[a-f0-9-]{36}"))) { "Invalid project identifier." }
        return File(context.filesDir, "projects/$projectId").canonicalFile
    }

    fun listPaths(context: Context, projectId: String, max: Int = 80): List<String> {
        val root = root(context, projectId)
        if (!root.exists()) return emptyList()
        val base = root.canonicalPath + File.separator
        return root.walkTopDown()
            .filter { it.isFile && !java.nio.file.Files.isSymbolicLink(it.toPath()) }
            .mapNotNull { file ->
                val canonical = runCatching { file.canonicalPath }.getOrNull() ?: return@mapNotNull null
                if (!canonical.startsWith(base)) null
                else canonical.removePrefix(base).replace(File.separatorChar, '/')
            }.take(max).toList()
    }

    /** Applies only new files. Any failure removes files created during this proposal. */
    fun applyProposal(context: Context, projectId: String, files: List<ProposedFile>): List<String> {
        val root = root(context, projectId)
        if (!root.exists() && !root.mkdirs()) throw IllegalStateException("Could not create the private project workspace.")
        val canonicalRoot = root.canonicalFile
        val created = mutableListOf<File>()
        try {
            files.forEach { item ->
                require(LocalProposalRules.validatePath(item.path)) { "Unsafe file path: " + item.path }
                val target = File(canonicalRoot, item.path).canonicalFile
                require(target.path.startsWith(canonicalRoot.path + File.separator)) { "Generated path escaped the workspace." }
                var parent: File? = target.parentFile
                while (parent != null && parent.path.startsWith(canonicalRoot.path)) {
                    require(!java.nio.file.Files.isSymbolicLink(parent.toPath())) { "Symbolic links are not allowed in project workspaces." }
                    if (parent == canonicalRoot) break
                    parent = parent.parentFile
                }
                val parentDir = target.parentFile
                if (parentDir != null && !parentDir.exists() && !parentDir.mkdirs()) {
                    throw IllegalStateException("Could not create a directory for " + item.path + ".")
                }
                require(!target.exists()) { "Refusing to overwrite an existing file: " + item.path }
                if (!target.createNewFile()) throw IllegalStateException("Could not create " + item.path + ".")
                created += target
                FileOutputStream(target).use { stream ->
                    stream.write(item.content.toByteArray(Charsets.UTF_8))
                    stream.fd.sync()
                }
            }
            return files.map { it.path }
        } catch (error: Exception) {
            created.asReversed().forEach { it.delete() }
            throw error
        }
    }

    fun exportZip(context: Context, projectId: String, destination: Uri) {
        val root = root(context, projectId)
        require(root.exists()) { "This project has no generated files to export." }
        val base = root.canonicalPath + File.separator
        val output = context.contentResolver.openOutputStream(destination)
            ?: throw IllegalStateException("Android could not open the selected export destination.")
        ZipOutputStream(output.buffered()).use { zip ->
            root.walkTopDown().filter { it.isFile && !java.nio.file.Files.isSymbolicLink(it.toPath()) }.forEach { file ->
                val canonical = file.canonicalFile
                require(canonical.path.startsWith(base)) { "A project file escaped the export root." }
                val relative = canonical.path.removePrefix(base).replace(File.separatorChar, '/')
                zip.putNextEntry(ZipEntry(relative))
                file.inputStream().buffered().use { it.copyTo(zip) }
                zip.closeEntry()
            }
        }
    }

    fun deleteWorkspace(context: Context, projectId: String) {
        val workspace = root(context, projectId)
        val projectsRoot = File(context.filesDir, "projects").canonicalFile
        require(workspace.path.startsWith(projectsRoot.path + File.separator))
        if (workspace.exists()) workspace.deleteRecursively()
    }
}
