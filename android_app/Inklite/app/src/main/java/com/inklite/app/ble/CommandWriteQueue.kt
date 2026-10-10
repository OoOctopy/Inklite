package com.inklite.app.ble

import com.inklite.app.input.InputCommand
import java.util.ArrayDeque

/** Single in-flight write. The sender clears the queue on every disconnect; commands are never replayed. */
class CommandWriteQueue(private val capacity: Int = BleConfig.MAX_PENDING_COMMANDS) {
    private val pending = ArrayDeque<InputCommand>()
    var inFlight: InputCommand? = null
        private set
    init { require(capacity > 0) }

    fun offer(command: InputCommand): Boolean {
        if (pending.size + (if (inFlight == null) 0 else 1) >= capacity) return false
        pending.addLast(command)
        return true
    }

    fun startNext(): InputCommand? {
        if (inFlight != null) return null
        inFlight = pending.pollFirst()
        return inFlight
    }

    fun acknowledge(): InputCommand? {
        val command = inFlight
        inFlight = null
        return command
    }

    fun clear() { pending.clear(); inFlight = null }
}
