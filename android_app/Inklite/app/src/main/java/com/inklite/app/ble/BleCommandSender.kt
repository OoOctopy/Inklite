package com.inklite.app.ble

import android.annotation.SuppressLint
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.BluetoothStatusCodes
import android.bluetooth.le.BluetoothLeScanner
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanFilter
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.content.pm.PackageManager
import android.location.LocationManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.os.ParcelUuid
import android.util.Log
import androidx.core.location.LocationManagerCompat
import com.inklite.app.R
import com.inklite.app.input.InputCommand

enum class BleState { DISCONNECTED, SCANNING, CONNECTING, DISCOVERING, READY, ERROR }

/** BLE only. All mutable state is on the main looper; radio callbacks are serialized onto it.
 * Lint cannot infer permission checks across asynchronous callbacks. Every action checks grants,
 * and every radio operation handles revocation (SecurityException), including teardown.
 */
@SuppressLint("MissingPermission")
class BleCommandSender(context: Context, private val onState: (BleState, String) -> Unit) {
    private val context = context.applicationContext
    private val main = Handler(Looper.getMainLooper())
    private val adapter = context.getSystemService(BluetoothManager::class.java)?.adapter
    private var scanner: BluetoothLeScanner? = null
    private var scanCallback: ScanCallback? = null
    private var gatt: BluetoothGatt? = null
    private var characteristic: BluetoothGattCharacteristic? = null
    private var deadline: Runnable? = null
    private var writeDeadline: Runnable? = null
    private val queue = CommandWriteQueue()
    var state = BleState.DISCONNECTED
        private set

    private fun status(newState: BleState, message: String) {
        state = newState
        Log.i("Inklite", "[BLE] $message")
        onState(newState, message)
    }

    fun hasHardware(): Boolean = adapter != null &&
        context.packageManager.hasSystemFeature(PackageManager.FEATURE_BLUETOOTH_LE)

    fun bluetoothEnabled(): Boolean = try {
        BlePermissions.canConnect(context) && adapter?.isEnabled == true
    } catch (_: SecurityException) { false }

    fun scanAndConnect() {
        check(Looper.myLooper() == main.looper)
        if (state in setOf(BleState.SCANNING, BleState.CONNECTING, BleState.DISCOVERING, BleState.READY)) return
        if (!BlePermissions.granted(context)) {
            status(BleState.ERROR, context.getString(R.string.ble_permissions_denied)); return
        }
        if (!hasHardware()) { status(BleState.ERROR, context.getString(R.string.ble_unavailable)); return }
        if (!bluetoothEnabled()) { status(BleState.ERROR, context.getString(R.string.ble_enable_bluetooth)); return }
        if (Build.VERSION.SDK_INT < 31) {
            val location = context.getSystemService(LocationManager::class.java)
            if (location == null || !LocationManagerCompat.isLocationEnabled(location)) {
                status(BleState.ERROR, context.getString(R.string.ble_legacy_location)); return
            }
        }
        try {
            val radio = adapter?.bluetoothLeScanner ?: error("BLE scanner unavailable")
            val callback = object : ScanCallback() {
                override fun onScanResult(callbackType: Int, result: ScanResult) {
                    main.post {
                        if (scanCallback === this && state == BleState.SCANNING) connect(result.device)
                    }
                }
                override fun onBatchScanResults(results: MutableList<ScanResult>) {
                    results.firstOrNull()?.let { onScanResult(0, it) }
                }
                override fun onScanFailed(errorCode: Int) {
                    main.post { if (scanCallback === this) fail(context.getString(R.string.ble_scan_failed, errorCode)) }
                }
            }
            scanner = radio
            scanCallback = callback
            status(BleState.SCANNING, context.getString(R.string.ble_scanning))
            radio.startScan(listOf(ScanFilter.Builder().setServiceUuid(ParcelUuid(BleConfig.SERVICE_UUID)).build()),
                ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build(), callback)
            armDeadline(BleConfig.SCAN_TIMEOUT_MS) { fail(context.getString(R.string.ble_scan_timeout)) }
        } catch (error: Exception) { fail(context.getString(R.string.ble_operation_failed, error.message ?: error.javaClass.simpleName)) }
    }

    private fun stopScan() {
        val callback = scanCallback
        scanCallback = null
        try { if (callback != null) scanner?.stopScan(callback) }
        catch (error: Exception) { Log.w("Inklite", "[BLE] Could not stop an unavailable scanner", error) }
        scanner = null
        cancelDeadline()
    }

    private fun connect(device: BluetoothDevice) {
        stopScan()
        if (!BlePermissions.canConnect(context)) { fail(context.getString(R.string.ble_permissions_denied)); return }
        status(BleState.CONNECTING, context.getString(R.string.ble_connecting))
        try {
            val callback = object : BluetoothGattCallback() {
                override fun onConnectionStateChange(connection: BluetoothGatt, result: Int, newState: Int) {
                    main.post {
                        if (gatt !== connection) return@post
                        if (result != BluetoothGatt.GATT_SUCCESS || newState == BluetoothProfile.STATE_DISCONNECTED) {
                            fail(context.getString(R.string.ble_disconnected_status, result)); return@post
                        }
                        if (newState == BluetoothProfile.STATE_CONNECTED) {
                            if (!BlePermissions.canConnect(context)) { fail(context.getString(R.string.ble_permissions_denied)); return@post }
                            status(BleState.DISCOVERING, context.getString(R.string.ble_discovering))
                            armDeadline(BleConfig.DISCOVERY_TIMEOUT_MS) { fail(context.getString(R.string.ble_discovery_timeout)) }
                            try {
                                if (!connection.discoverServices()) fail(context.getString(R.string.ble_discovery_failed))
                            } catch (error: SecurityException) { fail(context.getString(R.string.ble_permissions_denied)) }
                        }
                    }
                }
                override fun onServicesDiscovered(connection: BluetoothGatt, result: Int) {
                    main.post {
                        if (gatt !== connection || state != BleState.DISCOVERING) return@post
                        if (result != BluetoothGatt.GATT_SUCCESS) { fail(context.getString(R.string.ble_discovery_failed)); return@post }
                        if (!BlePermissions.canConnect(context)) { fail(context.getString(R.string.ble_permissions_denied)); return@post }
                        try {
                            val command = connection.getService(BleConfig.SERVICE_UUID)?.getCharacteristic(BleConfig.COMMAND_CHARACTERISTIC_UUID)
                            if (command == null || command.properties and BluetoothGattCharacteristic.PROPERTY_WRITE == 0) {
                                fail(context.getString(R.string.ble_characteristic_missing)); return@post
                            }
                            characteristic = command
                            cancelDeadline()
                            status(BleState.READY, context.getString(R.string.ble_ready))
                        } catch (error: SecurityException) { fail(context.getString(R.string.ble_permissions_denied)) }
                    }
                }
                override fun onCharacteristicWrite(connection: BluetoothGatt, written: BluetoothGattCharacteristic, result: Int) {
                    main.post {
                        if (gatt !== connection || written.uuid != BleConfig.COMMAND_CHARACTERISTIC_UUID || queue.inFlight == null) return@post
                        cancelWriteDeadline()
                        if (result != BluetoothGatt.GATT_SUCCESS) { fail(context.getString(R.string.ble_write_failed, result)); return@post }
                        val command = queue.acknowledge() ?: return@post
                        Log.i("Inklite", "[BLE] Sent: $command")
                        status(BleState.READY, context.getString(R.string.ble_sent, command.name))
                        writeNext()
                    }
                }
            }
            gatt = device.connectGatt(context, false, callback, BluetoothDevice.TRANSPORT_LE,
                BluetoothDevice.PHY_LE_1M_MASK, main)
            if (gatt == null) { fail(context.getString(R.string.ble_connect_failed)); return }
            armDeadline(BleConfig.CONNECT_TIMEOUT_MS) { fail(context.getString(R.string.ble_connect_timeout)) }
        } catch (error: Exception) { fail(context.getString(R.string.ble_operation_failed, error.message ?: error.javaClass.simpleName)) }
    }

    fun send(command: InputCommand): Boolean {
        check(Looper.myLooper() == main.looper)
        if (state != BleState.READY) {
            Log.i("Inklite", "[BLE] Not connected; dropped: $command")
            return false
        }
        if (!BlePermissions.canConnect(context)) { fail(context.getString(R.string.ble_permissions_denied)); return false }
        if (!queue.offer(command)) {
            Log.w("Inklite", "[BLE] Queue full; dropped: $command")
            status(BleState.READY, context.getString(R.string.ble_queue_full))
            return false
        }
        writeNext()
        return state == BleState.READY
    }

    @Suppress("DEPRECATION")
    private fun writeNext() {
        if (state != BleState.READY) return
        val command = queue.startNext() ?: return
        val connection = gatt
        val target = characteristic
        if (connection == null || target == null || !BlePermissions.canConnect(context)) {
            fail(context.getString(R.string.ble_permissions_denied)); return
        }
        try {
            val payload = command.name.toByteArray(Charsets.UTF_8)
            val accepted = if (Build.VERSION.SDK_INT >= 33) {
                connection.writeCharacteristic(target, payload, BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT) == BluetoothStatusCodes.SUCCESS
            } else {
                target.writeType = BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT
                target.value = payload
                connection.writeCharacteristic(target)
            }
            if (!accepted) { fail(context.getString(R.string.ble_write_not_started)); return }
            Log.i("Inklite", "[BLE] Sending: $command")
            val timeout = Runnable { fail(context.getString(R.string.ble_write_timeout)) }
            writeDeadline = timeout
            main.postDelayed(timeout, BleConfig.WRITE_TIMEOUT_MS)
        } catch (error: Exception) { fail(context.getString(R.string.ble_operation_failed, error.message ?: error.javaClass.simpleName)) }
    }

    private fun armDeadline(timeoutMs: Long, action: () -> Unit) {
        cancelDeadline()
        deadline = Runnable(action).also { main.postDelayed(it, timeoutMs) }
    }
    private fun cancelDeadline() { deadline?.let(main::removeCallbacks); deadline = null }
    private fun cancelWriteDeadline() { writeDeadline?.let(main::removeCallbacks); writeDeadline = null }

    private fun releaseConnection() {
        stopScan()
        cancelWriteDeadline()
        queue.clear()
        characteristic = null
        val connection = gatt
        gatt = null // Invalidate callbacks before disconnecting; a late callback cannot touch a new session.
        try { connection?.disconnect() } catch (error: Exception) { Log.w("Inklite", "[BLE] Disconnect failed", error) }
        try { connection?.close() } catch (error: Exception) { Log.w("Inklite", "[BLE] Close failed", error) }
    }
    private fun fail(message: String) { releaseConnection(); status(BleState.ERROR, message) }
    fun disconnect() {
        check(Looper.myLooper() == main.looper)
        releaseConnection()
        status(BleState.DISCONNECTED, context.getString(R.string.ble_disconnected))
    }
}
