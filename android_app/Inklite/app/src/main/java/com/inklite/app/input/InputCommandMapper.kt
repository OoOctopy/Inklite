package com.inklite.app.input

import com.inklite.app.gesture.Gesture

object InputCommandMapper {
    fun fromVolumeButton() = InputCommand.TAP
    fun fromGesture(gesture: Gesture): InputCommand? = when (gesture) {
        Gesture.NONE -> null
        Gesture.ROTATE_CW -> InputCommand.CW
        Gesture.ROTATE_CCW -> InputCommand.CCW
    }
}
