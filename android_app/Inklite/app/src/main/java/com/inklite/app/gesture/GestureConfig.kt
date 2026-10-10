package com.inklite.app.gesture

data class GestureConfig(
    val rotationThresholdDegrees: Double = 120.0,
    val historyWindowMs: Long = 1600,
    val historySize: Int = 60,
    val minimumSamples: Int = 8,
    val minimumDurationMs: Long = 250,
    val minimumMovementRadius: Double = 0.045,
    val minimumTrajectoryLength: Double = 0.22,
    val smoothingAlpha: Double = 0.65,
    val noiseDegrees: Double = 1.0,
    val directionConsistency: Double = 0.82,
    val maximumStepDegrees: Double = 45.0,
    val maximumFrameGapMs: Long = 300,
    val maximumPalmJump: Double = 0.35,
    val cooldownMs: Long = 900,
    val rearmQuietMs: Long = 250,
    val rearmQuietDegrees: Double = 6.0,
    val invertRotationDirection: Boolean = false
) {
    init {
        require(rotationThresholdDegrees.isFinite() && rotationThresholdDegrees in 90.0..180.0)
        require(historyWindowMs > minimumDurationMs && minimumDurationMs > 0)
        require(historySize >= minimumSamples && minimumSamples >= 3)
        require(minimumMovementRadius.isFinite() && minimumMovementRadius > 0)
        require(minimumTrajectoryLength.isFinite() && minimumTrajectoryLength > 0)
        require(smoothingAlpha > 0 && smoothingAlpha <= 1)
        require(directionConsistency > 0.5 && directionConsistency <= 1)
        require(noiseDegrees.isFinite() && noiseDegrees >= 0 && noiseDegrees < maximumStepDegrees)
        require(maximumStepDegrees.isFinite() && maximumStepDegrees in 1.0..90.0)
        require(maximumFrameGapMs > 0 && maximumPalmJump.isFinite() && maximumPalmJump > 0)
        require(cooldownMs > 0 && rearmQuietMs > 0 && rearmQuietDegrees.isFinite() && rearmQuietDegrees > 0)
    }
}
