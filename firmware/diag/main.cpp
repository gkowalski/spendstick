// Minimal bring-up image: logs over USB serial and lights the backlight. No display/SPI code.
#include <Arduino.h>

void setup() {
  Serial.begin(115200);
  pinMode(0, OUTPUT);
  digitalWrite(0, HIGH);
}

void loop() {
  static uint32_t n = 0;
  Serial.printf("diag alive %lu\n", (unsigned long)n++);
  delay(1000);
}
