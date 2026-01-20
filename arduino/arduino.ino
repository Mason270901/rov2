#include <Servo.h>

const int NUM_THRUSTERS = 6;
const int thrusterPins[NUM_THRUSTERS] = {8, 12, 13, 9, 11, 10};  // UL, FL, BL, UR, FR, BR
const int clawPin = 22;

Servo thrusters[NUM_THRUSTERS];
Servo claw;

float surge = 0, sway = 0, yaw = 0, heave = 0;
float clawPos = 0.5;
bool calibrate = false;

const int NEUTRAL = 1500;
const int RANGE = 400;

const int CLAW_OPEN = 120;
const int CLAW_CLOSED = 10;

void setup() {
  Serial.begin(115200);

  for (int i = 0; i < NUM_THRUSTERS; i++) {
    thrusters[i].attach(thrusterPins[i]);
    thrusters[i].writeMicroseconds(NEUTRAL);
  }

  claw.attach(clawPin);
  claw.write(CLAW_OPEN);

  delay(5000);  // ESC arming delay
}

void loop() {
  readSerial();

  if (calibrate) {
    runCalibration();
  } else {
    updateThrusters();
    updateClaw();
  }
}

void readSerial() {
  static String line = "";
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      parseLine(line);
      line = "";
    } else if (c != '\r') {
      line += c;
    }
  }
}

void parseLine(const String &line) {
  surge     = getValue(line, "SURGE");
  sway      = getValue(line, "SWAY");
  yaw       = getValue(line, "YAW");
  heave     = getValue(line, "HEAVE");
  clawPos   = getValue(line, "CLAW_POS");
  calibrate = (getValue(line, "CALIBRATE") > 0.5);
}

float getValue(const String &line, const String &key) {
  int idx = line.indexOf(key);
  if (idx < 0) return 0;
  idx += key.length();
  while (idx < line.length() && line[idx] == ' ') idx++;
  int end = idx;
  while (end < line.length() && line[end] != ' ') end++;
  return line.substring(idx, end).toFloat();
}

void updateThrusters() {
  float t[NUM_THRUSTERS];

  t[0] = surge + sway + yaw;  // UL
  t[1] = surge - sway + yaw;  // FL
  t[2] = surge - sway - yaw;  // BL
  t[3] = surge + sway - yaw;  // UR
  t[4] = heave;               // FR
  t[5] = heave;               // BR

  for (int i = 0; i < NUM_THRUSTERS; i++) {
    t[i] = constrain(t[i], -1.0, 1.0);
    int pulse = NEUTRAL + (int)(t[i] * RANGE);
    thrusters[i].writeMicroseconds(pulse);
  }
}

void updateClaw() {
  clawPos = constrain(clawPos, 0.0, 1.0);
  int angle = CLAW_OPEN + (int)((CLAW_CLOSED - CLAW_OPEN) * clawPos);
  claw.write(angle);
}

void runCalibration() {
  static unsigned long last = 0;
  static int phase = 0;

  if (millis() - last > 1500) {
    last = millis();
    phase++;
  }

  if (phase == 0) {
    for (int i = 0; i < NUM_THRUSTERS; i++) {
      thrusters[i].writeMicroseconds(NEUTRAL);
    }
    claw.write(CLAW_OPEN);
  }

  if (phase == 1) {
    claw.write(CLAW_CLOSED);
  }

  if (phase >= 2 && phase <= 7) {
    int idx = phase - 2;
    for (int i = 0; i < NUM_THRUSTERS; i++) {
      if (i == idx) thrusters[i].writeMicroseconds(NEUTRAL + 200);
      else thrusters[i].writeMicroseconds(NEUTRAL);
    }
  }

  if (phase > 7) phase = 0;
}