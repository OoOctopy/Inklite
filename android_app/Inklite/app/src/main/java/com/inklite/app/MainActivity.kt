package com.inklite.app

import android.Manifest
import android.bluetooth.BluetoothAdapter
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.util.Log
import android.view.Gravity
import android.view.KeyEvent
import android.view.Surface
import android.view.View
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.CheckBox
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Spinner
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.core.content.edit
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.lifecycle.Lifecycle
import com.inklite.app.camera.CameraAnalyzer
import com.inklite.app.camera.CameraConfig
import com.inklite.app.camera.LandmarkView
import com.inklite.app.ble.BleCommandSender
import com.inklite.app.ble.BlePermissions
import com.inklite.app.ble.BleState
import com.inklite.app.gesture.Gesture
import com.inklite.app.gesture.GestureConfig
import com.inklite.app.gesture.GestureDetector
import com.inklite.app.input.InputCommand
import com.inklite.app.input.InputConfig
import com.inklite.app.input.InputCommandMapper
import com.inklite.app.input.VolumeKeyHandler
import com.inklite.app.input.VolumeKeyMode
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger

class MainActivity : ComponentActivity() {
    private lateinit var preview: PreviewView
    private lateinit var status: TextView
    private lateinit var handStatus: TextView
    private lateinit var landmarks: LandmarkView
    private lateinit var lastCommand: TextView
    private lateinit var bleStatus: TextView
    private lateinit var bleConnect: Button
    private lateinit var bleDisconnect: Button
    private lateinit var bleSender: BleCommandSender
    private val debugButtons = mutableListOf<Button>()
    private val preferences by lazy { getPreferences(MODE_PRIVATE) }
    private val rotationEnabled = AtomicBoolean(false)
    private val invertRotation = AtomicBoolean(GestureConfig().invertRotationDirection)
    private val inputRevision = AtomicInteger(0)
    private var volumeKeyHandler = createVolumeKeyHandler(InputConfig.DEFAULT_VOLUME_KEY_MODE)
    private var provider: ProcessCameraProvider? = null
    private var analysis: ImageAnalysis? = null
    private var analyzer: CameraAnalyzer? = null
    private var generation = 0
    private val cameraExecutor = Executors.newSingleThreadExecutor()
    // Camera denial leaves physical TAP and the separate BLE permission flow usable.
    private val permission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) startCamera() else status.setText(R.string.camera_permission_denied)
    }
    private val blePermission = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
        if (BlePermissions.granted(this)) startBleConnection()
        else bleStatus.setText(R.string.ble_permissions_denied)
    }
    private val bluetoothEnable = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) {
        if (BlePermissions.granted(this) && bleSender.bluetoothEnabled()) bleSender.scanAndConnect()
        else bleStatus.setText(R.string.ble_enable_bluetooth)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            val padding = (16 * resources.displayMetrics.density).toInt()
            setPadding(padding, padding, padding, padding)
        }
        layout.addView(TextView(this).apply {
            setText(R.string.app_title)
            textSize = 22f
            gravity = Gravity.CENTER
        })
        status = TextView(this).apply { setText(R.string.camera_rear_preview); textSize = 16f }
        layout.addView(status)
        preview = PreviewView(this).apply {
            implementationMode = PreviewView.ImplementationMode.COMPATIBLE
            scaleType = PreviewView.ScaleType.FIT_CENTER
            contentDescription = getString(R.string.camera_preview_description)
        }
        layout.addView(preview, LinearLayout.LayoutParams(-1, (250 * resources.displayMetrics.density).toInt()))
        handStatus = TextView(this).apply { setText(R.string.hand_show_one) }
        layout.addView(handStatus)
        landmarks = LandmarkView(this)
        landmarks.contentDescription = getString(R.string.landmarks_description)
        layout.addView(landmarks, LinearLayout.LayoutParams(-1, (140 * resources.displayMetrics.density).toInt()))
        rotationEnabled.set(preferences.getBoolean("rotationEnabled", false))
        invertRotation.set(preferences.getBoolean("invertRotation", GestureConfig().invertRotationDirection))
        layout.addView(CheckBox(this).apply {
            setText(R.string.rotation_enable)
            isChecked = rotationEnabled.get()
            setOnCheckedChangeListener { _, enabled ->
                rotationEnabled.set(enabled)
                inputRevision.incrementAndGet()
                preferences.edit { putBoolean("rotationEnabled", enabled) }
            }
        })
        layout.addView(CheckBox(this).apply {
            setText(R.string.rotation_invert)
            isChecked = invertRotation.get()
            setOnCheckedChangeListener { _, inverted ->
                invertRotation.set(inverted)
                inputRevision.incrementAndGet()
                preferences.edit { putBoolean("invertRotation", inverted) }
            }
        })
        layout.addView(TextView(this).apply { setText(R.string.volume_key_label) })
        val modes = VolumeKeyMode.entries
        val defaultMode = InputConfig.DEFAULT_VOLUME_KEY_MODE
        val selectedMode = runCatching { VolumeKeyMode.valueOf(preferences.getString("volumeMode", defaultMode.name) ?: defaultMode.name) }
            .getOrDefault(defaultMode)
        volumeKeyHandler = createVolumeKeyHandler(selectedMode)
        layout.addView(Spinner(this).apply {
            adapter = ArrayAdapter(this@MainActivity, android.R.layout.simple_spinner_dropdown_item,
                                  resources.getStringArray(R.array.volume_key_modes).toList())
            setSelection(modes.indexOf(selectedMode))
            onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
                override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) {
                    volumeKeyHandler = createVolumeKeyHandler(modes[position])
                    preferences.edit { putString("volumeMode", modes[position].name) }
                }
                override fun onNothingSelected(parent: AdapterView<*>?) = Unit
            }
        })
        lastCommand = TextView(this).apply { setText(R.string.last_input_none); textSize = 18f }
        layout.addView(lastCommand)
        layout.addView(TextView(this).apply {
            setText(R.string.input_instructions)
        })
        layout.addView(Button(this).apply {
            setText(R.string.camera_retry)
            setOnClickListener { requestCamera() }
        })
        addBleControls(layout)
        val scroll = ScrollView(this).apply { addView(layout) }
        // targetSdk 35 uses edge-to-edge on Android 15; keep controls clear of system bars/cutouts.
        ViewCompat.setOnApplyWindowInsetsListener(scroll) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            insets
        }
        setContentView(scroll)
        ViewCompat.requestApplyInsets(scroll)
        if (!hasCameraPermission()) requestCamera()
    }

    private fun hasCameraPermission() =
        ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED

    private fun requestCamera() {
        if (hasCameraPermission()) startCamera() else permission.launch(Manifest.permission.CAMERA)
    }

    override fun onStart() {
        super.onStart()
        if (hasCameraPermission()) startCamera()
    }

    private fun startCamera() {
        if (!lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) return
        stopCamera()
        val requestGeneration = generation
        status.setText(R.string.camera_starting)
        preview.post {
            if (requestGeneration != generation || isDestroyed) return@post
            val future = ProcessCameraProvider.getInstance(this)
            future.addListener({
                if (requestGeneration != generation || !lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) return@addListener
                try {
                    val cameraProvider = future.get()
                    provider = cameraProvider
                    val selector = if (CameraConfig.USE_FRONT_CAMERA_FOR_TESTING) {
                        CameraSelector.DEFAULT_FRONT_CAMERA
                    } else CameraSelector.DEFAULT_BACK_CAMERA
                    check(cameraProvider.hasCamera(selector)) { getString(R.string.camera_unavailable) }
                    val targetRotation = preview.display?.rotation ?: Surface.ROTATION_0
                    val cameraPreview = Preview.Builder().setTargetRotation(targetRotation).build()
                        .also { it.setSurfaceProvider(preview.surfaceProvider) }
                    val gestureDetector = GestureDetector()
                    var seenRevision = -1
                    val cameraAnalyzer = CameraAnalyzer(applicationContext, onFrame = { frame ->
                        val revision = inputRevision.get()
                        if (revision != seenRevision) {
                            gestureDetector.reset()
                            seenRevision = revision
                        }
                        val gesture = if (rotationEnabled.get()) {
                            gestureDetector.update(frame.points.map { GestureDetector.Point(it.x, it.y) },
                                                   frame.imageWidth, frame.imageHeight, frame.timestampMs,
                                                   frame.handedness, invertRotation.get())
                        } else {
                            gestureDetector.reset()
                            Gesture.NONE
                        }
                        runOnUiThread {
                            if (requestGeneration == generation && lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) {
                                landmarks.show(frame)
                                handStatus.text = when (frame.handCount) {
                                    0 -> getString(R.string.hand_none)
                                    1 -> resources.getQuantityString(R.plurals.hand_detected, frame.points.size, frame.points.size)
                                    else -> getString(R.string.hand_multiple)
                                }
                                // Drop results calculated before a setting change or camera lifecycle transition.
                                if (revision == inputRevision.get() && rotationEnabled.get() && gesture != Gesture.NONE &&
                                    lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED) && hasWindowFocus()) {
                                    Log.i("Inklite", "[GESTURE] $gesture")
                                    InputCommandMapper.fromGesture(gesture)?.let(::publishCommand)
                                }
                            }
                        }
                    }, onError = { message ->
                        gestureDetector.reset()
                        runOnUiThread {
                            if (requestGeneration == generation) {
                                status.text = message
                                handStatus.setText(R.string.hand_none)
                                landmarks.clear()
                            }
                        }
                    })
                    analyzer = cameraAnalyzer
                    val cameraAnalysis = ImageAnalysis.Builder()
                        .setTargetRotation(targetRotation)
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
                        .build()
                    analysis = cameraAnalysis
                    cameraAnalysis.setAnalyzer(cameraExecutor, cameraAnalyzer)
                    cameraProvider.bindToLifecycle(this, selector, cameraPreview, cameraAnalysis)
                    status.setText(if (CameraConfig.USE_FRONT_CAMERA_FOR_TESTING) R.string.camera_front_testing else R.string.camera_rear_ready)
                    Log.i("Inklite", "[CAMERA] ${if (CameraConfig.USE_FRONT_CAMERA_FOR_TESTING) "Front" else "Rear"} preview bound")
                } catch (error: Exception) {
                    stopCamera()
                    Log.e("Inklite", "[CAMERA] Preview failed", error)
                    status.text = getString(R.string.camera_bind_failed, error.message ?: error.javaClass.simpleName)
                }
            }, ContextCompat.getMainExecutor(this))
        }
    }

    private fun stopCamera() {
        generation++
        val oldAnalyzer = analyzer
        oldAnalyzer?.stopAcceptingFrames()
        analysis?.clearAnalyzer()
        provider?.unbindAll()
        analysis = null
        analyzer = null
        if (oldAnalyzer != null) {
            cameraExecutor.execute {
                try { oldAnalyzer.closeOnAnalyzerThread() }
                catch (error: Exception) { Log.e("Inklite", "[CAMERA] Close failed", error) }
            }
        }
        if (::landmarks.isInitialized) landmarks.clear()
    }

    override fun onStop() {
        volumeKeyHandler.reset()
        stopCamera()
        super.onStop()
    }

    override fun onDestroy() {
        if (::bleSender.isInitialized) bleSender.disconnect()
        cameraExecutor.shutdown()
        super.onDestroy()
    }

    private fun createVolumeKeyHandler(mode: VolumeKeyMode) = VolumeKeyHandler(mode = mode) {
        Log.i("Inklite", "[INPUT] Volume key detected")
        publishCommand(InputCommandMapper.fromVolumeButton())
    }

    override fun onKeyDown(keyCode: Int, event: KeyEvent): Boolean {
        if (lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED) &&
            volumeKeyHandler.handle(keyCode, event.action, event.repeatCount, event.eventTime, event.isCanceled)) {
            return true
        }
        return super.onKeyDown(keyCode, event)
    }

    override fun onKeyUp(keyCode: Int, event: KeyEvent): Boolean {
        if (lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED) &&
            volumeKeyHandler.handle(keyCode, event.action, event.repeatCount, event.eventTime, event.isCanceled)) {
            return true
        }
        return super.onKeyUp(keyCode, event)
    }

    private fun publishCommand(command: InputCommand) {
        Log.i("Inklite", "[COMMAND] $command")
        val meaning = when (command) {
            InputCommand.TAP -> R.string.input_confirm
            InputCommand.CW -> R.string.input_next
            InputCommand.CCW -> R.string.input_back
        }
        lastCommand.text = getString(R.string.input_last, command.name, getString(meaning))
        if (::bleSender.isInitialized) bleSender.send(command)
    }

    private fun addBleControls(layout: LinearLayout) {
        bleStatus = TextView(this).apply { setText(R.string.ble_disconnected) }
        layout.addView(bleStatus)
        bleConnect = Button(this).apply {
            setText(R.string.ble_connect_button)
            setOnClickListener {
                if (BlePermissions.granted(this@MainActivity)) startBleConnection()
                else blePermission.launch(BlePermissions.required())
            }
        }
        bleDisconnect = Button(this).apply {
            setText(R.string.ble_disconnect_button)
            isEnabled = false
            setOnClickListener { bleSender.disconnect() }
        }
        layout.addView(bleConnect)
        layout.addView(bleDisconnect)
        // Manual packets are explicitly development controls, not camera/normal TAP recognition.
        if (BuildConfig.DEBUG) {
            layout.addView(TextView(this).apply { setText(R.string.ble_debug_label) })
            val buttons = LinearLayout(this).apply { orientation = LinearLayout.HORIZONTAL }
            InputCommand.entries.forEach { command ->
                val button = Button(this).apply {
                    text = command.name
                    isEnabled = false
                    setOnClickListener {
                        Log.i("Inklite", "[DEBUG] Manual BLE test: $command")
                        publishCommand(command)
                    }
                }
                debugButtons.add(button)
                buttons.addView(button, LinearLayout.LayoutParams(0, -2, 1f))
            }
            layout.addView(buttons)
        }
        bleSender = BleCommandSender(this) { state, message ->
            bleStatus.text = message
            bleConnect.isEnabled = state == BleState.DISCONNECTED || state == BleState.ERROR
            bleDisconnect.isEnabled = state != BleState.DISCONNECTED
            debugButtons.forEach { it.isEnabled = state == BleState.READY }
        }
    }

    private fun startBleConnection() {
        if (!BlePermissions.granted(this)) { bleStatus.setText(R.string.ble_permissions_denied); return }
        if (!bleSender.hasHardware()) { bleSender.scanAndConnect(); return }
        if (!bleSender.bluetoothEnabled()) {
            try { bluetoothEnable.launch(Intent(BluetoothAdapter.ACTION_REQUEST_ENABLE)) }
            catch (error: Exception) { bleStatus.setText(R.string.ble_enable_bluetooth) }
        } else bleSender.scanAndConnect()
    }
}
