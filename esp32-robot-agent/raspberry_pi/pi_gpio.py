"""
树莓派 GPIO 控制模块
===================
功能:
  - LED 控制（开/关/闪烁）
  - 蜂鸣器控制（响/停/音调）
  - 继电器/电机驱动（正转/反转/停止/速度 PWM）
  - 温湿度传感器读取（DHT11/DHT22）

设计原则:
  - 优先使用 RPi.GPIO；若运行在非树莓派环境（无硬件），
    自动降级为 Mock 模式，保证上层逻辑可正常调用。
  - 所有公开方法均有异常处理，返回结构化结果（dict），不抛出异常。
"""
import time
import logging
from typing import Dict, Optional

logger = logging.getLogger("pi_gpio")

# 是否成功加载 RPi.GPIO
_HW_AVAILABLE = False
try:
    import RPi.GPIO as GPIO
    _HW_AVAILABLE = True
except ImportError:
    logger.warning("未安装 RPi.GPIO，进入 Mock 模式（仅记录日志，不操作硬件）")

# DHT 传感器依赖（可选，不安装也不影响其他功能）
_DHT_AVAILABLE = False
try:
    import Adafruit_DHT  # type: ignore
    _DHT_AVAILABLE = True
except ImportError:
    try:
        import adafruit_dht  # type: ignore
        import board  # type: ignore
        _DHT_AVAILABLE = True
    except ImportError:
        logger.warning("未安装 DHT 传感器库，温湿度读取功能不可用")


class PiGPIO:
    """树莓派 GPIO 统一控制类，支持硬件不可用时的优雅降级"""

    def __init__(self, mode: str = "BCM"):
        """
        初始化 GPIO。
        :param mode: 引脚编号模式，"BCM"（GPIO 编号）或 "BOARD"（物理引脚编号）
        """
        self.mode = mode
        self.available = _HW_AVAILABLE
        # 引脚状态记录（即使在 Mock 模式下也用于状态查询）
        self._pin_states: Dict[int, bool] = {}
        self._pwm_objects: Dict[int, object] = {}

        if self.available:
            try:
                GPIO.setmode(GPIO.BCM if mode == "BCM" else GPIO.BOARD)
                GPIO.setwarnings(False)
                logger.info("GPIO 初始化成功，模式: %s", mode)
            except Exception as e:
                logger.error("GPIO 初始化失败: %s", e)
                self.available = False
        else:
            logger.info("GPIO 运行在 Mock 模式")

    # ---------------- LED 控制 ----------------
    def led_setup(self, pin: int) -> Dict:
        """配置 LED 引脚为输出模式"""
        try:
            if self.available:
                GPIO.setup(pin, GPIO.OUT)
            self._pin_states[pin] = False
            logger.info("LED 引脚 %d 已配置为输出", pin)
            return {"status": "ok", "pin": pin}
        except Exception as e:
            logger.error("LED 引脚 %d 配置失败: %s", pin, e)
            return {"status": "error", "message": str(e)}

    def led_on(self, pin: int) -> Dict:
        """点亮 LED"""
        try:
            if self.available:
                GPIO.output(pin, GPIO.HIGH)
            self._pin_states[pin] = True
            logger.debug("LED 引脚 %d 点亮", pin)
            return {"status": "ok", "pin": pin, "state": "on"}
        except Exception as e:
            logger.error("LED 引脚 %d 点亮失败: %s", pin, e)
            return {"status": "error", "message": str(e)}

    def led_off(self, pin: int) -> Dict:
        """熄灭 LED"""
        try:
            if self.available:
                GPIO.output(pin, GPIO.LOW)
            self._pin_states[pin] = False
            logger.debug("LED 引脚 %d 熄灭", pin)
            return {"status": "ok", "pin": pin, "state": "off"}
        except Exception as e:
            logger.error("LED 引脚 %d 熄灭失败: %s", pin, e)
            return {"status": "error", "message": str(e)}

    def led_blink(self, pin: int, times: int = 3, interval: float = 0.3) -> Dict:
        """LED 闪烁指定次数"""
        try:
            for _ in range(times):
                self.led_on(pin)
                time.sleep(interval)
                self.led_off(pin)
                time.sleep(interval)
            return {"status": "ok", "pin": pin, "times": times}
        except Exception as e:
            logger.error("LED 引脚 %d 闪烁失败: %s", pin, e)
            return {"status": "error", "message": str(e)}

    # ---------------- 蜂鸣器控制 ----------------
    def buzzer_setup(self, pin: int) -> Dict:
        """配置蜂鸣器引脚为输出模式"""
        return self.led_setup(pin)  # 复用输出配置逻辑

    def buzzer_on(self, pin: int, duration: Optional[float] = None) -> Dict:
        """
        蜂鸣器响。
        :param duration: 响铃时长（秒），None 表示持续响
        """
        result = self.led_on(pin)
        if duration is not None and result["status"] == "ok":
            time.sleep(duration)
            self.led_off(pin)
        return {"status": "ok", "pin": pin, "duration": duration}

    def buzzer_off(self, pin: int) -> Dict:
        """蜂鸣器停止"""
        return self.led_off(pin)

    def buzzer_beep(self, pin: int, frequency: int = 1000, duration: float = 0.2) -> Dict:
        """
        蜂鸣器以指定频率响铃（使用 PWM 产生音调）。
        :param frequency: 频率 Hz
        :param duration: 响铃时长 秒
        """
        try:
            if self.available:
                pwm = GPIO.PWM(pin, frequency)
                pwm.start(50)  # 50% 占空比
                time.sleep(duration)
                pwm.stop()
            else:
                time.sleep(duration)
                logger.debug("Mock: 蜂鸣器 %dHz %.2fs", frequency, duration)
            return {"status": "ok", "pin": pin, "frequency": frequency, "duration": duration}
        except Exception as e:
            logger.error("蜂鸣器 %d 响铃失败: %s", pin, e)
            return {"status": "error", "message": str(e)}

    # ---------------- 继电器 / 电机驱动 ----------------
    def relay_setup(self, pin: int, active_low: bool = True) -> Dict:
        """
        配置继电器引脚。
        :param active_low: 继电器是否低电平触发（多数模块为低电平触发）
        """
        try:
            if self.available:
                GPIO.setup(pin, GPIO.OUT)
                # 初始化为关闭状态
                GPIO.output(pin, GPIO.HIGH if active_low else GPIO.LOW)
            self._pin_states[pin] = False
            logger.info("继电器引脚 %d 已配置 (active_low=%s)", pin, active_low)
            return {"status": "ok", "pin": pin, "active_low": active_low}
        except Exception as e:
            logger.error("继电器引脚 %d 配置失败: %s", pin, e)
            return {"status": "error", "message": str(e)}

    def relay_on(self, pin: int, active_low: bool = True) -> Dict:
        """继电器吸合（开启）"""
        try:
            if self.available:
                GPIO.output(pin, GPIO.LOW if active_low else GPIO.HIGH)
            self._pin_states[pin] = True
            return {"status": "ok", "pin": pin, "state": "on"}
        except Exception as e:
            logger.error("继电器 %d 开启失败: %s", pin, e)
            return {"status": "error", "message": str(e)}

    def relay_off(self, pin: int, active_low: bool = True) -> Dict:
        """继电器断开（关闭）"""
        try:
            if self.available:
                GPIO.output(pin, GPIO.HIGH if active_low else GPIO.LOW)
            self._pin_states[pin] = False
            return {"status": "ok", "pin": pin, "state": "off"}
        except Exception as e:
            logger.error("继电器 %d 关闭失败: %s", pin, e)
            return {"status": "error", "message": str(e)}

    def motor_setup(self, in1: int, in2: int, pwm_pin: int) -> Dict:
        """
        配置 H 桥电机驱动引脚。
        :param in1: 方向控制引脚 1
        :param in2: 方向控制引脚 2
        :param pwm_pin: PWM 调速引脚
        """
        try:
            if self.available:
                GPIO.setup(in1, GPIO.OUT)
                GPIO.setup(in2, GPIO.OUT)
                GPIO.setup(pwm_pin, GPIO.OUT)
                pwm = GPIO.PWM(pwm_pin, 1000)
                pwm.start(0)
                self._pwm_objects[pwm_pin] = pwm
            logger.info("电机驱动已配置 in1=%d in2=%d pwm=%d", in1, in2, pwm_pin)
            return {"status": "ok", "in1": in1, "in2": in2, "pwm_pin": pwm_pin}
        except Exception as e:
            logger.error("电机驱动配置失败: %s", e)
            return {"status": "error", "message": str(e)}

    def motor_forward(self, in1: int, in2: int, pwm_pin: int, speed: int = 60) -> Dict:
        """电机正转，speed: 0-100"""
        try:
            speed = max(0, min(100, speed))
            if self.available:
                GPIO.output(in1, GPIO.HIGH)
                GPIO.output(in2, GPIO.LOW)
                pwm = self._pwm_objects.get(pwm_pin)
                if pwm:
                    pwm.ChangeDutyCycle(speed)
            logger.debug("电机正转 speed=%d", speed)
            return {"status": "ok", "direction": "forward", "speed": speed}
        except Exception as e:
            logger.error("电机正转失败: %s", e)
            return {"status": "error", "message": str(e)}

    def motor_backward(self, in1: int, in2: int, pwm_pin: int, speed: int = 60) -> Dict:
        """电机反转，speed: 0-100"""
        try:
            speed = max(0, min(100, speed))
            if self.available:
                GPIO.output(in1, GPIO.LOW)
                GPIO.output(in2, GPIO.HIGH)
                pwm = self._pwm_objects.get(pwm_pin)
                if pwm:
                    pwm.ChangeDutyCycle(speed)
            logger.debug("电机反转 speed=%d", speed)
            return {"status": "ok", "direction": "backward", "speed": speed}
        except Exception as e:
            logger.error("电机反转失败: %s", e)
            return {"status": "error", "message": str(e)}

    def motor_stop(self, in1: int, in2: int, pwm_pin: int) -> Dict:
        """电机停止"""
        try:
            if self.available:
                GPIO.output(in1, GPIO.LOW)
                GPIO.output(in2, GPIO.LOW)
                pwm = self._pwm_objects.get(pwm_pin)
                if pwm:
                    pwm.ChangeDutyCycle(0)
            logger.debug("电机停止")
            return {"status": "ok", "direction": "stop"}
        except Exception as e:
            logger.error("电机停止失败: %s", e)
            return {"status": "error", "message": str(e)}

    # ---------------- 温湿度传感器 (DHT11/DHT22) ----------------
    def read_dht(self, pin: int, sensor_type: str = "DHT22") -> Dict:
        """
        读取 DHT11/DHT22 温湿度传感器。
        :param pin: 数据引脚（BCM 编号）
        :param sensor_type: "DHT11" 或 "DHT22"
        :return: {"temperature": float, "humidity": float} 或 {"error": ...}
        """
        if not _DHT_AVAILABLE:
            return {"status": "error", "message": "DHT 传感器库未安装"}
        try:
            temperature = None
            humidity = None
            # 兼容两种库
            if "Adafruit_DHT" in dir() or "Adafruit_DHT" in __import__("sys").modules:
                sensor = Adafruit_DHT.DHT22 if sensor_type.upper() == "DHT22" else Adafruit_DHT.DHT11
                humidity, temperature = Adafruit_DHT.read_retry(sensor, pin)
            else:
                # adafruit-circuitpython-dht 新版库
                dht_device = adafruit_dht.DHT22(getattr(board, f"D{pin}")) if sensor_type.upper() == "DHT22" \
                    else adafruit_dht.DHT11(getattr(board, f"D{pin}"))
                temperature = dht_device.temperature
                humidity = dht_device.humidity
                dht_device.exit()

            if temperature is not None and humidity is not None:
                return {
                    "status": "ok",
                    "sensor": sensor_type,
                    "pin": pin,
                    "temperature": round(temperature, 1),
                    "humidity": round(humidity, 1),
                }
            return {"status": "error", "message": "传感器读取失败（可能未连接）"}
        except Exception as e:
            logger.error("DHT 读取失败: %s", e)
            return {"status": "error", "message": str(e)}

    # ---------------- 状态查询与清理 ----------------
    def get_pin_state(self, pin: int) -> bool:
        """查询引脚当前记录状态（仅软件层面记录）"""
        return self._pin_states.get(pin, False)

    def cleanup(self) -> None:
        """释放所有 GPIO 资源"""
        try:
            # 停止所有 PWM
            for pwm in self._pwm_objects.values():
                try:
                    pwm.stop()
                except Exception:
                    pass
            self._pwm_objects.clear()
            if self.available:
                GPIO.cleanup()
            logger.info("GPIO 资源已释放")
        except Exception as e:
            logger.error("GPIO 清理失败: %s", e)
