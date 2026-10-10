package com.inklite.app.input

import android.view.KeyEvent
import com.inklite.app.gesture.Gesture
import org.junit.Assert.*
import org.junit.Test

class InputTest {
    @Test fun onlyVolumeButtonMapsToTap() {
        assertEquals(InputCommand.TAP, InputCommandMapper.fromVolumeButton())
        assertNull(InputCommandMapper.fromGesture(Gesture.NONE))
        assertEquals(InputCommand.CW, InputCommandMapper.fromGesture(Gesture.ROTATE_CW))
        assertEquals(InputCommand.CCW, InputCommandMapper.fromGesture(Gesture.ROTATE_CCW))
    }
    @Test fun longPressEmitsOneTap() {
        var count = 0
        val handler = VolumeKeyHandler { count++ }
        assertTrue(handler.handle(KeyEvent.KEYCODE_VOLUME_UP, KeyEvent.ACTION_DOWN, 0, 1000))
        for (i in 1..10) assertTrue(handler.handle(KeyEvent.KEYCODE_VOLUME_UP, KeyEvent.ACTION_DOWN, i, 1000L + i * 200))
        assertTrue(handler.handle(KeyEvent.KEYCODE_VOLUME_UP, KeyEvent.ACTION_UP, 0, 3200))
        assertEquals(1, count)
        handler.handle(KeyEvent.KEYCODE_VOLUME_UP, KeyEvent.ACTION_DOWN, 0, 3400)
        assertEquals(2, count)
    }
    @Test fun modeAllowsOnlySelectedKey() {
        var count = 0
        val handler = VolumeKeyHandler(mode = VolumeKeyMode.DOWN) { count++ }
        assertFalse(handler.handle(KeyEvent.KEYCODE_VOLUME_UP, KeyEvent.ACTION_DOWN, 0, 1000))
        assertTrue(handler.handle(KeyEvent.KEYCODE_VOLUME_DOWN, KeyEvent.ACTION_DOWN, 0, 1000))
        assertEquals(1, count)
    }
    @Test fun bounceAndCanceledDownDoNotDuplicateTap() {
        var count = 0
        val handler = VolumeKeyHandler { count++ }
        handler.handle(KeyEvent.KEYCODE_VOLUME_UP, KeyEvent.ACTION_DOWN, 0, 1000)
        handler.handle(KeyEvent.KEYCODE_VOLUME_UP, KeyEvent.ACTION_DOWN, 0, 1100)
        handler.handle(KeyEvent.KEYCODE_VOLUME_UP, KeyEvent.ACTION_UP, 0, 1110)
        handler.handle(KeyEvent.KEYCODE_VOLUME_UP, KeyEvent.ACTION_DOWN, 0, 1120)
        handler.handle(KeyEvent.KEYCODE_VOLUME_DOWN, KeyEvent.ACTION_DOWN, 0, 1300, canceled = true)
        assertEquals(1, count)
    }
    @Test fun unrelatedKeysAreNotConsumed() {
        val handler = VolumeKeyHandler { fail("Unexpected TAP") }
        assertFalse(handler.handle(KeyEvent.KEYCODE_BACK, KeyEvent.ACTION_DOWN, 0, 1000))
    }
    @Test fun repeatedDownAfterResumeDoesNotConfirm() {
        var count = 0
        val handler = VolumeKeyHandler { count++ }
        handler.reset()
        handler.handle(KeyEvent.KEYCODE_VOLUME_UP, KeyEvent.ACTION_DOWN, 3, 1000)
        assertEquals(0, count)
    }
}
