#ifndef ROBOT_CONTROL_H
#define ROBOT_CONTROL_H

#include <ESP32Servo.h>
#include "config.h"

class RobotControl {
public:
    void begin();
    void setLeftServo(int angle);
    void setRightServo(int angle);
    void setArmServo(int angle);
    void setLED(bool on);
    float readDistance();
    void stop();
    void forward(int speed = 90);
    void backward(int speed = 90);
    void turnLeft(int speed = 90);
    void turnRight(int speed = 90);

private:
    Servo servoLeft;
    Servo servoRight;
    Servo servoArm;
};

#endif
