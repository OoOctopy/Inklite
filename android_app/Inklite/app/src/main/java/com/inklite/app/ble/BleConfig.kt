package com.inklite.app.ble

import java.util.UUID

object BleConfig {
    val SERVICE_UUID: UUID = UUID.fromString("72fbb2cc-949e-4a4e-9c23-03f50a0798cb")
    val COMMAND_CHARACTERISTIC_UUID: UUID = UUID.fromString("10fc5a67-f00e-4d52-94c2-673a573b6722")
    const val SCAN_TIMEOUT_MS = 15_000L
    const val CONNECT_TIMEOUT_MS = 15_000L
    const val DISCOVERY_TIMEOUT_MS = 10_000L
    const val WRITE_TIMEOUT_MS = 5_000L
    const val MAX_PENDING_COMMANDS = 8
}
