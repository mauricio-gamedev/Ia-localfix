package io.github.mauriciogamedev.ialocalfix

import android.app.Application
import android.content.ComponentCallbacks2

class IaLocalfixApplication : Application() {
    lateinit var inference: LocalInference
        private set

    override fun onCreate() {
        super.onCreate()
        inference = LocalInference(this)
    }

    override fun onTrimMemory(level: Int) {
        super.onTrimMemory(level)
        if (level >= ComponentCallbacks2.TRIM_MEMORY_COMPLETE && ::inference.isInitialized) inference.unload()
    }
}
