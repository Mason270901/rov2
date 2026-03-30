#include <Servo.h>
#include <math.h>

const int NUM_THRUSTERS = 6;
// avoid pin 13 for anything because it toggles during programming
const int thrusterPins[NUM_THRUSTERS] = {8, 12, 7, 9, 11, 10};  // UL, FL, BL, UR, FR, BR
const int clawPin = 22;

// GY-61 (ADXL335) accelerometer on analog pins
const int ACCEL_X_PIN = A0;
const int ACCEL_Y_PIN = A1;
const int ACCEL_Z_PIN = A2;

// Accelerometer calibration for 3.3V supply on 5V AREF
// 0g output = Vs/2 = 1.65V → ADC ≈ 338, sensitivity ≈ 300mV/g → ~61 counts/g
const float ACCEL_MID_X = 338.0;
const float ACCEL_MID_Y = 338.0;
const float ACCEL_MID_Z = 338.0;
const float ACCEL_SCALE = 61.0;

// Accelerometer low-pass filter (0..1, lower = smoother)
const float ACCEL_ALPHA = 0.1;
float ax_f = 0, ay_f = 0, az_f = 0;

// Computed orientation (degrees)
float pitch = 0, rollAngle = 0;

// Roll leveling
bool levelEnabled = false;
const float LEVEL_KP = 0.5;  // proportional gain — tune to taste

// Set to -1 if sensor is mounted component-side-down, 1 if component-side-up
const float ACCEL_Z_SIGN = -1.0;

// Telemetry timing
unsigned long lastTelemetry = 0;
const unsigned long TELEMETRY_INTERVAL = 100;  // ms

Servo thrusters[NUM_THRUSTERS];
Servo claw;

float surge = 0, sway = 0, yaw = 0, heave = 0;
float clawPos = 0.5;
bool calibrate = false;

// const float THRUSTER_ALPHA = 0.02;


// THRUSTER_ALPHA
// lower numbers filter more.
// with a value of 0.0002. holding the stick at full throttle, then
// releasing it, it takes the motors about 7.5 seconds to spool down to zero
const float THRUSTER_ALPHA = 0.0002*2*10;
float t_prev[NUM_THRUSTERS] = {0};

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

  Serial.println("board init, waiting for esc");

  for (int i = 0; i < 5; i++) {
    Serial.print("ESC wait ");
    Serial.println( 5 - (i + 1) );
    delay(1000);
  }

  Serial.println("done");
}

void loop() {
  readSerial();
  readAccelerometer();

  if (calibrate) {
    runCalibration();
  } else {
    updateThrusters();
    updateClaw();
  }

  sendTelemetry();
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
  surge       = getValue(line, "SURGE");
  sway        = getValue(line, "SWAY");
  yaw         = getValue(line, "YAW");
  heave       = getValue(line, "HEAVE");
  clawPos     = getValue(line, "CLAW_POS");
  calibrate   = (getValue(line, "CALIBRATE") > 0.5);
  levelEnabled = (getValue(line, "LEVEL") > 0.5);
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

  t[0] = surge + yaw - sway + 0;  // front left
  t[1] = surge - yaw + sway;  // front right
  t[2] = surge - yaw - sway;  // back right
  t[3] = surge + yaw + sway;  // back left

  // Vertical thrusters with optional roll leveling
  float rollCorrection = 0;
  if (levelEnabled) {
    // rollAngle > 0 means tilted right → need more lift on right side
    rollCorrection = constrain((rollAngle / 45.0) * LEVEL_KP, -1.0, 1.0);
  }
  t[4] = -heave + rollCorrection;  // up left
  t[5] = heave + rollCorrection;   // up right

  for (int i = 0; i < NUM_THRUSTERS; i++) {
    t[i] = constrain(t[i], -1.0, 1.0);
    float tf = THRUSTER_ALPHA * t[i] + (1.0 - THRUSTER_ALPHA) * t_prev[i];
    // Serial.print("t["); Serial.print(i); Serial.print("]="); Serial.print(t[i]); Serial.print(" tf="); Serial.println(tf);
    tf = constrain(tf, -1.0, 1.0);
    t_prev[i] = tf;
    int pulse = NEUTRAL + (int)(tf * RANGE);
    // int pulse = NEUTRAL + (int)(t[i] * RANGE);
    thrusters[i].writeMicroseconds(pulse);
  }
}

void updateClaw() {
  clawPos = constrain(clawPos, 0.0, 1.0);
  int angle = CLAW_OPEN + (int)((CLAW_CLOSED - CLAW_OPEN) * clawPos);
  claw.write(angle);
}

void readAccelerometer() {
  float ax_raw = (analogRead(ACCEL_X_PIN) - ACCEL_MID_X) / ACCEL_SCALE;
  float ay_raw = (analogRead(ACCEL_Y_PIN) - ACCEL_MID_Y) / ACCEL_SCALE;
  float az_raw = (analogRead(ACCEL_Z_PIN) - ACCEL_MID_Z) / ACCEL_SCALE;

  // Low-pass filter
  ax_f = ACCEL_ALPHA * ax_raw + (1.0 - ACCEL_ALPHA) * ax_f;
  ay_f = ACCEL_ALPHA * ay_raw + (1.0 - ACCEL_ALPHA) * ay_f;
  az_f = ACCEL_ALPHA * (az_raw * ACCEL_Z_SIGN) + (1.0 - ACCEL_ALPHA) * az_f;

  rollAngle = atan2(ay_f, az_f) * 180.0 / M_PI;
  pitch     = atan2(-ax_f, sqrt(ay_f * ay_f + az_f * az_f)) * 180.0 / M_PI;
}

void sendTelemetry() {
  unsigned long now = millis();
  if (now - lastTelemetry >= TELEMETRY_INTERVAL) {
    lastTelemetry = now;
    Serial.print("TEL PITCH ");
    Serial.print(pitch, 1);
    Serial.print(" ROLL ");
    Serial.print(rollAngle, 1);
    Serial.print(" LEVEL ");
    Serial.println(levelEnabled ? 1 : 0);
  }
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
