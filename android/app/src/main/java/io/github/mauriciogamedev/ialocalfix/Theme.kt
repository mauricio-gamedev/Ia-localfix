package io.github.mauriciogamedev.ialocalfix

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LocalfixColors = darkColorScheme(
    primary = Color(0xFF55D6C2),
    onPrimary = Color(0xFF06201D),
    secondary = Color(0xFF9BD8D0),
    background = Color(0xFF050708),
    surface = Color(0xFF101617),
    surfaceVariant = Color(0xFF1A2425),
    onSurface = Color(0xFFE7F0EF),
    onSurfaceVariant = Color(0xFFA9B9B7),
    error = Color(0xFFFF8A80)
)

@Composable
fun LocalfixTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = LocalfixColors, content = content)
}
