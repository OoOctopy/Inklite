package com.inklite.app.gesture

import org.junit.Assert.*
import org.junit.Test
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

class GestureDetectorTest {
    private fun points(degrees: Double, radius: Double = 0.18, width: Int = 640, height: Int = 480): List<GestureDetector.Point> {
        val angle = degrees * PI / 180
        val short = minOf(width, height).toDouble()
        return List(21) { i ->
            if (i == 8) GestureDetector.Point(0.5 + radius * cos(angle) * short / width, 0.5 + radius * sin(angle) * short / height)
            else GestureDetector.Point(0.5, 0.5)
        }
    }

    private fun sweep(detector: GestureDetector, start: Double, direction: Int, firstTime: Long = 1000,
                      radius: Double = 0.18, invert: Boolean = false, width: Int = 640, height: Int = 480): List<Gesture> {
        return (0..18).map { i ->
            detector.update(points(start + i * 10 * direction, radius, width, height), width, height,
                            firstTime + i * 65, "Right", invert)
        }.filter { it != Gesture.NONE }
    }

    @Test fun clockwiseCrossesPiBoundary() {
        assertEquals(listOf(Gesture.ROTATE_CW), sweep(GestureDetector(), 170.0, 1))
    }
    @Test fun counterClockwiseCrossesPiBoundary() {
        assertEquals(listOf(Gesture.ROTATE_CCW), sweep(GestureDetector(), -170.0, -1))
    }
    @Test fun inversionSwapsDirection() {
        assertEquals(listOf(Gesture.ROTATE_CCW), sweep(GestureDetector(), 0.0, 1, invert = true))
    }
    @Test fun jitterDoesNotTrigger() {
        val detector = GestureDetector()
        for (i in 0..200) assertEquals(Gesture.NONE, detector.update(points(if (i % 2 == 0) 10.0 else -10.0), 640, 480, 1000L + i * 65, "Right"))
    }
    @Test fun smallRadiusCannotTrigger() {
        assertTrue(sweep(GestureDetector(), 0.0, 1, radius = 0.01).isEmpty())
    }
    @Test fun insufficientTrajectoryCannotTrigger() {
        val detector = GestureDetector(GestureConfig(minimumTrajectoryLength = 1.0))
        assertTrue(sweep(detector, 0.0, 1).isEmpty())
    }
    @Test fun continuousRotationOnlyEmitsOnce() {
        val detector = GestureDetector()
        val results = (0..100).map { i -> detector.update(points(i * 10.0), 640, 480, 1000L + i * 65, "Right") }
        assertEquals(1, results.count { it != Gesture.NONE })
    }
    @Test fun quietPeriodRearmsNextGesture() {
        val detector = GestureDetector()
        assertEquals(1, sweep(detector, 0.0, 1).size)
        for (i in 0..20) detector.update(points(180.0), 640, 480, 2250L + i * 65, "Right")
        assertEquals(listOf(Gesture.ROTATE_CCW), sweep(detector, 180.0, -1, firstTime = 3650))
    }
    @Test fun noHandResetsHistory() {
        val detector = GestureDetector()
        for (i in 0..7) detector.update(points(i * 10.0), 640, 480, 1000L + i * 65, "Right")
        detector.update(emptyList(), 640, 480, 1500)
        for (i in 8..14) assertEquals(Gesture.NONE, detector.update(points(i * 10.0), 640, 480, 1600L + i * 65, "Right"))
    }
    @Test fun longFrameGapsCannotAccumulate() {
        val detector = GestureDetector()
        for (i in 0..30) assertEquals(Gesture.NONE, detector.update(points(i * 10.0), 640, 480, 1000L + i * 400, "Right"))
    }
    @Test fun handednessSwitchResetsHistory() {
        val detector = GestureDetector()
        for (i in 0..20) assertEquals(Gesture.NONE, detector.update(points(i * 10.0), 640, 480, 1000L + i * 65, if (i < 10) "Right" else "Left"))
    }
    @Test fun landscapeAndPortraitAreEquivalent() {
        assertEquals(sweep(GestureDetector(), 0.0, 1, width = 640, height = 480),
                     sweep(GestureDetector(), 0.0, 1, width = 480, height = 640))
    }
    @Test fun invalidPointsAreRejected() {
        val detector = GestureDetector()
        val invalid = points(0.0).toMutableList().also { it[8] = GestureDetector.Point(Double.NaN, 0.5) }
        assertEquals(Gesture.NONE, detector.update(invalid, 640, 480, 1000))
    }
    @Test fun wrapHandlesBothBoundaries() {
        assertEquals(20.0 * PI / 180, GestureDetector.wrap(-340.0 * PI / 180), 1e-9)
        assertEquals(-20.0 * PI / 180, GestureDetector.wrap(340.0 * PI / 180), 1e-9)
    }
    @Test fun opposingMotionFailsDirectionConsistency() {
        val detector = GestureDetector(GestureConfig(historyWindowMs = 10000, smoothingAlpha = 1.0, noiseDegrees = 0.0))
        var angle = 0.0
        detector.update(points(angle), 640, 480, 1000, "Right")
        for (i in 1..40) {
            angle += if (i % 2 == 1) 20.0 else -10.0
            assertEquals(Gesture.NONE, detector.update(points(angle), 640, 480, 1000L + i * 65, "Right"))
        }
    }
    @Test fun motionOutsideHistoryWindowExpires() {
        val detector = GestureDetector()
        // Small valid inter-frame movements, but not enough rotation within any 1.6-second window.
        for (i in 0..60) assertEquals(Gesture.NONE, detector.update(points(i * 8.0), 640, 480, 1000L + i * 200, "Right"))
    }
    @Test fun reacquiringHandPreservesCooldown() {
        val detector = GestureDetector(GestureConfig(minimumSamples = 3, minimumDurationMs = 1,
                                                    smoothingAlpha = 1.0, noiseDegrees = 0.0))
        val first = (0..7).map { detector.update(points(it * 20.0), 640, 480, 1000L + it * 65, "Right") }
        assertEquals(1, first.count { it != Gesture.NONE })
        detector.update(emptyList(), 640, 480, 1480)
        for (i in 0..7) assertEquals(Gesture.NONE, detector.update(points(i * 20.0), 640, 480, 1500L + i * 65, "Right"))
    }
}
