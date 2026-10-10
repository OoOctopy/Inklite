package com.inklite.app.gesture

import java.util.ArrayDeque
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.hypot
import kotlin.math.min
import kotlin.math.sin

/** Pure Kotlin temporal detector. No camera, Android key, or communication APIs. */
class GestureDetector(private val config: GestureConfig = GestureConfig()) {
    data class Point(val x: Double, val y: Double)
    private data class Sample(val time: Long, val angle: Double, val point: Point)
    private val history = ArrayDeque<Sample>()
    private var previousRawAngle: Double? = null
    private var filteredAngle: Double? = null
    private var previousTime: Long? = null
    private var previousPalm: Point? = null
    private var previousHand: String? = null
    private var cooldownUntil = Long.MIN_VALUE
    private var armed = true
    private var quietAnchor: Double? = null
    private var quietSince = 0L

    fun reset() {
        history.clear()
        previousRawAngle = null
        filteredAngle = null
        previousTime = null
        previousPalm = null
        previousHand = null
        armed = true
        quietAnchor = null
        // Keep the cooldown even when tracking is lost, so reacquisition cannot duplicate a gesture.
    }

    fun update(
        landmarks: List<Point>, imageWidth: Int, imageHeight: Int, timestampMs: Long,
        handedness: String? = null, invertDirection: Boolean = config.invertRotationDirection
    ): Gesture {
        if (landmarks.size != 21 || imageWidth <= 0 || imageHeight <= 0 ||
            landmarks.any { !it.x.isFinite() || !it.y.isFinite() }) {
            reset()
            return Gesture.NONE
        }
        // Both axes use the shorter image dimension. atan2 on independently normalized x/y distorts angles.
        val shortSide = min(imageWidth, imageHeight).toDouble()
        fun scaled(point: Point) = Point(point.x * imageWidth / shortSide, point.y * imageHeight / shortSide)
        val palmIndices = listOf(0, 5, 9, 13, 17)
        val palm = Point(palmIndices.sumOf { scaled(landmarks[it]).x } / palmIndices.size,
                         palmIndices.sumOf { scaled(landmarks[it]).y } / palmIndices.size)
        val tip = scaled(landmarks[8])
        val dx = tip.x - palm.x
        val dy = tip.y - palm.y
        val radius = hypot(dx, dy)
        if (radius < config.minimumMovementRadius) {
            reset()
            return Gesture.NONE
        }
        val rawAngle = atan2(dy, dx)
        val lastTime = previousTime
        val lastPalm = previousPalm
        val identityChanged = previousHand != null && handedness != previousHand
        val gap = lastTime != null && (timestampMs <= lastTime || timestampMs - lastTime > config.maximumFrameGapMs)
        val palmJump = lastPalm != null && hypot(palm.x - lastPalm.x, palm.y - lastPalm.y) > config.maximumPalmJump
        if (identityChanged || gap || palmJump) reset()
        previousTime = timestampMs
        previousPalm = palm
        previousHand = handedness
        val oldRaw = previousRawAngle
        previousRawAngle = rawAngle
        if (oldRaw != null && abs(wrap(rawAngle - oldRaw)) > radians(config.maximumStepDegrees)) {
            history.clear()
            filteredAngle = rawAngle
            return Gesture.NONE
        }
        if (!armed) {
            val anchor = quietAnchor
            if (anchor == null || abs(wrap(rawAngle - anchor)) > radians(config.rearmQuietDegrees)) {
                quietAnchor = rawAngle
                quietSince = timestampMs
            }
            if (timestampMs < cooldownUntil || timestampMs - quietSince < config.rearmQuietMs) return Gesture.NONE
            armed = true
            quietAnchor = null
            history.clear()
            filteredAngle = rawAngle
        }
        if (timestampMs < cooldownUntil) {
            history.clear()
            filteredAngle = rawAngle
            return Gesture.NONE
        }
        val previous = filteredAngle
        var angle = if (previous == null) rawAngle else previous + config.smoothingAlpha * wrap(rawAngle - previous)
        if (previous != null && abs(angle - previous) < radians(config.noiseDegrees)) angle = previous
        filteredAngle = angle
        history.addLast(Sample(timestampMs, angle, Point(radius * cos(angle), radius * sin(angle))))
        while (history.size > config.historySize || (history.isNotEmpty() && timestampMs - history.first.time > config.historyWindowMs)) {
            history.removeFirst()
        }
        if (history.size < config.minimumSamples || timestampMs - history.first.time < config.minimumDurationMs) return Gesture.NONE
        var net = 0.0
        var totalAngle = 0.0
        var trajectory = 0.0
        var last: Sample? = null
        for (sample in history) {
            val previousSample = last
            if (previousSample != null) {
                val delta = wrap(sample.angle - previousSample.angle)
                net += delta
                totalAngle += abs(delta)
                trajectory += hypot(sample.point.x - previousSample.point.x, sample.point.y - previousSample.point.y)
            }
            last = sample
        }
        if (abs(net) < radians(config.rotationThresholdDegrees) || trajectory < config.minimumTrajectoryLength ||
            totalAngle == 0.0 || abs(net) / totalAngle < config.directionConsistency) return Gesture.NONE
        cooldownUntil = timestampMs + config.cooldownMs
        armed = false
        quietAnchor = rawAngle
        quietSince = timestampMs
        history.clear()
        // Image y increases downwards: a positive angular change is clockwise in the displayed image.
        val clockwise = (net > 0) != invertDirection
        return if (clockwise) Gesture.ROTATE_CW else Gesture.ROTATE_CCW
    }

    companion object {
        fun wrap(angle: Double): Double = atan2(sin(angle), cos(angle))
        private fun radians(degrees: Double): Double = degrees * PI / 180.0
    }
}
