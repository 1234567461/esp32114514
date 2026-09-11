"""
树莓派 GPIO 控制模块
提供 LED、蜂鸣器、继电器、电机驱动、温湿度传感器(DHT11/DHT22)的统一控制接口。
当运行环境缺少 RPi.GPIO 时自动降级为 Mock 模式，所有方法返回 dict，不抛出异常。
"""
import time
import threading
from typing import Dict, Optional

# 尝试导入 RPi.GPIO；若不可用则启用 Mock 模式
try:
    import RPi.GPIO as _RPI_GPIO  # type: ignore
    GPIO_AVAILABLE = True
except Exception:
    _RPI_GPIO = None
    GPIO_AVAILABLE = False

# 尝试导入 DHT 传感器库（Adafruit_DHT 或 board+adafruit_dht）；不可用时 Mock
try:
    import Adafruit_DHT as _DHT_LIB  # type: ignore
    DHT_AVAILABLE = True
except Exception:
    _DHT_LIB = None
    DHT_AVAILABLE = False


class PiGPIO:
    """树莓派 GPIO 控制器，统一管理 LED / 蜂鸣器 / 继电器 / 电机 / 温湿度传感器。

    所有方法均返回 dict，即使底层 GPIO 不可用也只返回包含 mock/error 标记的结果，
    不会向调用方抛出异常。
    """

    # 默认引脚映射（BCM 编号），可在实例化时覆盖
    DEFAULT_PINS = {
        "led": 17,
        "buzzer": 18,
        "relay": 22,
        "motor_in1": 23,
        "motor_in2": 24,
        "motor_pwm": 25,
        "dht": 4,
    }

    def __init__(self, pins: Optional[Dict[str, int]] = None, dht_type: str = "DHT11"):
        """初始化 GPIO 控制器。

        :param pins: 自定义引脚映射，缺省使用 DEFAULT_PINS
        :param dht_type: 温湿度传感器型号，"DHT11" 或 "DHT22"
        """
        self.pins = dict(self.DEFAULT_PINS)
        if pins:
            self.pins.update(pins)
        self.dht_type = dht_type.upper()
        self.mock = not GPIO_AVAILABLE
        self._motor_pwm = None        # 电机 PWM 实例
        self._buzzer_pwm = None       # 蜂鸣器 PWM 实例
        self._led_blink_thread = None # LED 闪烁线程
        self._blink_stop = threading.Event()
        self._initialized = False
        try:
            self._setup()
        except Exception as e:
            # 初始化失败时降级为 Mock，避免影响上层服务
            self.mock = True
            self._init_error = str(e)

    # -------------------- 初始化与清理 --------------------
    def _setup(self) -> None:
        """配置 GPIO 模式与引脚方向（仅在真实硬件上执行）。"""
        if self.mock:
            return
        _RPI_GPIO.setmode(_RPI_GPIO.BCM)
        _RPI_GPIO.setwarnings(False)
        # 输出引脚
        for key in ("led", "buzzer", "relay", "motor_in1", "motor_in2", "motor_pwm"):
            _RPI_GPIO.setup(self.pins[key], _RPI_GPIO.OUT, initial=_RPI_GPIO.LOW)
        # 电机 PWM
        self._motor_pwm = _RPI_GPIO.PWM(self.pins["motor_pwm"], 1000)
        self._motor_pwm.start(0)
        # 蜂鸣器 PWM（默认关闭）
        self._buzzer_pwm = _RPI_GPIO.PWM(self.pins["buzzer"], 2000)
        self._buzzer_pwm.start(0)
        self._initialized = True

    def cleanup(self) -> Dict:
        """释放 GPIO 资源，返回结果 dict。"""
        try:
            self._blink_stop.set()
            if self._motor_pwm is not None:
                self._motor_pwm.stop()
            if self._buzzer_pwm is not None:
                self._buzzer_pwm.stop()
            if not self.mock and self._initialized:
                _RPI_GPIO.cleanup()
            self._initialized = False
            return {"status": "ok", "message": "GPIO 已释放"}
        except Exception as e:
            return {"status": "error", "message": f"清理失败: {e}", "mock": self.mock}

    # -------------------- LED 控制 --------------------
    def led_on(self) -> Dict:
        """点亮 LED。"""
        try:
            if not self.mock:
                _RPI_GPIO.output(self.pins["led"], _RPI_GPIO.HIGH)
            return {"status": "ok", "led": "on", "pin": self.pins["led"], "mock": self.mock}
        except Exception as e:
            return {"status": "error", "message": str(e), "mock": self.mock}

    def led_off(self) -> Dict:
        """熄灭 LED。"""
        try:
            self._blink_stop.set()
            if not self.mock:
                _RPI_GPIO.output(self.pins["led"], _RPI_GPIO.LOW)
            return {"status": "ok", "led": "off", "pin": self.pins["led"], "mock": self.mock}
        except Exception as e:
            return {"status": "error", "message": str(e), "mock": self.mock}

    def led_blink(self, times: int = 5, interval: float = 0.3) -> Dict:
        """以指定次数和间隔闪烁 LED（后台线程执行）。

        :param times: 闪烁次数
        :param interval: 每次亮灭间隔（秒）
        """
        try:
            self._blink_stop.set()
            if times <= 0:
                return {"status": "error", "message": "闪烁次数必须为正整数"}
            self._blink_stop = threading.Event()
            stop = self._blink_stop

            def _blink():
                for _ in range(times):
                    if stop.is_set():
                        break
                    if not self.mock:
                        _RPI_GPIO.output(self.pins["led"], _RPI_GPIO.HIGH)
                    time.sleep(interval)
                    if stop.is_set():
                        break
                    if not self.mock:
                        _RPI_GPIO.output(self.pins["led"], _RPI_GPIO.LOW)
                    time.sleep(interval)
                if not stop.is_set() and not self.mock:
                    _RPI_GPIO.output(self.pins["led"], _RPI_GPIO.LOW)

            self._led_blink_thread = threading.Thread(target=_blink, daemon=True)
            self._led_blink_thread.start()
            return {"status": "ok", "led": "blink", "times": times,
                    "interval": interval, "mock": self.mock}
        except Exception as e:
            return {"status": "error", "message": str(e), "mock": self.mock}

    # -------------------- 蜂鸣器控制 --------------------
    def buzzer_on(self) -> Dict:
        """蜂鸣器持续响（默认占空比）。"""
        try:
            if not self.mock:
                self._buzzer_pwm.ChangeDutyCycle(50)
            return {"status": "ok", "buzzer": "on", "pin": self.pins["buzzer"], "mock": self.mock}
        except Exception as e:
            return {"status": "error", "message": str(e), "mock": self.mock}

    def buzzer_off(self) -> Dict:
        """蜂鸣器停止。"""
        try:
            if not self.mock:
                self._buzzer_pwm.ChangeDutyCycle(0)
            return {"status": "ok", "buzzer": "off", "pin": self.pins["buzzer"], "mock": self.mock}
        except Exception as e:
            return {"status": "error", "message": str(e), "mock": self.mock}

    def buzzer_tone(self, frequency: int = 1000, duration: float = 0.3) -> Dict:
        """以指定频率播放蜂鸣器音调并自动停止。

        :param frequency: 频率（Hz）
        :param duration: 持续时间（秒）
        """
        try:
            if frequency <= 0:
                return {"status": "error", "message": "频率必须为正整数"}
            if not self.mock:
                self._buzzer_pwm.ChangeFrequency(frequency)
                self._buzzer_pwm.ChangeDutyCycle(50)
                time.sleep(duration)
                self._buzzer_pwm.ChangeDutyCycle(0)
            return {"status": "ok", "buzzer": "tone", "frequency": frequency,
                    "duration": duration, "mock": self.mock}
        except Exception as e:
            return {"status": "error", "message": str(e), "mock": self.mock}

    # -------------------- 继电器控制 --------------------
    def relay_on(self) -> Dict:
        """继电器吸合（常开触点闭合）。"""
        try:
            if not self.mock:
                _RPI_GPIO.output(self.pins["relay"], _RPI_GPIO.HIGH)
            return {"status": "ok", "relay": "on", "pin": self.pins["relay"], "mock": self.mock}
        except Exception as e:
            return {"status": "error", "message": str(e), "mock": self.mock}

    def relay_off(self) -> Dict:
        """继电器断开。"""
        try:
            if not self.mock:
                _RPI_GPIO.output(self.pins["relay"], _RPI_GPIO.LOW)
            return {"status": "ok", "relay": "off", "pin": self.pins["relay"], "mock": self.mock}
        except Exception as e:
            return {"status": "error", "message": str(e), "mock": self.mock}

    # -------------------- 电机驱动 --------------------
    def motor_forward(self, speed: int = 60) -> Dict:
        """电机正转。

        :param speed: 速度百分比 0-100
        """
        try:
            speed = max(0, min(100, int(speed)))
            if not self.mock:
                _RPI_GPIO.output(self.pins["motor_in1"], _RPI_GPIO.HIGH)
                _RPI_GPIO.output(self.pins["motor_in2"], _RPI_GPIO.LOW)
                self._motor_pwm.ChangeDutyCycle(speed)
            return {"status": "ok", "motor": "forward", "speed": speed, "mock": self.mock}
        except Exception as e:
            return {"status": "error", "message": str(e), "mock": self.mock}

    def motor_backward(self, speed: int = 60) -> Dict:
        """电机反转。

        :param speed: 速度百分比 0-100
        """
        try:
            speed = max(0, min(100, int(speed)))
            if not self.mock:
                _RPI_GPIO.output(self.pins["motor_in1"], _RPI_GPIO.LOW)
                _RPI_GPIO.output(self.pins["motor_in2"], _RPI_GPIO.HIGH)
                self._motor_pwm.ChangeDutyCycle(speed)
            return {"status": "ok", "motor": "backward", "speed": speed, "mock": self.mock}
        except Exception as e:
            return {"status": "error", "message": str(e), "mock": self.mock}

    def motor_stop(self) -> Dict:
        """电机停止。"""
        try:
            if not self.mock:
                _RPI_GPIO.output(self.pins["motor_in1"], _RPI_GPIO.LOW)
                _RPI_GPIO.output(self.pins["motor_in2"], _RPI_GPIO.LOW)
                self._motor_pwm.ChangeDutyCycle(0)
            return {"status": "ok", "motor": "stop", "mock": self.mock}
        except Exception as e:
            return {"status": "error", "message": str(e), "mock": self.mock}

    def motor_set_speed(self, speed: int = 60) -> Dict:
        """仅调整电机 PWM 占空比（不改变方向）。

        :param speed: 速度百分比 0-100
        """
        try:
            speed = max(0, min(100, int(speed)))
            if not self.mock:
                self._motor_pwm.ChangeDutyCycle(speed)
            return {"status": "ok", "motor": "speed", "speed": speed, "mock": self.mock}
        except Exception as e:
            return {"status": "error", "message": str(e), "mock": self.mock}

    # -------------------- 温湿度传感器 --------------------
    def read_dht(self) -> Dict:
        """读取 DHT11/DHT22 温湿度数据。

        当 DHT 库不可用或读取失败时返回带 error 字段的 dict（Mock 模式返回占位值）。
        """
        if self.mock or not DHT_AVAILABLE:
            # Mock 降级：返回模拟数据，便于上层联调
            return {
                "status": "ok",
                "temperature": 25.0,
                "humidity": 50.0,
                "sensor": self.dht_type,
                "mock": True,
            }
        try:
            sensor_map = {"DHT11": _DHT_LIB.DHT11, "DHT22": _DHT_LIB.DHT22}
            sensor = sensor_map.get(self.dht_type, _DHT_LIB.DHT11)
            humidity, temperature = _DHT_LIB.read_retry(sensor, self.pins["dht"])
            if humidity is not None and temperature is not None:
                return {
                    "status": "ok",
                    "temperature": round(float(temperature), 2),
                    "humidity": round(float(humidity), 2),
                    "sensor": self.dht_type,
                    "mock": False,
                }
            return {"status": "error", "message": "传感器读数失败",
                    "sensor": self.dht_type, "mock": False}
        except Exception as e:
            return {"status": "error", "message": str(e),
                    "sensor": self.dht_type, "mock": False}

    # -------------------- 状态查询 --------------------
    def get_status(self) -> Dict:
        """返回 GPIO 控制器当前状态概览。"""
        return {
            "gpio_available": GPIO_AVAILABLE,
            "dht_available": DHT_AVAILABLE,
            "mock": self.mock,
            "initialized": self._initialized,
            "pins": self.pins,
            "dht_type": self.dht_type,
        }


if __name__ == "__main__":
    import json
    gpio = PiGPIO()
    print(json.dumps(gpio.get_status(), ensure_ascii=False, indent=2))
    print(json.dumps(gpio.led_on(), ensure_ascii=False))
    print(json.dumps(gpio.read_dht(), ensure_ascii=False))
    gpio.cleanup()
