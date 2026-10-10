package com.inklite.app.camera

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.view.View
import kotlin.math.min

/** Separate aspect-correct diagnostics panel; it does not claim alignment with PreviewView crops. */
class LandmarkView(context: Context) : View(context) {
    private var frame: HandFrame? = null
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.rgb(35, 96, 80)
        strokeWidth = 3f
    }
    private val connections = listOf(
        0 to 1, 1 to 2, 2 to 3, 3 to 4,
        0 to 5, 5 to 6, 6 to 7, 7 to 8,
        5 to 9, 9 to 10, 10 to 11, 11 to 12,
        9 to 13, 13 to 14, 14 to 15, 15 to 16,
        13 to 17, 0 to 17, 17 to 18, 18 to 19, 19 to 20
    )

    fun show(frame: HandFrame) { this.frame = frame; invalidate() }
    fun clear() { frame = null; invalidate() }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val data = frame ?: return
        if (data.points.size != 21) return
        val scale = min(width.toFloat() / data.imageWidth, height.toFloat() / data.imageHeight)
        val dx = (width - data.imageWidth * scale) / 2f
        val dy = (height - data.imageHeight * scale) / 2f
        fun x(i: Int) = dx + data.points[i].x.toFloat() * data.imageWidth * scale
        fun y(i: Int) = dy + data.points[i].y.toFloat() * data.imageHeight * scale
        paint.color = Color.rgb(35, 96, 80)
        for ((a, b) in connections) canvas.drawLine(x(a), y(a), x(b), y(b), paint)
        for (i in data.points.indices) {
            paint.color = if (i == 8) Color.rgb(196, 84, 36) else Color.rgb(35, 96, 80)
            canvas.drawCircle(x(i), y(i), if (i == 8) 6f else 4f, paint)
        }
    }
}
