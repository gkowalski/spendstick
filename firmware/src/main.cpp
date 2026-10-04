// T-Dongle C5: shows Anthropic usage/cost frames pushed by the host over USB serial.
// Protocol: one JSON object per line (see src/sticks3/frames.py). Layout is landscape 160x80.
#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <ArduinoJson.h>
#include <SPI.h>

#define FW_VERSION "0.4.1"

// T-Dongle C5 pins (LilyGO pinout)
constexpr int PIN_MOSI = 2, PIN_MISO = 7, PIN_SCK = 6, PIN_CS = 10, PIN_DC = 3, PIN_BL = 0, PIN_RST = 1;
constexpr int PIN_BTN = 28;

constexpr uint32_t SCREEN_MS = 60000;
constexpr uint32_t STALE_S = 180;

Adafruit_ST7735 tft(&SPI, PIN_CS, PIN_DC, PIN_RST);
GFXcanvas16 canvas(160, 80);

struct Usage {
  bool valid = false;
  uint64_t in = 0, out = 0, cacheR = 0, cacheW = 0, d7 = 0;
  uint32_t spark[7] = {};  // daily totals, last 7 days
  uint8_t nSpark = 0;
  char top[24] = "";
  uint32_t rxMs = 0;
} usage;

struct Cost {
  bool valid = false;
  float today = 0, d7 = 0;
  float spark[7] = {};
  uint8_t nSpark = 0;
  char top[24] = "";
  uint32_t rxMs = 0;
} cost;

struct Reset {
  bool valid = false;
  uint32_t leftS = 0;   // seconds to the reset at the time the frame arrived
  float elapsed = 0;    // fraction of the period already used
  float mtd = 0;
  char date[12] = "";
  uint32_t rxMs = 0;
} reset;

struct Models {
  bool valid = false;
  uint8_t n = 0;       // rows stored (max 4)
  uint8_t total = 0;   // total models seen by the host
  char name[4][26] = {};
  uint64_t tokens[4] = {};
  float usd[4] = {};
  uint32_t rxMs = 0;
} models;

constexpr uint8_t NUM_SCREENS = 4;
uint8_t screen = 0;
uint32_t screenSince = 0;
String line;
bool needRender = false;

// RGB565 palette
uint16_t C_BG, C_FG, C_DIM, C_USAGE, C_COST, C_RESET, C_MODELS, C_BAD;

String fmtTokens(uint64_t n) {
  char b[16];
  if (n >= 1000000000ULL) snprintf(b, sizeof b, "%.2fB", n / 1e9);
  else if (n >= 1000000ULL) snprintf(b, sizeof b, "%.2fM", n / 1e6);
  else if (n >= 1000ULL) snprintf(b, sizeof b, "%.1fK", n / 1e3);
  else snprintf(b, sizeof b, "%llu", (unsigned long long)n);
  return b;
}

String shortModel(const char* m, size_t maxLen = 14) {
  String s(m);
  if (s.startsWith("claude-")) s.remove(0, 7);
  if (s.length() > maxLen) s = s.substring(0, maxLen);
  return s;
}

void drawHeader(const char* title, uint16_t accent, uint32_t rxMs, bool valid) {
  canvas.fillRect(0, 0, 160, 12, accent);
  canvas.setTextColor(C_BG);
  canvas.setTextSize(1);
  canvas.setCursor(3, 2);
  canvas.print(title);
  bool stale = !valid || (millis() - rxMs) / 1000 > STALE_S;
  canvas.fillCircle(152, 6, 3, stale ? C_BAD : C_BG);
  // Seconds until the screen switches.
  uint32_t elapsed = millis() - screenSince;
  uint32_t left = elapsed >= SCREEN_MS ? 0 : (SCREEN_MS - elapsed + 999) / 1000;
  char b[12];
  snprintf(b, sizeof b, "%lus", (unsigned long)left);
  int16_t x1, y1;
  uint16_t w, h;
  canvas.getTextBounds(b, 0, 0, &x1, &y1, &w, &h);
  canvas.setCursor(144 - w, 2);
  canvas.print(b);
}

template <typename T>
void drawBars(const T* v, uint8_t n, int x, int y, int w, int h, uint16_t color) {
  if (n == 0) return;
  T mx = 0;
  for (uint8_t i = 0; i < n; i++) if (v[i] > mx) mx = v[i];
  if (mx <= 0) mx = 1;
  int bw = w / n;
  for (uint8_t i = 0; i < n; i++) {
    int bh = (int)((float)v[i] / mx * h);
    if (v[i] > 0 && bh < 1) bh = 1;
    canvas.fillRect(x + i * bw, y + h - bh, bw > 2 ? bw - 1 : bw, bh, color);
  }
}

void drawWaiting(const char* title, uint16_t accent) {
  drawHeader(title, accent, 0, false);
  canvas.setTextColor(C_DIM);
  canvas.setTextSize(1);
  canvas.setCursor(8, 38);
  canvas.print("waiting for host...");
}

void drawUsage() {
  canvas.fillScreen(C_BG);
  if (!usage.valid) return drawWaiting("USAGE 7d", C_USAGE);
  drawHeader("USAGE 7d", C_USAGE, usage.rxMs, true);
  canvas.setTextColor(C_FG);
  canvas.setTextSize(3);
  canvas.setCursor(4, 16);
  canvas.print(fmtTokens(usage.d7));
  canvas.setTextSize(1);
  canvas.setTextColor(C_DIM);
  canvas.setCursor(4, 42);
  canvas.printf("24h in %s out %s", fmtTokens(usage.in).c_str(), fmtTokens(usage.out).c_str());
  canvas.setCursor(4, 52);
  canvas.print("tokens, 7 days");
  drawBars(usage.spark, usage.nSpark, 4, 62, 152, 16, C_USAGE);
}

void drawCost() {
  canvas.fillScreen(C_BG);
  if (!cost.valid) return drawWaiting("COST 7d", C_COST);
  drawHeader("COST 7d", C_COST, cost.rxMs, true);
  canvas.setTextColor(C_FG);
  canvas.setTextSize(3);
  canvas.setCursor(4, 16);
  canvas.printf("$%.2f", cost.d7);
  canvas.setTextSize(1);
  canvas.setTextColor(C_DIM);
  canvas.setCursor(4, 42);
  canvas.printf("today $%.2f", cost.today);
  canvas.setCursor(4, 52);
  canvas.print(cost.top[0] ? cost.top : "no spend");
  drawBars(cost.spark, cost.nSpark, 4, 62, 152, 16, C_COST);
}

void drawModels() {
  canvas.fillScreen(C_BG);
  if (!models.valid) return drawWaiting("MODELS 7d", C_MODELS);
  drawHeader("MODELS 7d", C_MODELS, models.rxMs, true);
  canvas.setTextSize(1);
  if (models.n == 0) {
    canvas.setTextColor(C_DIM);
    canvas.setCursor(8, 38);
    canvas.print("no model usage");
    return;
  }
  for (uint8_t i = 0; i < models.n; i++) {
    int y = 16 + i * 12;
    if (i % 2 == 0) canvas.fillRect(0, y - 2, 160, 12, tft.color565(22, 26, 36));
    canvas.setTextColor(C_FG);
    canvas.setCursor(3, y);
    canvas.print(shortModel(models.name[i], 11));
    canvas.setTextColor(C_DIM);
    canvas.setCursor(76, y);
    canvas.print(fmtTokens(models.tokens[i]));
    char b[12];
    snprintf(b, sizeof b, "$%.2f", models.usd[i]);
    int16_t x1, y1;
    uint16_t w, h;
    canvas.getTextBounds(b, 0, 0, &x1, &y1, &w, &h);
    canvas.setTextColor(C_MODELS);
    canvas.setCursor(157 - w, y);
    canvas.print(b);
  }
  if (models.total > models.n) {
    canvas.setTextColor(C_DIM);
    canvas.setCursor(3, 69);
    canvas.printf("+%u more", (unsigned)(models.total - models.n));
  }
}

void drawReset() {
  canvas.fillScreen(C_BG);
  if (!reset.valid) return drawWaiting("RESET monthly", C_RESET);
  drawHeader("RESET monthly", C_RESET, reset.rxMs, true);
  uint32_t passed = (millis() - reset.rxMs) / 1000;
  uint32_t left = reset.leftS > passed ? reset.leftS - passed : 0;
  uint32_t d = left / 86400, h = (left % 86400) / 3600, m = (left % 3600) / 60;
  char b[16];
  if (d > 0) snprintf(b, sizeof b, "%lud %luh", (unsigned long)d, (unsigned long)h);
  else snprintf(b, sizeof b, "%luh %lum", (unsigned long)h, (unsigned long)m);
  canvas.setTextColor(C_FG);
  canvas.setTextSize(3);
  canvas.setCursor(4, 16);
  canvas.print(b);
  canvas.setTextSize(1);
  canvas.setTextColor(C_DIM);
  canvas.setCursor(4, 42);
  canvas.printf("resets %s 00:00 UTC", reset.date);
  canvas.setCursor(4, 52);
  canvas.printf("month to date $%.2f", reset.mtd);
  canvas.drawRect(4, 64, 152, 10, C_DIM);
  canvas.fillRect(5, 65, (int)(150 * reset.elapsed), 8, C_RESET);
}

void render() {
  if (screen == 0) drawUsage();
  else if (screen == 1) drawCost();
  else if (screen == 2) drawModels();
  else drawReset();
  tft.drawRGBBitmap(0, 0, canvas.getBuffer(), 160, 80);
}

void handleLine(const String& s) {
  JsonDocument doc;
  if (deserializeJson(doc, s)) return;
  const char* t = doc["t"] | "";
  if (!strcmp(t, "hello")) {
    Serial.println("{\"ok\":\"tdongle-c5\",\"fw\":\"" FW_VERSION "\"}");
  } else if (!strcmp(t, "usage")) {
    usage.in = doc["h24"]["in"] | 0ULL;
    usage.out = doc["h24"]["out"] | 0ULL;
    usage.cacheR = doc["h24"]["cache_r"] | 0ULL;
    usage.cacheW = doc["h24"]["cache_w"] | 0ULL;
    JsonObject d7 = doc["d7"];
    usage.d7 = (uint64_t)(d7["in"] | 0ULL) + (d7["out"] | 0ULL) + (d7["cache_r"] | 0ULL) + (d7["cache_w"] | 0ULL);
    JsonArray sp = doc["spark7"];
    usage.nSpark = 0;
    for (JsonVariant v : sp) if (usage.nSpark < 7) usage.spark[usage.nSpark++] = v.as<uint32_t>();
    usage.valid = true;
    usage.rxMs = millis();
  } else if (!strcmp(t, "cost")) {
    cost.today = doc["today"] | 0.0f;
    cost.d7 = doc["d7"] | 0.0f;
    JsonArray sp = doc["spark7"];
    cost.nSpark = 0;
    for (JsonVariant v : sp) if (cost.nSpark < 7) cost.spark[cost.nSpark++] = v.as<float>();
    cost.top[0] = 0;
    JsonArray top = doc["top"];
    if (top.size() > 0) {
      snprintf(cost.top, sizeof cost.top, "%s $%.2f", shortModel(top[0][0] | "").c_str(), (float)(top[0][1] | 0.0f));
    }
    cost.valid = true;
    cost.rxMs = millis();
  } else if (!strcmp(t, "models")) {
    models.total = doc["n"] | 0;
    models.n = 0;
    for (JsonArray row : doc["rows"].as<JsonArray>()) {
      if (models.n >= 4) break;
      snprintf(models.name[models.n], sizeof models.name[0], "%s", (const char*)(row[0] | ""));
      models.tokens[models.n] = row[1] | 0ULL;
      models.usd[models.n] = row[2] | 0.0f;
      models.n++;
    }
    models.valid = true;
    models.rxMs = millis();
  } else if (!strcmp(t, "reset")) {
    reset.leftS = doc["left_s"] | 0u;
    reset.elapsed = doc["elapsed"] | 0.0f;
    reset.mtd = doc["mtd"] | 0.0f;
    snprintf(reset.date, sizeof reset.date, "%s", (const char*)(doc["date"] | ""));
    reset.valid = true;
    reset.rxMs = millis();
  } else {
    return;
  }
  // Redraw from loop(), not here, so back-to-back frames aren't lost while the LCD refreshes.
  needRender = true;
  Serial.printf("{\"rx\":\"%s\"}\n", t);
}

void setup() {
  Serial.setRxBufferSize(4096);  // must precede begin(); default 256 B overflows on bursts
  Serial.begin(115200);
  delay(1500);
  Serial.println("boot: serial up");
  pinMode(PIN_BL, OUTPUT);
  digitalWrite(PIN_BL, LOW);  // backlight is active-low on LilyGO T-Dongle boards
  pinMode(PIN_BTN, INPUT_PULLUP);
  Serial.println("boot: spi.begin");
  SPI.begin(PIN_SCK, PIN_MISO, PIN_MOSI, PIN_CS);
  Serial.println("boot: tft.initR");
  tft.initR(INITR_MINI160x80);  // 0.96" 80x160 panel; may need invertDisplay(false) or a _PLUGIN init
  Serial.println("boot: tft init done");
  tft.invertDisplay(true);
  tft.setRotation(3);
  C_BG = tft.color565(8, 10, 16);
  C_FG = tft.color565(240, 240, 245);
  C_DIM = tft.color565(140, 146, 160);
  C_USAGE = tft.color565(255, 150, 60);
  C_COST = tft.color565(60, 200, 180);
  C_RESET = tft.color565(150, 130, 255);
  C_MODELS = tft.color565(255, 205, 70);
  C_BAD = tft.color565(230, 60, 60);
  line.reserve(2048);
  Serial.println("boot: first render");
  render();
  Serial.println("boot: setup done");
  screenSince = millis();
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      handleLine(line);
      line = "";
    } else if (c != '\r' && line.length() < 2048) {
      line += c;
    }
  }

  if (needRender) {
    needRender = false;
    render();
  }

  static bool btnPrev = true;
  bool btn = digitalRead(PIN_BTN);
  bool flip = (!btn && btnPrev);
  btnPrev = btn;

  static uint32_t lastTick = 0;
  if (flip || millis() - screenSince >= SCREEN_MS) {
    screen = (screen + 1) % NUM_SCREENS;
    screenSince = millis();
    render();
  } else if (millis() - lastTick >= 1000) {  // refresh the age readout
    lastTick = millis();
    render();
  }
}
