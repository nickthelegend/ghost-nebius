/*
 * ghost-node.ino -- a GHOST sensing node: one ESP32 per room, no camera.
 *
 * It joins the home Wi-Fi, pings the router ~100 times a second, and records
 * the channel state information (CSI) of every reply: 64 subcarrier
 * amplitudes that ripple when someone in the room breathes or moves. Batches
 * go to the GHOST hub over UDP in the same "GC1" format HOTARU uses, so the
 * hub treats lamps and nodes alike. Where to put it: on the far side of the
 * room from the router, so the person is between the two.
 *
 * Board: any ESP32 / ESP32-S3 / ESP32-C3 on arduino-esp32 core 3.x. No libraries.
 *   arduino-cli compile --fqbn esp32:esp32:esp32s3 firmware/ghost-node
 *
 * Settings: copy secrets.example.h to secrets.h.
 * The onboard LED (if any) blinks once per 100 CSI frames: a quick health check.
 */
#include <WiFi.h>
#include <WiFiUdp.h>
#include "esp_wifi.h"
#include "ping/ping_sock.h"
#include "secrets.h"

#ifndef NODE_NAME
#define NODE_NAME "node"
#endif
#ifndef GHOST_HUB_PORT
#define GHOST_HUB_PORT 8770
#endif
#ifndef CSI_HZ
#define CSI_HZ 100
#endif
#ifndef LED_PIN
#define LED_PIN -1
#endif

struct CsiRec { uint32_t ms; int8_t rssi; uint8_t n; uint8_t amp[64]; };
static QueueHandle_t q;
static uint8_t ap[6];
static WiFiUDP udp;
static volatile uint32_t frames = 0;
static esp_ping_handle_t pinger = nullptr;

static void onCsi(void*, wifi_csi_info_t* info) {
  if (!info || !info->buf || memcmp(info->mac, ap, 6) != 0) return;
  CsiRec r;
  r.ms = millis();
  r.rssi = info->rx_ctrl.rssi;
  int n = min(64, (int)(info->len / 2));
  r.n = n;
  for (int k = 0; k < n; k++) {
    float im = info->buf[2 * k], re = info->buf[2 * k + 1];
    r.amp[k] = (uint8_t)min(255.0f, sqrtf(re * re + im * im));
  }
  frames++;
  xQueueSend(q, &r, 0);
}

static bool startCsi() {
  memcpy(ap, WiFi.BSSID(), 6);
  wifi_csi_config_t c = {};
  c.lltf_en = true;
  c.ltf_merge_en = true;
  if (esp_wifi_set_csi_config(&c) != ESP_OK || esp_wifi_set_csi_rx_cb(onCsi, nullptr) != ESP_OK ||
      esp_wifi_set_csi(true) != ESP_OK) return false;
  esp_ping_config_t pc = ESP_PING_DEFAULT_CONFIG();
  IPAddress gw = WiFi.gatewayIP();
  IP_ADDR4(&pc.target_addr, gw[0], gw[1], gw[2], gw[3]);
  pc.count = ESP_PING_COUNT_INFINITE;
  pc.interval_ms = 1000 / CSI_HZ;
  pc.timeout_ms = 500;
  pc.data_size = 8;
  esp_ping_callbacks_t cb = {};
  return esp_ping_new_session(&pc, &cb, &pinger) == ESP_OK && esp_ping_start(pinger) == ESP_OK;
}

static void hello() {
  // Tells the hub which room this sender is: "GH1 <name>"
  String s = String("GH1 ") + NODE_NAME;
  udp.beginPacket(GHOST_HUB_HOST, GHOST_HUB_PORT + 1);
  udp.write((const uint8_t*)s.c_str(), s.length());
  udp.endPacket();
}

void setup() {
  Serial.begin(115200);
  delay(300);
  if (LED_PIN >= 0) pinMode(LED_PIN, OUTPUT);
  q = xQueueCreate(64, sizeof(CsiRec));
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.printf("\nGHOST node '%s' joining %s", NODE_NAME, WIFI_SSID);
  while (WiFi.status() != WL_CONNECTED) { delay(300); Serial.print('.'); }
  Serial.printf("\n%s  %d dBm  router %s\n", WiFi.localIP().toString().c_str(), WiFi.RSSI(),
                WiFi.gatewayIP().toString().c_str());
  udp.begin(GHOST_HUB_PORT + 2);
  Serial.println(startCsi() ? "CSI on" : "*** CSI failed to start ***");
  hello();
}

void loop() {
  static uint32_t lastHello = 0, lastRate = 0, lastFrames = 0, lastBlink = 0;
  static uint8_t pkt[4 + 8 * 70];
  CsiRec r;
  int count = 0, at = 4;
  while (count < 8 && xQueueReceive(q, &r, pdMS_TO_TICKS(5)) == pdTRUE) {
    memcpy(pkt + at, &r.ms, 4); at += 4;
    pkt[at++] = (uint8_t)r.rssi;
    pkt[at++] = r.n;
    memcpy(pkt + at, r.amp, r.n); at += r.n;
    count++;
  }
  if (count) {
    pkt[0] = 'G'; pkt[1] = 'C'; pkt[2] = '1'; pkt[3] = count;
    udp.beginPacket(GHOST_HUB_HOST, GHOST_HUB_PORT + 1);
    udp.write(pkt, at);
    udp.endPacket();
  }
  uint32_t now = millis();
  if (now - lastHello > 10000) { lastHello = now; hello(); }
  if (now - lastRate > 5000) {
    Serial.printf("csi %lu Hz  rssi %d\n", (unsigned long)((frames - lastFrames) / 5), WiFi.RSSI());
    lastFrames = frames; lastRate = now;
  }
  if (LED_PIN >= 0 && frames / 100 != lastBlink) { lastBlink = frames / 100; digitalWrite(LED_PIN, lastBlink & 1); }
  if (WiFi.status() != WL_CONNECTED) { WiFi.reconnect(); delay(500); }
}
