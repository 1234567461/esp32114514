#include "robot_control.h"

void RobotControl::begin() {
    servoLeft.setPeriodHertz(SERVO_FREQ);
    servoRight.setPeriodHertz(SERVO_FREQ);
    servoArm.setPeriodHertz(SERVO_FREQ);
    servoLeft.attach(SERVO_PIN_LEFT, SERVO_MIN_PULSE, SERVO_MAX_PULSE);
    servoRight.attach(SERVO_PIN_RIGHT, SERVO_MIN_PULSE, SERVO_MAX_PULSE);
    servoArm.attach(SERVO_PIN_ARM, SERVO_MIN_PULSE, SERVO_MAX_PULSE);
    pinMode(LED_PIN, OUTPUT);
    pinMode(TRIG_PIN, OUTPUT);
    pinMode(ECHO_PIN, INPUT);
    stop();
}

void RobotControl::setLeftServo(int angle) {
    servoLeft.write(constrain(angle, 0, 180));
}

void RobotControl::setRightServo(int angle) {
    servoRight.write(constrain(angle, 0, 180));
}

void RobotControl::setArmServo(int angle) {
    servoArm.write(constrain(angle, 0, 180));
}

void RobotControl::setLED(bool on) {
    digitalWrite(LED_PIN, on ? HIGH : LOW);
}

float RobotControl::readDistance() {
    digitalWrite(TRIG_PIN, LOW);
    delayMicroseconds(2);
    digitalWrite(TRIG_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(TRIG_PIN, LOW);
    long duration = pulseIn(ECHO_PIN, HIGH, 30000);
    if (duration == 0) return -1;
    return duration * 0.034 / 2.0;
}

void RobotControl::stop() {
    servoLeft.write(90);
    servoRight.write(90);
}

void RobotControl::forward(int speed) {
    int v = map(speed, 0, 100, 90, 180);
    servoLeft.write(v);
    servoRight.write(180 - v + 90); // 反向轮
}

void RobotControl::backward(int speed) {
    int v = map(speed, 0, 100, 90, 0);
    servoLeft.write(v);
    servoRight.write(180 - v);
}

void RobotControl::turnLeft(int speed) {
    servoLeft.write(90 - map(speed, 0, 100, 0, 90));
    servoRight.write(90 + map(speed, 0, 100, 0, 90));
}

void RobotControl::turnRight(int speed) {
    servoLeft.write(90 + map(speed, 0, 100, 0, 90));
    servoRight.write(90 - map(speed, 0, 100, 0, 90));
}
