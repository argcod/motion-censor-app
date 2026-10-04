const int pirPin = 4;
const int ledPin = 19;
const int buzzerPin = 18;

// --- CONFIGURATION ---
// Change these values depending on where you place this specific sensor!
String location = "Room1";
String sensorID = "Sensor01";
// ---------------------

bool detected = false;

void setup() {
  Serial.begin(115200);

  pinMode(pirPin, INPUT);
  pinMode(ledPin, OUTPUT);
  pinMode(buzzerPin, OUTPUT);

  Serial.println("SYSTEM_READY");
}

void loop() {
  int motion = digitalRead(pirPin);

  if (motion == HIGH && !detected) {
    // Send the dynamic location and sensor ID
    Serial.println("MOTION," + location + "," + sensorID);

    digitalWrite(ledPin, HIGH);
    digitalWrite(buzzerPin, HIGH);
    delay(1000);

    digitalWrite(ledPin, LOW);
    digitalWrite(buzzerPin, LOW);

    detected = true;
  }

  if (motion == LOW) {
    detected = false;
  }

  delay(100);
}
