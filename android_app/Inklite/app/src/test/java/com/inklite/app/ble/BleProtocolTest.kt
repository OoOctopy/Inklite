package com.inklite.app.ble

import com.inklite.app.input.InputCommand
import org.junit.Assert.*
import org.junit.Test

class BleProtocolTest {
    @Test fun writesAreSerializedInOrder() {
        val queue = CommandWriteQueue()
        InputCommand.entries.forEach { assertTrue(queue.offer(it)) }
        assertEquals(InputCommand.TAP, queue.startNext())
        assertNull(queue.startNext())
        assertEquals(InputCommand.TAP, queue.acknowledge())
        assertEquals(InputCommand.CW, queue.startNext())
        queue.acknowledge()
        assertEquals(InputCommand.CCW, queue.startNext())
        queue.acknowledge()
        assertNull(queue.startNext())
    }
    @Test fun capacityIncludesInFlight() {
        val queue = CommandWriteQueue(2)
        assertTrue(queue.offer(InputCommand.TAP))
        queue.startNext()
        assertTrue(queue.offer(InputCommand.CW))
        assertFalse(queue.offer(InputCommand.CCW))
        queue.acknowledge()
        assertTrue(queue.offer(InputCommand.CCW))
    }
    @Test fun disconnectDropsUnsentAndInFlightCommands() {
        val queue = CommandWriteQueue()
        queue.offer(InputCommand.TAP)
        queue.offer(InputCommand.CW)
        queue.startNext()
        queue.clear()
        assertNull(queue.acknowledge())
        assertNull(queue.startNext())
        queue.offer(InputCommand.CCW)
        assertEquals(InputCommand.CCW, queue.startNext())
    }
    @Test fun payloadIsExactlyTheThreeUtf8Words() {
        assertArrayEquals(byteArrayOf(84, 65, 80), InputCommand.TAP.name.toByteArray(Charsets.UTF_8))
        assertArrayEquals(byteArrayOf(67, 87), InputCommand.CW.name.toByteArray(Charsets.UTF_8))
        assertArrayEquals(byteArrayOf(67, 67, 87), InputCommand.CCW.name.toByteArray(Charsets.UTF_8))
    }
    @Test fun permissionListsFollowAndroidVersion() {
        assertArrayEquals(arrayOf("android.permission.ACCESS_FINE_LOCATION"), BlePermissions.required(30))
        assertArrayEquals(arrayOf("android.permission.BLUETOOTH_SCAN", "android.permission.BLUETOOTH_CONNECT"), BlePermissions.required(31))
    }
}
