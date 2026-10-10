package com.inklite.app.camera

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Matrix
import android.os.SystemClock
import android.util.Log
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import com.inklite.app.R
import com.google.mediapipe.framework.image.BitmapImageBuilder
import com.google.mediapipe.tasks.core.BaseOptions
import com.google.mediapipe.tasks.core.Delegate
import com.google.mediapipe.tasks.vision.core.RunningMode
import com.google.mediapipe.tasks.vision.handlandmarker.HandLandmarker
import java.util.concurrent.atomic.AtomicBoolean

data class LandmarkPoint(val x: Double, val y: Double)

data class HandFrame(
    val points: List<LandmarkPoint>,
    val imageWidth: Int,
    val imageHeight: Int,
    val timestampMs: Long,
    val handedness: String?,
    val handCount: Int
)

/** All inference and native close calls run on the same single camera executor. */
class CameraAnalyzer(
    private val context: Context,
    private val onFrame: (HandFrame) -> Unit,
    private val onError: (String) -> Unit
) : ImageAnalysis.Analyzer {
    private var landmarker: HandLandmarker? = null
    private var lastTimestamp = -1L
    private var lastHandCount = -1
    private var lastErrorAt = Long.MIN_VALUE
    private val stopped = AtomicBoolean(false)

    private fun createLandmarker(): HandLandmarker {
        val base = BaseOptions.builder()
            .setModelAssetPath(CameraConfig.MODEL_ASSET)
            .setDelegate(Delegate.CPU)
            .build()
        val options = HandLandmarker.HandLandmarkerOptions.builder()
            .setBaseOptions(base)
            // Synchronous VIDEO inference on the analyzer thread avoids asynchronous bitmap lifetime races.
            .setRunningMode(RunningMode.VIDEO)
            .setNumHands(2)
            .setMinHandDetectionConfidence(CameraConfig.DETECTION_CONFIDENCE)
            .setMinHandPresenceConfidence(CameraConfig.PRESENCE_CONFIDENCE)
            .setMinTrackingConfidence(CameraConfig.TRACKING_CONFIDENCE)
            .build()
        return HandLandmarker.createFromOptions(context, options).also {
            Log.i("Inklite", "[LANDMARKS] Model initialized (CPU / VIDEO)")
        }
    }

    override fun analyze(image: ImageProxy) {
        var original: Bitmap? = null
        var rotated: Bitmap? = null
        try {
            if (stopped.get()) return
            val timestamp = SystemClock.uptimeMillis()
            if (timestamp - lastTimestamp < CameraConfig.MIN_FRAME_INTERVAL_MS) return
            lastTimestamp = timestamp
            val detector = landmarker ?: createLandmarker().also { landmarker = it }
            // CameraX toBitmap handles pixel/row strides. Rotation is applied once, before inference.
            original = image.toBitmap()
            val matrix = Matrix().apply {
                postRotate(image.imageInfo.rotationDegrees.toFloat())
                if (CameraConfig.USE_FRONT_CAMERA_FOR_TESTING) postScale(-1f, 1f)
            }
            val bitmap = Bitmap.createBitmap(original, 0, 0, original.width, original.height, matrix, true)
            rotated = bitmap
            val mpImage = BitmapImageBuilder(bitmap).build()
            val result = try {
                detector.detectForVideo(mpImage, timestamp)
            } finally {
                mpImage.close()
            }
            val count = result.landmarks().size
            if (count != lastHandCount) {
                Log.i("Inklite", "[LANDMARKS] Hands: $count; points per hand: ${result.landmarks().firstOrNull()?.size ?: 0}")
                lastHandCount = count
            }
            val points = if (count == 1) {
                result.landmarks()[0].map { LandmarkPoint(it.x().toDouble(), it.y().toDouble()) }
            } else emptyList()
            val label = if (count == 1) result.handedness().firstOrNull()?.firstOrNull()?.categoryName() else null
            if (!stopped.get()) onFrame(HandFrame(points, bitmap.width, bitmap.height, timestamp, label, count))
        } catch (error: LinkageError) {
            stopped.set(true)
            Log.e("Inklite", "[CAMERA] Native MediaPipe library unavailable", error)
            onError(context.getString(R.string.camera_native_unavailable))
        } catch (error: Exception) {
            stopped.set(true)
            val now = SystemClock.uptimeMillis()
            if (lastErrorAt == Long.MIN_VALUE || now - lastErrorAt > 3000) {
                lastErrorAt = now
                Log.e("Inklite", "[CAMERA] Analysis failed", error)
                onError(context.getString(R.string.camera_analysis_failed, error.message ?: error.javaClass.simpleName))
            }
        } finally {
            if (rotated !== original) rotated?.recycle()
            original?.recycle()
            // Always release frames, including early return and inference failures.
            image.close()
        }
    }

    fun stopAcceptingFrames() { stopped.set(true) }

    fun closeOnAnalyzerThread() {
        landmarker?.close()
        landmarker = null
    }
}
