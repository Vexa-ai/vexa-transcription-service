# Real-Time Audio Transcription Service

A **production-ready, scalable** real-time audio transcription system designed for **enterprise and SaaS applications**. This system powers **secure, private, and highly accurate speech-to-text conversion**, serving as the **backbone for Vexa.ai**, an **alternative to Otter.ai, Fireflies.ai, and Tactiq.io**, enabling enterprises to build custom AI-powered conversation processing solutions.

> **🔒 Enterprise-Grade Security & Compliance** Unlike cloud-based transcription services, this system allows for full **on-premise deployment**, ensuring that all transcription data remains within your organization's infrastructure. Ideal for **high-security environments**.

## 🚀 Why Choose This Transcription System?

### **Enterprise-First Approach**

✔ **Multiuser Production-Ready** – Built for **enterprise-scale** deployment ✔ **Data Sovereignty** – Your audio and text **never leave your network** ✔ **GDPR & HIPAA Compliance** – Meet strict data privacy regulations ✔ **Custom Security Policies** – Integrate with your **existing authentication** & access controls ✔ **Air-Gapped Deployment** – Works in **offline environments** ✔ **Enterprise Scalability** – Designed for large workloads, supporting 1000s of concurrent users

### **Core Capabilities**

✅ **Real-time transcription** with speaker detection\
✅ **Multi-platform support** – **Google Meet Chrome Extension available**, future integrations for Zoom, Microsoft Teams, Slack, etc.\
✅ **Bring Your Own Data Source** – Flexible API allows integration with **custom platforms**\
✅ **5-10 second transcription latency** for seamless live captions\
✅ **Redis-backed storage** for fast retrieval & webhook-based integrations\
✅ **Whisper v3 (optimized) for high-accuracy speech-to-text**\
✅ **GPU acceleration** for ultra-fast processing

---

## 🏢 **Who Should Use This?**

We are actively looking for **enterprises and SaaS teams** currently using services like **Otter.ai, Fireflies.ai, and Tactiq.io**, but need **better privacy, control, and customization**.

🔹 **Enterprise Meeting Transcription** – Automate meeting notes with speaker attribution\
🔹 **Customer Support & Call Centers** – Real-time call transcription & agent assistance\
🔹 **Education & Accessibility** – Create searchable lecture transcripts & captions\
🔹 **Content Creation** – Transcribe podcasts, generate subtitles, and repurpose audio content\
🔹 **Medical & Healthcare** – Secure, HIPAA-compliant transcription for patient records\
🔹 **Sales & CRM** – Capture and analyze sales calls for insights and training\
🔹 **Internal Management Meetings** – Automate documentation of leadership discussions\
🔹 **Legal & Compliance** – Generate accurate transcripts for legal proceedings and documentation

---

## ⚙️ System Architecture

The pipeline consists of **scalable microservices** designed for **high-volume real-time transcription**:

### **1️⃣ StreamQueue API** – Handles reliable audio ingestion

- Ensures delivery of **audio chunks every 3 seconds**
- Supports **multiple concurrent sessions**

### **2️⃣ Audio Processing Service** – Core audio transcription engine

- Calls **Whisper Service** for speech-to-text processing
- Stores transcriptions **with speaker metadata** in Redis
- Supports **webhook integrations** for real-time updates

### **3️⃣ Whisper Service** – GPU-powered transcription module

- Runs **Whisper large-v3** model for **best accuracy**
- Deployed with **Ray Serve** for **scalability & efficiency**

### **4️⃣ Redis Storage** – Fast, ephemeral transcript storage

- Enables **quick retrieval & session-based storage**
- Serves as a **message broker** between services

---

## 🛠 **Quick Start**

### **1. Clone the Repositories**

```sh
# Clone the audio processing service
git clone https://github.com/yourusername/audio.git

# Clone the whisper service
git clone https://github.com/yourusername/whisper_service.git
```

### **2. Configure the Environment**

```sh
# Set up environment variables for audio service
cd audio
cp .env.example .env

# Set up environment variables for whisper service
cd ../whisper_service
cp .env.example .env
```

Edit `.env` files to configure **API tokens, GPU settings, and webhooks**.

### **3. Start the Whisper Service** (GPU Required)

```sh
cd whisper_service
docker-compose up -d
```

### **4. Start the Audio Service**

```sh
cd ../audio
docker-compose up -d
```

---

## 🔌 **Integration Guide**

### **1️⃣ Sending Audio Chunks** (Example in JavaScript)

```js
async function sendAudioChunk(audioBlob, sessionId) {
  await fetch('http://your-server:8000/api/audio/stream', {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer your_api_token',
      'Content-Type': 'application/octet-stream',
      'X-Session-ID': sessionId
    },
    body: audioBlob
  });
}
```

### **2️⃣ Updating Speaker Info**

```js
async function updateSpeaker(sessionId, speakerName) {
  await fetch('http://your-server:8000/api/speaker', {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer your_api_token',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ session_id: sessionId, speaker_name: speakerName })
  });
}
```

### **3️⃣ Receiving Transcriptions via Webhook**

```python
from fastapi import FastAPI, Body
from pydantic import BaseModel
from typing import List, Dict

app = FastAPI()

class TranscriptionSegment(BaseModel):
    content: str
    start_timestamp: str
    end_timestamp: str
    speaker: str = None
    words: List[Dict] = []

@app.post("/api/transcriptions/{session_id}")
async def receive_transcription(session_id: str, segments: List[TranscriptionSegment] = Body(...)):
    print("Transcription received:", segments)
    return {"status": "success"}
```

---

## 🤝 **How to Contribute**

We welcome **contributions from enterprises and developers**! If your company is migrating from **Otter.ai, Fireflies, or Tactiq**, we’d love to hear your use case.

### **Ways to Contribute**

\
✅ **Optimize latency & scaling** for enterprise workloads\
✅ **Enhance security & compliance features**\
✅ **Integrate with CRM, customer support tools, and knowledge bases**\
✅ **Integrate with Zoom and Microsoft Teams for seamless transcription**

🚀 **Join the open-source effort today!** Submit a **Pull Request**, open a **GitHub Issue**, or **contact us**.

---

## 🔗 **Related Projects**

This project is a core component of **[Vexa](https://vexa.ai)** – an **AI-powered meeting intelligence** platform that extends transcription into **business knowledge extraction**.

🔹 Try Vexa for **real-time transcription & AI-driven insights**: [vexa.ai](https://vexa.ai)\
🔹 Follow us: [@vexa.ai](https://linkedin.com/company/vexa-ai)\
🔹 Join our **developer community**: [Vexa Discord](https://discord.gg/vexa)

⭐ **Star this repo** to get notified when the public release goes live!

