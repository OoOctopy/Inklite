package com.inklite.app.input

import android.view.KeyEvent

enum class VolumeKeyMode { BOTH, UP, DOWN }

class VolumeKeyHandler(
    private val mode: VolumeKeyMode = InputConfig.DEFAULT_VOLUME_KEY_MODE,
    private val debounceMs: Long = InputConfig.VOLUME_DEBOUNCE_MS,
    private val onTap: () -> Unit
) {
    private val pressed = mutableSetOf<Int>()
    private var lastTapTime: Long? = null

    init { require(debounceMs >= 0) }

    /** Return true for configured keys, consuming both down and up without changing audio volume. */
    fun handle(keyCode: Int, action: Int, repeatCount: Int, eventTimeMs: Long, canceled: Boolean = false): Boolean {
        val selected = when (keyCode) {
            KeyEvent.KEYCODE_VOLUME_UP -> mode != VolumeKeyMode.DOWN
            KeyEvent.KEYCODE_VOLUME_DOWN -> mode != VolumeKeyMode.UP
            else -> false
        }
        if (!selected) return false
        if (action == KeyEvent.ACTION_UP) {
            pressed.remove(keyCode)
        } else if (action == KeyEvent.ACTION_DOWN && repeatCount == 0 && pressed.add(keyCode) && !canceled) {
            val last = lastTapTime
            if (last == null || eventTimeMs - last >= debounceMs) {
                lastTapTime = eventTimeMs
                onTap()
            }
        }
        return true
    }

    fun reset() {
        pressed.clear()
        lastTapTime = null
    }
}
